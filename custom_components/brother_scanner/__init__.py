import voluptuous as vol
import asyncio
import logging
import datetime
import os
from homeassistant.exceptions import HomeAssistantError
from .const import (
    DOMAIN,
    SCANS_DIR,
    CONF_COLOR_MODE,
    CONF_RESOLUTION,
    CONF_DUPLEX,
    CONF_OUTPUT_FORMAT,
    CONF_OCR,
    CONF_BRIGHTNESS,
    CONF_CONTRAST,
    CONF_DESKEW,
    CONF_ROTATION,
    TESSERACT_CMD,
    DEFAULT_COLOR_MODE,
    DEFAULT_RESOLUTION,
    DEFAULT_DUPLEX,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OCR,
    DEFAULT_BRIGHTNESS,
    DEFAULT_CONTRAST,
    DEFAULT_DESKEW,
    DEFAULT_ROTATION,
    MAX_PAGES,
    SERVICE_SNAPSHOT,
    SERVICE_CANCEL_SCAN,
)
from .api import scan_jpeg, cancel_scan_job
from .diagnostics import (
    load_diagnostics,
    save_diagnostics,
    save_last_snapshot,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Set up Brother scanner from a config entry."""
    ip = entry.data["ip"]
    entry_id = entry.entry_id

    # Store IP and per-device lock
    hass.data.setdefault(DOMAIN, {})[entry_id] = {
        "ip": ip,
        "lock": asyncio.Lock(),
        "current_job": None,
        "entities": [],
        "entry_id": entry_id,
        "options": _entry_options(entry),
    }

    # Forward entities to HA
    await hass.config_entries.async_forward_entry_setups(
        entry, ["button", "camera", "sensor"]
    )

    # Reload the integration when options are updated (e.g. via options flow)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    # Register snapshot service once
    if not hass.services.has_service(DOMAIN, SERVICE_SNAPSHOT):

        async def snapshot_service_wrapper(call):
            await snapshot_service(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SNAPSHOT,
            snapshot_service_wrapper,
            schema=vol.Schema(
                {
                    vol.Required("ip"): str,
                    vol.Optional("filename"): str,
                    vol.Optional(CONF_COLOR_MODE): str,
                    vol.Optional(CONF_RESOLUTION): vol.Coerce(int),
                    vol.Optional(CONF_DUPLEX): str,
                    vol.Optional(CONF_OUTPUT_FORMAT): str,
                    vol.Optional(CONF_OCR): bool,
                    vol.Optional(CONF_BRIGHTNESS): vol.Coerce(int),
                    vol.Optional(CONF_CONTRAST): vol.Coerce(int),
                    vol.Optional(CONF_DESKEW): bool,
                    vol.Optional(CONF_ROTATION): str,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        )

    # Register cancel-scan service once
    if not hass.services.has_service(DOMAIN, SERVICE_CANCEL_SCAN):

        async def cancel_service_wrapper(call):
            await cancel_service(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_CANCEL_SCAN,
            cancel_service_wrapper,
            schema=vol.Schema({vol.Required("ip"): str}),
        )

    return True


def _entry_options(entry) -> dict:
    """Return effective scan options for an entry (options over defaults)."""
    opts = entry.options or {}
    return {
        CONF_COLOR_MODE: opts.get(CONF_COLOR_MODE, DEFAULT_COLOR_MODE),
        CONF_RESOLUTION: int(opts.get(CONF_RESOLUTION, DEFAULT_RESOLUTION)),
        CONF_DUPLEX: opts.get(CONF_DUPLEX, DEFAULT_DUPLEX),
        CONF_OUTPUT_FORMAT: opts.get(CONF_OUTPUT_FORMAT, DEFAULT_OUTPUT_FORMAT),
        CONF_OCR: bool(opts.get(CONF_OCR, DEFAULT_OCR)),
        CONF_BRIGHTNESS: int(opts.get(CONF_BRIGHTNESS, DEFAULT_BRIGHTNESS)),
        CONF_CONTRAST: int(opts.get(CONF_CONTRAST, DEFAULT_CONTRAST)),
        CONF_DESKEW: bool(opts.get(CONF_DESKEW, DEFAULT_DESKEW)),
        CONF_ROTATION: opts.get(CONF_ROTATION, DEFAULT_ROTATION),
    }


async def _refresh_options(hass, entry_id):
    """Reload stored options for an entry (called from the options flow)."""
    entry = next(
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id == entry_id
    )
    hass.data[DOMAIN][entry_id]["options"] = _entry_options(entry)
    # Re-create diagnosed entities data remains in place; coordinator picks it up.


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "button")
    await hass.config_entries.async_forward_entry_unload(entry, "camera")
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


async def _async_reload_entry(hass, entry):
    """Reload the config entry after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def snapshot_service(hass, call):
    ip = call.data["ip"]
    filename = call.data.get("filename")

    # Find device by IP
    device_data = next((d for d in hass.data[DOMAIN].values() if d["ip"] == ip), None)
    if not device_data:
        raise HomeAssistantError(f"Device {ip} not found")

    lock = device_data["lock"]
    entry_id = device_data["entry_id"]
    options = dict(device_data["options"])
    # Allow per-call overrides
    for key in (
        CONF_COLOR_MODE,
        CONF_RESOLUTION,
        CONF_DUPLEX,
        CONF_OUTPUT_FORMAT,
        CONF_OCR,
        CONF_BRIGHTNESS,
        CONF_CONTRAST,
        CONF_DESKEW,
        CONF_ROTATION,
    ):
        if key in call.data:
            options[key] = call.data[key]

    if lock.locked():
        _LOGGER.warning("Snapshot already running for %s, skipping call", ip)
        return

    async with lock:
        try:
            # Expose the created job (if any) so cancel_scan can abort it
            current_job = {"jobid": None, "jobtoken": None}

            def _on_job_start(jobid, jobtoken):
                current_job["jobid"] = jobid
                current_job["jobtoken"] = jobtoken
                device_data["current_job"] = current_job

            try:
                images = await scan_jpeg(
                    ip,
                    max_pages=MAX_PAGES,
                    color_mode=options[CONF_COLOR_MODE],
                    resolution=options[CONF_RESOLUTION],
                    duplex=options[CONF_DUPLEX],
                    brightness=options[CONF_BRIGHTNESS],
                    contrast=options[CONF_CONTRAST],
                    deskew=options[CONF_DESKEW],
                    rotation=options[CONF_ROTATION],
                    on_job_start=_on_job_start,
                )
            finally:
                # The scan is no longer active; clear the cancel target.
                device_data["current_job"] = None

            saved_paths = await _save_scan(
                hass, ip, entry_id, images, filename, options
            )

            # Persist diagnostics
            diag = await load_diagnostics(hass, entry_id)
            diag["pages_scanned"] = int(diag.get("pages_scanned", 0)) + len(images)
            diag["last_scan"] = datetime.datetime.now().astimezone().isoformat()
            diag["last_pages"] = len(images)
            await save_diagnostics(hass, entry_id, diag)

            # Save last snapshot path (first/last page for camera) to storage
            await save_last_snapshot(hass, entry_id, saved_paths[-1])

            hass.bus.async_fire(
                f"{DOMAIN}_snapshot_saved",
                {"ip": ip, "filename": saved_paths[-1], "pages": saved_paths},
            )

            # Refresh diagnose sensors immediately
            coordinator = hass.data[DOMAIN][entry_id].get("coordinator")
            if coordinator:
                await coordinator.async_request_refresh()

        except OSError as e:
            _LOGGER.error("Failed to save snapshot for %s: %s", ip, e)
            raise HomeAssistantError(f"Failed to save snapshot: {e}")
        except Exception as e:
            _LOGGER.error(
                "Unexpected error during snapshot for %s: %s",
                ip,
                e,
                exc_info=True,
            )
            raise HomeAssistantError(f"Unexpected error: {e}") from e


async def cancel_service(hass, call):
    """Cancel the currently running scan job for a device."""
    ip = call.data["ip"]
    device_data = next((d for d in hass.data[DOMAIN].values() if d["ip"] == ip), None)
    if not device_data:
        raise HomeAssistantError(f"Device {ip} not found")

    current_job = device_data.get("current_job")
    if not current_job or not current_job.get("jobid"):
        _LOGGER.info("No active scan job for %s to cancel", ip)
        return

    await cancel_scan_job(
        ip, current_job["jobid"], current_job.get("jobtoken", "")
    )
    _LOGGER.info("Cancelled scan job %s for %s", current_job["jobid"], ip)


async def _save_scan(hass, ip, entry_id, images, filename, options) -> list:
    """Save scanned pages, produce PDF and optional OCR, return list of saved paths."""
    saved_paths = []

    async def write_file(path, data):
        def _w():
            with open(path, "wb") as f:
                f.write(data)

        await hass.async_add_executor_job(_w)
        saved_paths.append(path)

    base_path = _resolve_filename(hass, ip, filename)
    os.makedirs(os.path.dirname(base_path), exist_ok=True)

    if options[CONF_OUTPUT_FORMAT] == "pdf":
        pdf_path = base_path
        if not pdf_path.lower().endswith(".pdf"):
            pdf_path = f"{pdf_path}.pdf"
        await _write_pdf(hass, images, pdf_path)
        saved_paths.append(pdf_path)
    else:
        multi = len(images) > 1
        for idx, jpeg_bytes in enumerate(images):
            path = base_path
            if multi:
                stem, ext = os.path.splitext(base_path)
                path = f"{stem}_p{idx + 1}{ext or '.jpg'}"
            elif not path.lower().endswith(".jpg"):
                path = f"{path}.jpg"
            await write_file(path, jpeg_bytes)
            _LOGGER.info("Snapshot saved: %s", path)

    if options[CONF_OCR]:
        await _run_ocr(hass, saved_paths)

    return saved_paths


def _resolve_filename(hass, ip, filename):
    """Return the absolute path to save the scan to."""
    if filename:
        if os.path.isabs(filename):
            return filename
        return hass.config.path("www", filename)
    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return hass.config.path("www", f"{SCANS_DIR}/{ip}_{now}")


async def _write_pdf(hass, images, pdf_path):
    """Combine JPEG pages into a single PDF using img2pdf (lossless)."""
    import img2pdf

    temp_files = []

    def _w():
        for i, data in enumerate(images):
            tmp = f"{pdf_path}.tmp_{i}.jpg"
            with open(tmp, "wb") as f:
                f.write(data)
            temp_files.append(tmp)
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(temp_files))

    try:
        await hass.async_add_executor_job(_w)
    finally:
        for tmp in temp_files:
            try:
                os.remove(tmp)
            except OSError:
                pass


async def _run_ocr(hass, saved_paths):
    """Optionally run OCR on scanned pages. Silently skips if tesseract is missing."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        _LOGGER.warning("OCR enabled but pytesseract not installed; skipping")
        return

    for path in saved_paths:
        if not path.lower().endswith((".jpg", ".jpeg", ".png")):
            _LOGGER.debug("Skipping OCR for non-image file: %s", path)
            continue
        try:
            out_path = f"{os.path.splitext(path)[0]}.txt"

            def _ocr(p=path, o=out_path):
                pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
                text = pytesseract.image_to_string(Image.open(p))
                with open(o, "w", encoding="utf-8") as f:
                    f.write(text)
                return o

            out = await hass.async_add_executor_job(_ocr)
            _LOGGER.info("OCR text saved: %s", out)
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("OCR failed for %s: %s", path, e)
