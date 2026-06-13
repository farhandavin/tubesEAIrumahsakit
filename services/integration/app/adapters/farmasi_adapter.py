"""
SOAP/XML Adapter for Farmasi (Pharmacy) Service.
THE KEY HETEROGENEITY COMPONENT — bridges REST ↔ SOAP protocol gap.
Uses raw HTTP + lxml to build and parse SOAP envelopes (not zeep) for
maximum reliability with spyne-based SOAP endpoints.
"""

import logging
import os

import httpx
from lxml import etree

logger = logging.getLogger(__name__)

FARMASI_SERVICE_URL = os.getenv(
    "FARMASI_SERVICE_URL", "http://farmasi-service:8003"
)

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TNS = "hospital.farmasi.soap"


def _build_soap_envelope(method_name: str, params: dict) -> str:
    """Build a complete SOAP 1.1 envelope with given method and parameters."""
    envelope = etree.Element(
        f"{{{SOAP_NS}}}Envelope",
        nsmap={
            "soap11env": SOAP_NS,
            "tns": TNS,
        },
    )
    body = etree.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    method = etree.SubElement(body, f"{{{TNS}}}{method_name}")

    for key, value in params.items():
        param_elem = etree.SubElement(method, f"{{{TNS}}}{key}")
        param_elem.text = str(value)

    xml_bytes = etree.tostring(
        envelope, pretty_print=True, xml_declaration=True, encoding="utf-8"
    )
    return xml_bytes.decode("utf-8")


def _parse_xml_text_recursive(text: str) -> dict:
    inner_dict = {}
    try:
        try:
            inner_root = etree.fromstring(text.encode("utf-8"))
        except etree.XMLSyntaxError:
            inner_root = etree.fromstring(f"<root>{text}</root>".encode("utf-8"))
        
        for inner_elem in inner_root.iter():
            if inner_elem.text and inner_elem.text.strip():
                inner_text = inner_elem.text.strip()
                if inner_text.startswith("<") and inner_text.endswith(">"):
                    inner_dict.update(_parse_xml_text_recursive(inner_text))
                else:
                    inner_tag = (
                        etree.QName(inner_elem.tag).localname
                        if "}" in inner_elem.tag
                        else inner_elem.tag
                    )
                    inner_dict[inner_tag] = inner_text
    except Exception as e:
        logger.warning("Failed to parse inner XML text recursively: %s", str(e))
    return inner_dict


def _parse_soap_response(xml_text: str) -> dict:
    """Parse a SOAP response XML and extract all leaf-node values."""
    result: dict = {}
    try:
        root = etree.fromstring(
            xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text
        )
        # Find Body element
        body = root.find(f".//{{{SOAP_NS}}}Body")
        target = body if body is not None else root

        for elem in target.iter():
            if elem.text and elem.text.strip():
                tag = (
                    etree.QName(elem.tag).localname
                    if "}" in elem.tag
                    else elem.tag
                )
                text_val = elem.text.strip()
                if text_val.startswith('<') and text_val.endswith('>'):
                    inner_res = _parse_xml_text_recursive(text_val)
                    if inner_res:
                        result.update(inner_res)
                    else:
                        result[tag] = text_val
                else:
                    result[tag] = text_val
    except etree.XMLSyntaxError as e:
        logger.error("XML parse error in SOAP response: %s", str(e))
        result["error"] = f"xml_parse_error: {e}"
        result["raw"] = xml_text[:500]
    except Exception as e:
        logger.error("Unexpected error parsing SOAP response: %s", str(e))
        result["error"] = str(e)
    return result



# --- Sync functions (for consumer threads) ---

def dispense_medicine(
    prescription_id: str,
    patient_id: int,
    patient_name: str,
    medicine_name: str,
    quantity: int,
) -> dict:
    """
    Call Farmasi SOAP service to dispense medicine (sync).
    Builds a SOAP envelope, POSTs to /soap, and parses the XML response.
    """
    url = f"{FARMASI_SERVICE_URL}/soap"
    logger.info(
        "Farmasi adapter: dispense_medicine — prescription=%s, patient=%d, "
        "medicine=%s, qty=%d",
        prescription_id,
        patient_id,
        medicine_name,
        quantity,
    )

    soap_xml = _build_soap_envelope(
        "dispense_medicine",
        {
            "prescription_id": prescription_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "medicine_name": medicine_name,
            "quantity": quantity,
        },
    )
    logger.debug("SOAP request:\n%s", soap_xml)

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                content=soap_xml,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "dispense_medicine",
                },
            )
            response.raise_for_status()
            response_text = response.text
            logger.debug("SOAP response:\n%s", response_text)

            result = _parse_soap_response(response_text)
            result["http_status"] = response.status_code
            logger.info(
                "Farmasi adapter: dispense_medicine succeeded — %s",
                result,
            )
            return result

    except httpx.ConnectError as e:
        logger.error(
            "Farmasi adapter: connection error for dispense_medicine: %s",
            str(e),
        )
        return {
            "error": "connection_error",
            "detail": str(e),
            "medicine_name": medicine_name,
        }
    except httpx.HTTPStatusError as e:
        logger.error(
            "Farmasi adapter: HTTP %d for dispense_medicine: %s",
            e.response.status_code,
            str(e),
        )
        return {
            "error": "http_error",
            "status_code": e.response.status_code,
            "detail": e.response.text[:500],
        }
    except Exception as e:
        logger.error(
            "Farmasi adapter: unexpected error for dispense_medicine: %s",
            str(e),
        )
        return {"error": "unexpected_error", "detail": str(e)}


def check_stock(medicine_name: str) -> dict:
    """
    Call Farmasi SOAP service to check medicine stock (sync).
    """
    url = f"{FARMASI_SERVICE_URL}/soap"
    logger.info(
        "Farmasi adapter: check_stock — medicine=%s", medicine_name
    )

    soap_xml = _build_soap_envelope(
        "check_stock",
        {"medicine_name": medicine_name},
    )

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                content=soap_xml,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "check_stock",
                },
            )
            response.raise_for_status()
            result = _parse_soap_response(response.text)
            result["http_status"] = response.status_code
            logger.info(
                "Farmasi adapter: check_stock result — %s", result
            )
            return result

    except httpx.ConnectError as e:
        logger.error(
            "Farmasi adapter: connection error for check_stock: %s", str(e)
        )
        return {"error": "connection_error", "detail": str(e)}
    except httpx.HTTPStatusError as e:
        logger.error(
            "Farmasi adapter: HTTP %d for check_stock: %s",
            e.response.status_code,
            str(e),
        )
        return {"error": "http_error", "status_code": e.response.status_code}
    except Exception as e:
        logger.error(
            "Farmasi adapter: unexpected error for check_stock: %s", str(e)
        )
        return {"error": "unexpected_error", "detail": str(e)}


# --- Async versions (for FastAPI route handlers) ---

async def dispense_medicine_async(
    prescription_id: str,
    patient_id: int,
    patient_name: str,
    medicine_name: str,
    quantity: int,
) -> dict:
    """Async version of dispense_medicine for use in FastAPI handlers."""
    url = f"{FARMASI_SERVICE_URL}/soap"
    soap_xml = _build_soap_envelope(
        "dispense_medicine",
        {
            "prescription_id": prescription_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "medicine_name": medicine_name,
            "quantity": quantity,
        },
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                content=soap_xml,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "dispense_medicine",
                },
            )
            response.raise_for_status()
            result = _parse_soap_response(response.text)
            result["http_status"] = response.status_code
            return result
    except Exception as e:
        logger.error("Farmasi adapter (async): dispense error: %s", str(e))
        return {"error": str(e)}


async def check_stock_async(medicine_name: str) -> dict:
    """Async version of check_stock for use in FastAPI handlers."""
    url = f"{FARMASI_SERVICE_URL}/soap"
    soap_xml = _build_soap_envelope(
        "check_stock",
        {"medicine_name": medicine_name},
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                content=soap_xml,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "check_stock",
                },
            )
            response.raise_for_status()
            result = _parse_soap_response(response.text)
            result["http_status"] = response.status_code
            return result
    except Exception as e:
        logger.error("Farmasi adapter (async): check_stock error: %s", str(e))
        return {"error": str(e)}
