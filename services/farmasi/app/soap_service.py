import logging
from lxml import etree

from spyne import Application, ServiceBase, srpc, Unicode, Integer32
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication

from app.database import SessionLocal
from app.models import Medicine, Dispensation

logger = logging.getLogger(__name__)

TNS = "hospital.farmasi.soap"


class FarmasiService(ServiceBase):
    """SOAP service for pharmacy operations — dispensing, stock checks, and inventory listing."""

    @srpc(Unicode, Integer32, Unicode, Unicode, Integer32, _returns=Unicode)
    def dispense_medicine(prescription_id, patient_id, patient_name, medicine_name, quantity):
        """
        Dispense a medicine for a patient prescription.
        Finds the medicine by name (case-insensitive), validates stock,
        reduces stock, creates a dispensation record, and returns result XML.
        """
        db = SessionLocal()
        try:
            # Case-insensitive search
            medicine = (
                db.query(Medicine)
                .filter(Medicine.nama_obat.ilike(f"%{medicine_name}%"))
                .first()
            )

            if not medicine:
                root = etree.Element("DispenseResponse")
                etree.SubElement(root, "status").text = "ERROR"
                etree.SubElement(root, "message").text = (
                    f"Obat '{medicine_name}' tidak ditemukan dalam inventaris."
                )
                return etree.tostring(root, pretty_print=True, encoding="unicode")

            if medicine.stok < quantity:
                root = etree.Element("DispenseResponse")
                etree.SubElement(root, "status").text = "ERROR"
                etree.SubElement(root, "message").text = (
                    f"Stok tidak mencukupi untuk '{medicine.nama_obat}'. "
                    f"Stok tersedia: {medicine.stok}, diminta: {quantity}."
                )
                return etree.tostring(root, pretty_print=True, encoding="unicode")

            # Reduce stock
            medicine.stok -= quantity
            total_price = medicine.harga * quantity

            # Create dispensation record
            dispensation = Dispensation(
                prescription_id=prescription_id,
                patient_id=patient_id,
                patient_name=patient_name,
                medicine_name=medicine.nama_obat,
                quantity=quantity,
                total_price=total_price,
                status="DISPENSED",
            )
            db.add(dispensation)
            db.commit()
            db.refresh(dispensation)

            logger.info(
                "Dispensed %d x %s for patient %s (Rx: %s). Total: Rp %.0f",
                quantity, medicine.nama_obat, patient_name, prescription_id, total_price,
            )

            # Build success response XML
            root = etree.Element("DispenseResponse")
            etree.SubElement(root, "status").text = "SUCCESS"
            etree.SubElement(root, "dispensation_id").text = str(dispensation.id)
            etree.SubElement(root, "prescription_id").text = prescription_id
            etree.SubElement(root, "patient_name").text = patient_name
            etree.SubElement(root, "medicine_name").text = medicine.nama_obat
            etree.SubElement(root, "quantity").text = str(quantity)
            etree.SubElement(root, "total_price").text = f"{total_price:.0f}"
            etree.SubElement(root, "remaining_stock").text = str(medicine.stok)
            etree.SubElement(root, "message").text = "Obat berhasil diberikan."
            return etree.tostring(root, pretty_print=True, encoding="unicode")

        except Exception as e:
            db.rollback()
            logger.error("Error dispensing medicine: %s", e, exc_info=True)
            root = etree.Element("DispenseResponse")
            etree.SubElement(root, "status").text = "ERROR"
            etree.SubElement(root, "message").text = f"Internal error: {str(e)}"
            return etree.tostring(root, pretty_print=True, encoding="unicode")
        finally:
            db.close()

    @srpc(Unicode, _returns=Unicode)
    def check_stock(medicine_name):
        """
        Check the stock level for a specific medicine by name (case-insensitive search).
        Returns XML with medicine details or an error if not found.
        """
        db = SessionLocal()
        try:
            medicine = (
                db.query(Medicine)
                .filter(Medicine.nama_obat.ilike(f"%{medicine_name}%"))
                .first()
            )

            if not medicine:
                root = etree.Element("StockResponse")
                etree.SubElement(root, "status").text = "NOT_FOUND"
                etree.SubElement(root, "message").text = (
                    f"Obat '{medicine_name}' tidak ditemukan."
                )
                return etree.tostring(root, pretty_print=True, encoding="unicode")

            root = etree.Element("StockResponse")
            etree.SubElement(root, "status").text = "OK"
            med_el = etree.SubElement(root, "medicine")
            etree.SubElement(med_el, "nama_obat").text = medicine.nama_obat
            etree.SubElement(med_el, "stok").text = str(medicine.stok)
            etree.SubElement(med_el, "harga").text = f"{medicine.harga:.0f}"
            etree.SubElement(med_el, "satuan").text = medicine.satuan
            return etree.tostring(root, pretty_print=True, encoding="unicode")

        except Exception as e:
            logger.error("Error checking stock: %s", e, exc_info=True)
            root = etree.Element("StockResponse")
            etree.SubElement(root, "status").text = "ERROR"
            etree.SubElement(root, "message").text = f"Internal error: {str(e)}"
            return etree.tostring(root, pretty_print=True, encoding="unicode")
        finally:
            db.close()

    @srpc(_returns=Unicode)
    def get_all_medicines():
        """
        Retrieve the full medicine inventory with stock levels.
        Returns XML list of all medicines.
        """
        db = SessionLocal()
        try:
            medicines = db.query(Medicine).all()

            root = etree.Element("MedicinesResponse")
            etree.SubElement(root, "status").text = "OK"
            etree.SubElement(root, "count").text = str(len(medicines))

            list_el = etree.SubElement(root, "medicines")
            for med in medicines:
                med_el = etree.SubElement(list_el, "medicine")
                etree.SubElement(med_el, "id").text = str(med.id)
                etree.SubElement(med_el, "nama_obat").text = med.nama_obat
                etree.SubElement(med_el, "stok").text = str(med.stok)
                etree.SubElement(med_el, "harga").text = f"{med.harga:.0f}"
                etree.SubElement(med_el, "satuan").text = med.satuan

            return etree.tostring(root, pretty_print=True, encoding="unicode")

        except Exception as e:
            logger.error("Error getting all medicines: %s", e, exc_info=True)
            root = etree.Element("MedicinesResponse")
            etree.SubElement(root, "status").text = "ERROR"
            etree.SubElement(root, "message").text = f"Internal error: {str(e)}"
            return etree.tostring(root, pretty_print=True, encoding="unicode")
        finally:
            db.close()


def create_soap_app():
    """Create and return the Spyne WSGI application."""
    soap_application = Application(
        [FarmasiService],
        tns=TNS,
        name="FarmasiService",
        in_protocol=Soap11(validator="lxml"),
        out_protocol=Soap11(),
    )
    wsgi_app = WsgiApplication(soap_application)
    logger.info("SOAP application created. TNS=%s", TNS)
    return wsgi_app
