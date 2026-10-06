import uuid
import asyncio
import logging
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
    DEFAULT_BRIGHTNESS,
    DEFAULT_CONTRAST,
    DEFAULT_DESKEW,
    DEFAULT_ROTATION,
    MAX_PAGES,
)

_LOGGER = logging.getLogger(__name__)


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
          {resolution_extra}{scanning_side_extra}{adjustment_extra}
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

CANCEL_JOB_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:sca="http://schemas.microsoft.com/windows/2006/08/wdp/scan">
  <soap:Header>
    <wsa:To>{url}</wsa:To>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/scan/CancelJob</wsa:Action>
    <wsa:MessageID>urn:uuid:{msgid}</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:From>
      <wsa:Address>urn:uuid:python-client</wsa:Address>
    </wsa:From>
  </soap:Header>
  <soap:Body>
    <sca:CancelJobRequest>
      <sca:JobId>{jobid}</sca:JobId>
      <sca:JobToken>{jobtoken}</sca:JobToken>
    </sca:CancelJobRequest>
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
        _LOGGER.debug("Scanner state response for %s:\n%s", ip, text)
        return {
            "state": _extract(text, r"<wscn:ScannerState>(.*?)</wscn:ScannerState>"),
            "state_reason": _extract(
                text, r"<wscn:ScannerStateReason>(.*?)</wscn:ScannerStateReason>"
            ),
            "adf_state": _extract(
                text, r"<wscn:(?:AdfState|AutoDocumentFeederState)>(.*?)</wscn:(?:AdfState|AutoDocumentFeederState)>"
            ),
            "raw": text,
        }


def _extract(text: str, pattern: str) -> str:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else "Unknown"


def _extract_all(text: str, pattern: str) -> list[str]:
    """Return all non-empty, deduplicated matches for a regex pattern."""
    seen = []
    for m in re.findall(pattern, text):
        val = m.strip()
        if val and val not in seen:
            seen.append(val)
    return seen


# Maps the values a device advertises in <wscn:ADFColor> to the standard WSD
# color-mode tokens used in <sca:ColorMode>. Some Brother devices report e.g.
# "Grayscale8" while the plugin historically used "Gray8"; normalise so we
# always send a value the scanner understands.
COLOR_MODE_ALIASES = {
    "Grayscale8": "Grayscale8",
    "Gray8": "Grayscale8",
    "GrayScale8": "Grayscale8",
    "Grayscale16": "Grayscale16",
    "Gray16": "Grayscale16",
    "RGB24": "RGB24",
    "RGB48": "RGB48",
    "BlackAndWhite1": "BlackAndWhite1",
}


async def get_scanner_capabilities(ip: str) -> dict:
    """Query the scanner's advertised capabilities (description + configuration).

    Returns a dict with the color modes, resolutions, duplex support and max
    document size the device actually advertises. Values are extracted safely and
    fall back to the module defaults if the device does not expose them, so a
    capability probe failure never breaks configuration.
    """
    from .const import (
        MODEL,
        COLOR_MODES,
        RESOLUTIONS,
        DUPLEX_VALUES,
        DEFAULT_PAGE_WIDTH,
        DEFAULT_PAGE_HEIGHT,
    )

    url = f"http://{ip}/WebServices/ScannerService"
    # Build a request for the elements we care about (mirrors the known-good
    # request but asks for description + configuration too).
    desc_config_names = (
        "ScannerStatus",
        "ScannerElements",
        "AutoDocumentFeederStatus",
        "ScannerDescription",
        "ScannerConfiguration",
    )
    options = "\n".join(
        f'        <sca:Name>sca:{n}</sca:Name>' for n in desc_config_names
    )
    xml = """<?xml version="1.0" encoding="utf-8"?>
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
{options}
      </sca:RequestedElements>
    </sca:GetScannerElementsRequest>
  </soap:Body>
</soap:Envelope>
""".format(url=url, msgid=make_uuid(), fromid=make_uuid(), options=options)

    async with aiohttp.ClientSession() as session:
        try:
            resp_bytes = await async_soap_request(
                session, url, xml, step="GetScannerElements(capabilities)"
            )
        except aiohttp.ClientResponseError:
            # Fall back to the minimal status-only request; not fatal.
            resp_bytes = await async_soap_request(
                session, url, SCANNER_STATUS_ONLY_XML.format(
                    url=url, msgid=make_uuid(), fromid=make_uuid()
                ),
                step="GetScannerElements(status)",
            )
    text = resp_bytes.decode("utf-8", errors="ignore")
    _LOGGER.debug("Scanner capabilities response for %s:\n%s", ip, text)

    # Model name from ScannerDescription (fallback to configured MODEL)
    model_match = re.search(
        r"<wscn:ScannerName[^>]*>(.*?)</wscn:ScannerName>", text, re.DOTALL
    )
    advertised_model = model_match.group(1).strip() if model_match else None

    # Advertised colour modes (normalised to standard WSD tokens)
    advertised_colors = _extract_all(text, r"<wscn:ColorEntry>(.*?)</wscn:ColorEntry>")
    color_modes = [
        COLOR_MODE_ALIASES.get(raw, raw) for raw in advertised_colors
    ]
    if not color_modes:
        color_modes = list(COLOR_MODES)

    # ADF resolutions (device reports widths and heights under <wscn:ADFResolutions>).
    # The ScannerConfiguration also contains an <wscn:ADFOpticalResolution> with
    # width/height, so we must scope the extraction to ADFResolutions only.
    resolutions: list[int] = []
    for block in re.findall(
        r"<wscn:ADFResolutions>(.*?)</wscn:ADFResolutions>", text, re.DOTALL
    ):
        for w in re.findall(r"<wscn:Width>(\d+)</wscn:Width>", block):
            val = int(w)
            if val not in resolutions:
                resolutions.append(val)
    if not resolutions:
        resolutions = list(RESOLUTIONS)

    # Duplex support
    duplex_supported = (
        re.search(r"<wscn:ADFSupportsDuplex>(\d+)</wscn:ADFSupportsDuplex>", text)
    )
    if duplex_supported:
        duplex_values = ["None", "Duplex"] if duplex_supported.group(1) == "1" else ["None"]
    else:
        duplex_values = list(DUPLEX_VALUES)

    duplex_ok = "Duplex" in duplex_values

    # Rotation support. The WSD RotationValue is expressed in degrees; a device
    # that only reports 0 does not support rotating the scanned image.
    rotation_values = _extract_all(text, r"<wscn:RotationValue>(\d+)</wscn:RotationValue>")
    if rotation_values and rotation_values == ["0"]:
        rotations = ["None"]
    else:
        rotations = ["None", "Rotate90", "Rotate180", "Rotate270"]

    # Max document size (media size in thousandths of an inch)
    max_width = int(m.group(1)) if (m := re.search(
        r"<wscn:ADFMaximumSize>\s*<wscn:Width>(\d+)</wscn:Width>", text
    )) else DEFAULT_PAGE_WIDTH
    max_height = int(m.group(1)) if (m := re.search(
        r"<wscn:ADFMaximumSize>.*?<wscn:Height>(\d+)</wscn:Height>", text, re.DOTALL
    )) else DEFAULT_PAGE_HEIGHT

    # Brightness/contrast capability (both reported as 1 on the ADS-1100W).
    brightness_supported = (
        re.search(r"<wscn:BrightnessSupported>(\d+)</wscn:BrightnessSupported>", text)
    )
    contrast_supported = (
        re.search(r"<wscn:ContrastSupported>(\d+)</wscn:ContrastSupported>", text)
    )

    return {
        "model": advertised_model or MODEL,
        "color_modes": color_modes,
        "resolutions": resolutions,
        "duplex": duplex_values,
        "duplex_supported": duplex_ok,
        "rotations": rotations,
        "brightness_supported": bool(
            brightness_supported and brightness_supported.group(1) == "1"
        ),
        "contrast_supported": bool(
            contrast_supported and contrast_supported.group(1) == "1"
        ),
        "max_width": max_width,
        "max_height": max_height,
    }


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
    brightness: int = DEFAULT_BRIGHTNESS,
    contrast: int = DEFAULT_CONTRAST,
    deskew: bool = DEFAULT_DESKEW,
    rotation: str = DEFAULT_ROTATION,
    on_job_start=None,
) -> list[bytes]:
    """Scan one or more pages (ADF) from a Brother scanner.

    Returns a list of JPEG bytes, one per scanned page.

    ``on_job_start(jobid, jobtoken)`` is called (if provided) as soon as the
    scan job has been created, allowing callers to later cancel it.
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
        # The resolution, scanning-side and image-adjustment fields are optional:
        # they are only added when they differ from the defaults, to stay
        # compatible with devices that reject them (which would otherwise cause
        # a 400 on RetrieveImage).
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

        adjustment_extra = ""
        if brightness != DEFAULT_BRIGHTNESS:
            adjustment_extra += (
                f'\n          <sca:Brightness sca:MustHonor="true">{brightness}</sca:Brightness>'
            )
        if contrast != DEFAULT_CONTRAST:
            adjustment_extra += (
                f'\n          <sca:Contrast sca:MustHonor="true">{contrast}</sca:Contrast>'
            )
        if deskew:
            adjustment_extra += '\n          <sca:Deskew sca:MustHonor="true">true</sca:Deskew>'
        if rotation.lower() not in ("none", ""):
            adjustment_extra += (
                f'\n          <sca:Rotation sca:MustHonor="true">{rotation}</sca:Rotation>'
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
            adjustment_extra=adjustment_extra,
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

        if on_job_start is not None:
            on_job_start(jobid, jobtoken)

        # 3. Retrieve image(s) as long as the job reports more data
        images: list[bytes] = []
        for _ in range(max_pages):
            xml = RETRIEVE_IMAGE_XML.format(
                url=url, msgid=make_uuid(), jobid=jobid, jobtoken=jobtoken
            )
            try:
                resp_bytes = await async_soap_request(
                    session, url, xml, step=f"RetrieveImage page {len(images) + 1}"
                )
            except aiohttp.ClientResponseError as e:
                # If we already retrieved at least one page, a failure on the
                # next RetrieveImage simply means there are no more pages (the
                # scanner signals "end of document" with a fault instead of a
                # clean response). Treat it as a normal completion.
                if images:
                    _LOGGER.debug(
                        "Scanner reported end of document after %d page(s): %s",
                        len(images),
                        e,
                    )
                    break
                raise
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


async def cancel_scan_job(ip: str, jobid: str, jobtoken: str) -> None:
    """Cancel an in-progress scan job on the scanner (WSD CancelJob)."""
    url = f"http://{ip}/WebServices/ScannerService"
    xml = CANCEL_JOB_XML.format(url=url, msgid=make_uuid(), jobid=jobid, jobtoken=jobtoken)
    async with aiohttp.ClientSession() as session:
        await async_soap_request(session, url, xml, step="CancelJob")
