import uuid
import asyncio
import aiohttp
import re

from .const import (
    DEFAULT_FORMAT,
    DEFAULT_INPUT_SOURCE,
    DEFAULT_COLOR_MODE,
    DEFAULT_CONTENT_TYPE,
    DEFAULT_PAGE_WIDTH,
    DEFAULT_PAGE_HEIGHT,
    DEFAULT_RESOLUTION,
    DEFAULT_DUPLEX,
    MAX_PAGES,
)


# --- SOAP XML templates ---
GET_SCANNER_ELEMENTS_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:sca="http://schemas.microsoft.com/windows/2006/08/wdp/scan">
  <soap:Header>
    <wsa:To>{url}</wsa:To>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/scan/GetScannerElements</wsa:Action>
    <wsa:MessageID>urn:uuid:{msgid}</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:From>
      <wsa:Address>urn:uuid:{fromid}</wsa:Address>
    </wsa:From>
  </soap:Header>
  <soap:Body>
    <sca:GetScannerElementsRequest>
      <sca:RequestedElements>
        <sca:Name>sca:ScannerStatus</sca:Name>
        <sca:Name>sca:ScannerElements</sca:Name>
        <sca:Name>sca:AutoDocumentFeederStatus</sca:Name>
      </sca:RequestedElements>
    </sca:GetScannerElementsRequest>
  </soap:Body>
</soap:Envelope>

"""

# Minimal variant requesting only ScannerStatus, used as a fallback for devices
# that reject the extended request.
SCANNER_STATUS_ONLY_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:sca="http://schemas.microsoft.com/windows/2006/08/wdp/scan">
  <soap:Header>
    <wsa:To>{url}</wsa:To>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/scan/GetScannerElements</wsa:Action>
    <wsa:MessageID>urn:uuid:{msgid}</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:From>
      <wsa:Address>urn:uuid:{fromid}</wsa:Address>
    </wsa:From>
  </soap:Header>
  <soap:Body>
    <sca:GetScannerElementsRequest>
      <sca:RequestedElements>
        <sca:Name>sca:ScannerStatus</sca:Name>
      </sca:RequestedElements>
    </sca:GetScannerElementsRequest>
  </soap:Body>
</soap:Envelope>

"""
CREATE_SCAN_JOB_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:sca="http://schemas.microsoft.com/windows/2006/08/wdp/scan">
  <soap:Header>
    <wsa:To>{url}</wsa:To>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/scan/CreateScanJob</wsa:Action>
    <wsa:MessageID>urn:uuid:{msgid}</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:From>
      <wsa:Address>urn:uuid:python-client</wsa:Address>
    </wsa:From>
  </soap:Header>
  <soap:Body>
    <sca:CreateScanJobRequest>
      <sca:ScanTicket>
        <sca:JobDescription>
          <sca:JobName>Python Scan Job</sca:JobName>
          <sca:JobOriginatingUserName>Python Client</sca:JobOriginatingUserName>
          <sca:JobInformation>Scanning in auto mode..</sca:JobInformation>
        </sca:JobDescription>
        <sca:DocumentParameters>
          <sca:Format sca:MustHonor="true">{format}</sca:Format>
          <sca:InputSource sca:MustHonor="true">{input_source}</sca:InputSource>
          <sca:ContentType>{content_type}</sca:ContentType>
          <sca:ColorMode>{color_mode}</sca:ColorMode>
          {resolution_extra}{scanning_side_extra}
          <sca:Documents sca:MustHonor="true">
            <sca:DocumentDescription>
              <sca:DocumentName>ADF Scan</sca:DocumentName>
              <sca:MediaSize sca:MustHonor="true">
                <sca:Width>{page_width}</sca:Width>
                <sca:Height>{page_height}</sca:Height>
              </sca:MediaSize>
            </sca:DocumentDescription>
          </sca:Documents>
          <sca:DocumentHandling>
            <sca:Separators sca:MustHonor="true">None</sca:Separators>
            <sca:ReverseOrder>false</sca:ReverseOrder>
          </sca:DocumentHandling>
        </sca:DocumentParameters>
      </sca:ScanTicket>
    </sca:CreateScanJobRequest>
  </soap:Body>
</soap:Envelope>
"""

RETRIEVE_IMAGE_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:sca="http://schemas.microsoft.com/windows/2006/08/wdp/scan">
  <soap:Header>
    <wsa:To>{url}</wsa:To>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/scan/RetrieveImage</wsa:Action>
    <wsa:MessageID>urn:uuid:{msgid}</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:From>
      <wsa:Address>urn:uuid:python-client</wsa:Address>
    </wsa:From>
  </soap:Header>
  <soap:Body>
    <sca:RetrieveImageRequest>
      <sca:JobId>{jobid}</sca:JobId>
      <sca:JobToken>{jobtoken}</sca:JobToken>
      <sca:DocumentDescription>
        <sca:DocumentName>Python Scan</sca:DocumentName>
      </sca:DocumentDescription>
    </sca:RetrieveImageRequest>
  </soap:Body>
</soap:Envelope>
"""


# --- Helpers ---
def make_uuid() -> str:
    return str(uuid.uuid4())


async def async_soap_request(
    session: aiohttp.ClientSession, url: str, xml: str, step: str = "SOAP"
) -> bytes:
    headers = {"Content-Type": "application/soap+xml"}
    async with session.post(url, data=xml.encode("utf-8"), headers=headers) as resp:
        body = await resp.text(errors="ignore")
        if resp.status >= 400:
            snippet = body[:500]
            raise aiohttp.ClientResponseError(
                resp.request_info,
                resp.history,
                status=resp.status,
                message=(
                    f"{step} returned HTTP {resp.status}: {resp.reason} | "
                    f"body: {snippet}"
                ),
                headers=resp.headers,
            )
        return await resp.read()


def extract_jpeg_from_mtom(response_bytes: bytes) -> bytes:
    # Detect boundary from Content-Type
    m = re.search(rb"^--([^\r\n]+)", response_bytes, re.MULTILINE)
    if not m:
        raise Exception("MIME boundary not found in response")
    boundary = m.group(1)
    parts = response_bytes.split(b"--" + boundary)
    for part in parts:
        if b"Content-Type: image/jpeg" in part:
            split = re.split(rb"\r?\n\r?\n", part, maxsplit=1)
            if len(split) == 2:
                return split[1].strip().rstrip(b"--").strip()
    raise Exception("JPEG not found in MTOM response")


# --- Main API function ---
async def get_scanner_state(ip: str) -> dict:
    """Query scanner status, ADF status and scanner elements.

    Returns a dict with scanner state, state reason and ADF state.
    """
    url = f"http://{ip}/WebServices/ScannerService"
    async with aiohttp.ClientSession() as session:
        try:
            state_xml = GET_SCANNER_ELEMENTS_XML.format(
                url=url, msgid=make_uuid(), fromid=make_uuid()
            )
            resp_bytes = await async_soap_request(session, url, state_xml)
        except aiohttp.ClientResponseError:
            # Fall back to the minimal request some printers only accept.
            state_xml = SCANNER_STATUS_ONLY_XML.format(
                url=url, msgid=make_uuid(), fromid=make_uuid()
            )
            resp_bytes = await async_soap_request(session, url, state_xml)
        text = resp_bytes.decode("utf-8", errors="ignore")
        return {
            "state": _extract(text, r"<wscn:ScannerState>(.*?)</wscn:ScannerState>"),
            "state_reason": _extract(
                text, r"<wscn:ScannerStateReason>(.*?)</wscn:ScannerStateReason>"
            ),
            "adf_state": _extract(
                text, r"<wscn:AdfState>(.*?)</wscn:AdfState>"
            ),
            "raw": text,
        }


def _extract(text: str, pattern: str) -> str:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else "Unknown"


async def check_online(ip: str, timeout: float = 2.0) -> bool:
    """Return True if the scanner responds on its WSD scan service port."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 80), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def scan_jpeg(
    ip: str,
    max_pages: int = MAX_PAGES,
    color_mode: str = DEFAULT_COLOR_MODE,
    fmt: str = DEFAULT_FORMAT,
    input_source: str = DEFAULT_INPUT_SOURCE,
    content_type: str = DEFAULT_CONTENT_TYPE,
    resolution: int = DEFAULT_RESOLUTION,
    duplex: str = DEFAULT_DUPLEX,
    page_width: int = DEFAULT_PAGE_WIDTH,
    page_height: int = DEFAULT_PAGE_HEIGHT,
) -> list[bytes]:
    """Scan one or more pages (ADF) from a Brother scanner.

    Returns a list of JPEG bytes, one per scanned page.
    """
    url = f"http://{ip}/WebServices/ScannerService"
    async with aiohttp.ClientSession() as session:
        # 1. Ensure idle
        state_xml = GET_SCANNER_ELEMENTS_XML.format(
            url=url, msgid=make_uuid(), fromid=make_uuid()
        )
        resp_bytes = await async_soap_request(
            session, url, state_xml, step="GetScannerElements"
        )
        m = re.search(rb"<wscn:ScannerState>(.*?)</wscn:ScannerState>", resp_bytes)
        state = m.group(1).decode() if m else "Unknown"
        if state.lower() != "idle":
            raise Exception(f"Scanner not idle (state={state})")

        # 2. Create scan job (ADF multi-page)
        # The resolution and scanning-side fields are optional: they are only
        # added when explicitly requested, to stay compatible with devices that
        # reject them (which would otherwise cause a 400 on RetrieveImage).
        resolution_extra = ""
        if resolution != DEFAULT_RESOLUTION:
            resolution_extra = (
                f'\n          <sca:xResolution sca:MustHonor="true">{resolution}</sca:xResolution>'
                f'\n          <sca:yResolution sca:MustHonor="true">{resolution}</sca:yResolution>'
            )
        scanning_side_extra = ""
        if duplex.lower() == "duplex":
            scanning_side_extra = (
                '\n          <sca:ScanningSide sca:MustHonor="true">Duplex</sca:ScanningSide>'
            )

        xml = CREATE_SCAN_JOB_XML.format(
            url=url,
            msgid=make_uuid(),
            format=fmt,
            input_source=input_source,
            content_type=content_type,
            color_mode=color_mode,
            resolution_extra=resolution_extra,
            scanning_side_extra=scanning_side_extra,
            page_width=page_width,
            page_height=page_height,
        )
        resp_bytes = await async_soap_request(
            session, url, xml, step="CreateScanJob"
        )
        jid = re.search(rb"<wscn:JobId>(\d+)</wscn:JobId>", resp_bytes)
        jtok = re.search(rb"<wscn:JobToken>(.*?)</wscn:JobToken>", resp_bytes)
        if not jid or not jtok:
            raise Exception("Failed to create scan job")
        jobid, jobtoken = jid.group(1).decode(), jtok.group(1).decode()

        # 3. Retrieve image(s) as long as the job reports more data
        images: list[bytes] = []
        for _ in range(max_pages):
            xml = RETRIEVE_IMAGE_XML.format(
                url=url, msgid=make_uuid(), jobid=jobid, jobtoken=jobtoken
            )
            resp_bytes = await async_soap_request(
                session, url, xml, step=f"RetrieveImage page {len(images) + 1}"
            )
            images.append(extract_jpeg_from_mtom(resp_bytes))

            # Check job state for "more data available"
            state_m = re.search(rb"<wscn:JobState>(.*?)</wscn:JobState>", resp_bytes)
            reasons_m = re.findall(
                rb"<wscn:JobStateReason>(.*?)</wscn:JobStateReason>", resp_bytes
            )
            job_state = state_m.group(1).decode() if state_m else ""
            reasons = [r.decode().strip() for r in reasons_m]
            # "Completed" with no "MoreDataAvailable" means all pages are done
            if (
                "Completed" in job_state
                and "MoreDataAvailable" not in reasons
            ):
                break
            if job_state in ("Canceled", "Aborted"):
                raise Exception(f"Scan job ended with state {job_state}")

        return images
