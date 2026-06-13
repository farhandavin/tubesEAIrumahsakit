"""
Message Translator — handles format transformations between systems.
Implements the EIP Message Translator pattern to bridge different data formats
across Registrasi (REST), EMR (REST), Farmasi (SOAP/XML), and Billing (REST).
"""

import logging
from datetime import datetime
from typing import Optional

from lxml import etree

from .canonical_models import (
    CanonicalPatient,
    CanonicalPrescription,
    CanonicalPrescriptionItem,
    CanonicalBillingEntry,
)

logger = logging.getLogger(__name__)


def patient_event_to_canonical(raw_message: dict) -> CanonicalPatient:
    """Convert raw patient registration event to canonical format."""
    try:
        logger.info(
            "Transforming patient event to canonical: patient_id=%s",
            raw_message.get("id", "unknown"),
        )
        canonical = CanonicalPatient(
            source_id=raw_message.get("id", 0),
            nama=raw_message.get("nama", ""),
            nik=raw_message.get("nik", ""),
            tanggal_lahir=raw_message.get("tanggal_lahir", ""),
            jenis_kelamin=raw_message.get("jenis_kelamin", ""),
            alamat=raw_message.get("alamat", ""),
            no_telepon=raw_message.get("no_telepon", ""),
            payment_type=raw_message.get("payment_type", "UMUM"),
            event_type=raw_message.get("event_type", "patient.registered"),
            timestamp=raw_message.get(
                "timestamp", datetime.utcnow().isoformat()
            ),
        )
        logger.info(
            "Successfully transformed patient event: source_id=%d, nama=%s",
            canonical.source_id,
            canonical.nama,
        )
        return canonical
    except Exception as e:
        logger.error("Failed to transform patient event: %s", str(e))
        raise


def prescription_event_to_canonical(raw_message: dict) -> CanonicalPrescription:
    """Convert raw prescription event to canonical format."""
    try:
        logger.info(
            "Transforming prescription event to canonical: prescription_id=%s",
            raw_message.get("prescription_id", "unknown"),
        )
        items = []
        for item in raw_message.get("items", []):
            items.append(
                CanonicalPrescriptionItem(
                    medicine_name=item.get("medicine_name", ""),
                    quantity=item.get("quantity", 0),
                    dosage=item.get("dosage", ""),
                )
            )

        canonical = CanonicalPrescription(
            prescription_id=str(raw_message.get("prescription_id", "")),
            patient_id=raw_message.get("patient_id", 0),
            patient_name=raw_message.get("patient_name", ""),
            doctor_name=raw_message.get("doctor_name", ""),
            diagnosis=raw_message.get("diagnosis", ""),
            items=items,
            payment_type=raw_message.get("payment_type", "UMUM"),
            event_type=raw_message.get("event_type", "prescription.created"),
            timestamp=raw_message.get(
                "timestamp", datetime.utcnow().isoformat()
            ),
        )
        logger.info(
            "Successfully transformed prescription event: id=%s, items_count=%d",
            canonical.prescription_id,
            len(canonical.items),
        )
        return canonical
    except Exception as e:
        logger.error("Failed to transform prescription event: %s", str(e))
        raise


def canonical_prescription_to_soap_xml(
    prescription: CanonicalPrescription,
) -> list[str]:
    """
    Convert canonical prescription to a list of SOAP XML strings for Farmasi.
    Returns one XML per item so each can be dispatched individually.
    """
    xml_list: list[str] = []
    try:
        for item in prescription.items:
            root = etree.Element("dispenseRequest")
            etree.SubElement(root, "prescriptionId").text = str(
                prescription.prescription_id
            )
            etree.SubElement(root, "patientId").text = str(
                prescription.patient_id
            )
            etree.SubElement(root, "patientName").text = prescription.patient_name
            etree.SubElement(root, "medicineName").text = item.medicine_name
            etree.SubElement(root, "quantity").text = str(item.quantity)

            xml_str = etree.tostring(
                root, pretty_print=True, xml_declaration=False, encoding="unicode"
            )
            xml_list.append(xml_str)
            logger.debug(
                "Generated SOAP XML for item: %s", item.medicine_name
            )

        logger.info(
            "Generated %d SOAP XML requests for prescription %s",
            len(xml_list),
            prescription.prescription_id,
        )
        return xml_list
    except Exception as e:
        logger.error("Failed to generate SOAP XML: %s", str(e))
        raise


def soap_xml_response_to_dict(xml_response: str) -> dict:
    """Parse SOAP XML response from Farmasi back into dict format."""
    try:
        logger.debug("Parsing SOAP XML response (%d chars)", len(xml_response))
        root = etree.fromstring(xml_response.encode("utf-8") if isinstance(xml_response, str) else xml_response)

        # Navigate into SOAP Body
        namespaces = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "tns": "hospital.farmasi.soap",
        }

        body = root.find(".//soap:Body", namespaces)
        if body is None:
            # Try without namespace
            body = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Body")

        result: dict = {}
        if body is not None:
            for elem in body.iter():
                if elem.text and elem.text.strip():
                    # Strip namespace from tag
                    tag = etree.QName(elem.tag).localname if "}" in elem.tag else elem.tag
                    result[tag] = elem.text.strip()
        else:
            # Fallback: parse entire document
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    tag = etree.QName(elem.tag).localname if "}" in elem.tag else elem.tag
                    result[tag] = elem.text.strip()

        logger.info("Parsed SOAP response: %d fields extracted", len(result))
        return result
    except etree.XMLSyntaxError as e:
        logger.error("XML syntax error parsing SOAP response: %s", str(e))
        return {"error": str(e), "raw_response": xml_response[:500]}
    except Exception as e:
        logger.error("Failed to parse SOAP XML response: %s", str(e))
        return {"error": str(e)}


def canonical_to_billing_entry(
    prescription: CanonicalPrescription, total_amount: float
) -> CanonicalBillingEntry:
    """Convert prescription to billing entry with calculated amount."""
    try:
        medicine_names = ", ".join(
            [item.medicine_name for item in prescription.items]
        )
        billing = CanonicalBillingEntry(
            patient_id=prescription.patient_id,
            patient_name=prescription.patient_name,
            description=f"Prescription {prescription.prescription_id}: {medicine_names}",
            amount=total_amount,
            entry_type="PRESCRIPTION",
            payment_type=prescription.payment_type,
            source_system="integration-service",
            event_type="billing.charge",
            timestamp=datetime.utcnow().isoformat(),
        )
        logger.info(
            "Created billing entry: patient_id=%d, amount=%.2f, payment_type=%s",
            billing.patient_id,
            billing.amount,
            billing.payment_type,
        )
        return billing
    except Exception as e:
        logger.error("Failed to create billing entry: %s", str(e))
        raise
