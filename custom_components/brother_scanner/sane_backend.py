"""SANE-backed acquisition for Brother network scanners.

The ADS-1100W does NOT expose eSCL/AirScan (confirmed via mDNS: it advertises
only ``_scanner._tcp`` = WSD and has no ``_uscan._tcp`` record), and its WSD
Scan Service reports ``ADFSupportsDuplex=0``. The only protocol that honours
duplex on this device is Brother's proprietary one, exposed on Linux through
the SANE ``brother4``/``brscan4`` backend.

Rather than hard-depend on that stack (which is unavailable on Windows or in
many Home Assistant add-on images), this module talks to the system ``scanimage``
CLI at runtime and *gracefully reports "not available"* when neither the binary
nor a Brother device is present. The rest of the integration keeps its WSD path
as the automatic fallback, so nothing regresses when SANE is missing.

The module is deliberately synchronous (blocking subprocess calls): callers are
expected to wrap it via ``hass.async_add_executor_job`` / a worker thread.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)

# Common scanimage device strings for Brother network scanners. ``scanimage -L``
# returns one line per device; Brother devices look like:
#   device `brother4:net1;dev0' is a Brother ADS-1100W ... network scanner
_DEVICE_RE = re.compile(
    r"device `(?P<dev>[^']+)'\s+is a .*?(?P<model>ADS-[\w-]+).*?scanner",
    re.IGNORECASE,
)

# SANE colour-mode names -> WSD-style tokens used elsewhere in the integration.
_MODE_ALIASES = {
    "black & white": "BlackAndWhite1",
    "black and white": "BlackAndWhite1",
    "lineart": "BlackAndWhite1",
    "gray": "Grayscale8",
    "grayscale": "Grayscale8",
    "color": "RGB24",
}

# Reverse: WSD-style tokens stored by the options flow -> SANE native mode names.
_WSD_TO_SANE_MODE = {
    "blackandwhite1": "Lineart",
    "blackandwhite": "Lineart",
    "grayscale8": "Gray",
    "grayscale": "Gray",
    "rgb24": "Color",
    "color": "Color",
}


def _sane_mode_name(color_mode: str) -> str:
    """Translate a stored WSD-style colour-mode token to a SANE native mode name."""
    return _WSD_TO_SANE_MODE.get((color_mode or "").lower(), color_mode)


def scanimage_path() -> Optional[str]:
    """Return the path to ``scanimage``, or None if it is not installed."""
    return shutil.which("scanimage")


def _run(cmd: list[str]) -> tuple[str, str]:
    """Run a command and return (stdout, stderr) without raising on exit code."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        err = proc.stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            _LOGGER.debug("Command %s exited %d: %s", cmd, proc.returncode, err)
        return out, err
    except FileNotFoundError:
        return "", "scanimage not found"
    except subprocess.TimeoutExpired:
        return "", "scanimage timed out"


def list_brother_devices() -> list[dict[str, str]]:
    """Return a list of Brother scanner devices found via ``scanimage -L``.

    Each entry: {"device": <backend:...>, "model": <model> | ""}.
    Returns [] when SANE/the binary or any Brother device is unavailable.
    """
    binary = scanimage_path()
    if not binary:
        return []
    out, err = _run([binary, "-L"])
    devices: list[dict[str, str]] = []
    for line in out.splitlines():
        m = _DEVICE_RE.search(line)
        if m:
            devices.append(
                {
                    "device": m.group("dev"),
                    "model": m.group("model").strip(),
                }
            )
    if not devices and err:
        _LOGGER.debug("scanimage -L produced no Brother devices: %s", err.strip())
    return devices


def _parse_resolutions(text: str) -> list[int]:
    """Parse a resolution constraint like '25..1200dpi' or '100,200,300dpi' or '100dpi'."""
    text = text.strip().lower()
    numbers = [int(x) for x in re.findall(r"\d+", text)]
    if not numbers:
        return []
    # A range (a..b) -> step through common DPI ladder; a list -> as-is.
    if ".." in text and len(numbers) >= 2:
        lo, hi = numbers[0], numbers[1]
        step = 25 if hi - lo > 400 else (50 if hi - lo > 200 else 25)
        return list(range(lo, hi + 1, step))
    return numbers


def probe_capabilities(device: Optional[str] = None) -> dict[str, Any]:
    """Probe a Brother scanner's real options via ``scanimage -A``.

    Returns a dict keyed like the integration's ``capabilities`` blob:
      {
        "model": <model> | "",
        "color_modes": [...],   # WSD-style tokens scoped to the ADF source
        "resolutions": [...],
        "duplex": bool,
        "sources": [...],       # raw SANE source names (Flatbed/ADF/...)
      }
    """
    binary = scanimage_path()
    if not binary:
        return {}
    devices = list_brother_devices()
    if not devices:
        return {}
    target = device or devices[0]["device"]

    out, err = _run([binary, "-A", "-d", target])

    sources: list[str] = []
    modes: list[str] = []
    resolutions: list[int] = []
    duplex = False

    def _clean_list(val: str) -> list[str]:
        """Split a `|`-separated option value and strip any `[default]` annotations."""
        out = []
        for item in val.split("|"):
            item = re.sub(r"\s*\[.*?\]\s*$", "", item).strip()
            if item:
                out.append(item)
        return out

    for line in out.splitlines():
        stripped = line.strip()
        low = stripped.lower()

        # --- source list ---
        # Forms: "Source: A|B" or "--source A|B [A]"
        if low.startswith("source:") or low.startswith("--source"):
            if low.startswith("source:"):
                val = stripped.split(":", 1)[1].strip()
            else:
                m = re.search(r"--source\s+([^;]+)", stripped)
                val = m.group(1).strip() if m else ""
            if val:
                sources = _clean_list(val)
            continue

        # --- colour/mode list ---
        # Forms: "Mode: Lineart|Gray|Color" or "--mode Lineart|Gray|Color [Color]"
        if low.startswith("mode:") or low.startswith("--mode"):
            if low.startswith("mode:"):
                val = stripped.split(":", 1)[1].strip()
            else:
                m = re.search(r"--mode\s+([^;]+)", stripped)
                val = m.group(1).strip() if m else ""
            raw_modes = _clean_list(val)
            modes = []
            for m in raw_modes:
                key = m.lower()
                modes.append(_MODE_ALIASES.get(key, m))
            continue

        # --- resolution ---
        # Forms: "Resolution: 100..1200dpi" or "--resolution 100..1200dpi [200]"
        if low.startswith("resolution:") or low.startswith("--resolution"):
            if low.startswith("resolution:"):
                val = stripped.split(":", 1)[1].strip()
            else:
                m = re.search(r"--resolution\s+([^;]+)", stripped)
                val = m.group(1).strip() if m else ""
            val = re.sub(r"\s*\[.*?\]\s*$", "", val)
            resolutions = _parse_resolutions(val)
            continue

        # --- duplex ---
        # Forms: "Duplex: yes|no [no]" or "--duplex=yes|no [no]" or "Duplex: no"
        if low.startswith("duplex:") or low.startswith("--duplex"):
            if low.startswith("--duplex"):
                m = re.search(r"--duplex[=:]?\s*([^;]+)", stripped)
                val = m.group(1).strip() if m else ""
            else:
                val = stripped.split(":", 1)[1].strip()
            vlow = (val or "").lower()
            has_yes = any(w in vlow for w in ("yes", "true", "on", "1"))
            has_no = any(w in vlow for w in ("no", "false", "off", "0", "none"))
            # A selector that includes "yes" supports duplex; a pure "no"/"off"
            # (or absent) does not.
            duplex = has_yes and not (has_no and not has_yes)
            if has_yes and has_no:
                duplex = True
            continue

    if not modes and not resolutions and not sources and not duplex and err:
        _LOGGER.debug("scanimage -A produced no options: %s", err.strip())

    # For the ADF sheet feed, prefer ADF-relevant sources.
    adf_sources = [s for s in sources if "adf" in s.lower()]
    chosen_source = adf_sources[0] if adf_sources else (sources[0] if sources else "ADF")

    model = ""
    for d in devices:
        if d["device"] == target:
            model = d["model"]
            break

    return {
        "model": model,
        "color_modes": modes or None,
        "resolutions": resolutions or None,
        "duplex": duplex,
        "sources": sources,
        "source": chosen_source,
    }


def scan(
    device: str,
    *,
    source: str = "ADF",

    color_mode: str = "RGB24",
    resolution: int = 200,
    duplex: bool = False,
    max_pages: int = 10,
) -> list[bytes]:
    """Acquire scanned pages over SANE and return a list of JPEG byte blobs.

    Uses ``scanimage --batch`` to a temporary directory, which reliably handles
    both single-page and multi-page ADF feeds. Each produced ``pageN.jpg`` is
    read back in order and added to the returned list.
    """
    binary = scanimage_path()
    if not binary:
        raise RuntimeError("scanimage is not installed on this host")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            binary,
            "-d", device,
            "--source", source,
            "--mode", _sane_mode_name(color_mode),
            "--resolution", str(resolution),
            "--format", "jpeg",
            "--batch", f"{tmpdir}/page%d.jpg",
            "--batch-count", str(max_pages),
        ]
        if duplex:
            cmd.append("--duplex=yes")

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )

        pages: list[bytes] = []
        idx = 1
        while True:
            path = f"{tmpdir}/page{idx}.jpg"
            try:
                with open(path, "rb") as f:
                    pages.append(f.read())
            except FileNotFoundError:
                break
            idx += 1

        if not pages:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"scanimage produced no pages: {err}")

        if proc.returncode != 0:
            _LOGGER.debug("scanimage exited %d but produced %d page(s)", proc.returncode, len(pages))
        return pages


# ---------------------------------------------------------------------------
# SANE bridge (HTTP) transport
#
# When Home Assistant runs in an immutable HAOS VM, `scanimage` and the Brother
# driver live in a separate add-on container (or on a remote Linux host) that
# exposes a tiny HTTP scan bridge. Reaching it means the integration does not
# itself need the SANE client or the proprietary backend installed.
# ---------------------------------------------------------------------------


async def check_bridge(url: str, *, timeout: float = 5.0) -> dict:
    """Probe a SANE bridge's ``/health`` endpoint.

    Returns ``{"available": bool, "device": str|None, "listed": bool}``. Never
    raises; a failed/unreachable bridge simply reports ``available: False``.
    """
    import aiohttp

    base = url.rstrip("/")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base}/health", timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    return {"available": False, "device": None, "listed": False}
                data = await resp.json()
        return {
            "available": bool(data.get("ok")),
            "device": data.get("device"),
            "listed": bool(data.get("listed")),
        }
    except Exception as e:  # noqa: BLE001
        _LOGGER.debug("SANE bridge health check failed for %s: %s", base, e)
        return {"available": False, "device": None, "listed": False}


async def async_scan_via_http(
    url: str,
    *,
    color_mode: str = "RGB24",
    resolution: int = 200,
    duplex: bool = False,
    max_pages: int = 10,
    timeout: float = 320.0,
) -> list[bytes]:
    """Acquire pages through a SANE bridge over HTTP; return JPEG byte blobs.

    Mirrors the local :func:`scan` contract so the integration can dispatch to
    either transport transparently. The WSD-style colour token is translated to
    a SANE native mode here (consistent with the local path), and the ADF source
    for duplex is left to the bridge (it derives ``ADF Duplex`` from ``duplex``).
    """
    import aiohttp
    import base64

    base = url.rstrip("/")
    payload = {
        "duplex": bool(duplex),
        "color_mode": _sane_mode_name(color_mode),
        "resolution": int(resolution),
        "max_pages": int(max_pages),
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base}/scan",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                status = resp.status
                data = await resp.json()
    except aiohttp.ClientError as e:
        raise RuntimeError(f"SANE bridge unreachable at {base}: {e}") from e

    if not isinstance(data, dict) or not data.get("ok"):
        error = (data or {}).get("error") if isinstance(data, dict) else None
        raise RuntimeError(error or f"SANE bridge scan failed (HTTP {status})")

    pages = data.get("pages") or []
    if not pages:
        raise RuntimeError("SANE bridge returned no pages")
    try:
        return [base64.b64decode(p) for p in pages]
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"SANE bridge returned malformed page data: {e}") from e


