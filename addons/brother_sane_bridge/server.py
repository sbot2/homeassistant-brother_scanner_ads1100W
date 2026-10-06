"""Scan bridge HTTP service for the Brother ADS-1100W.

Exposes a tiny stdlib HTTP API that the Home Assistant integration can call to
acquire pages through a remote ``saned``/``brscan4`` backend via
``scanimage -d net:<host>:<device>``. This is what enables duplex on a device
whose WSD service reports ``ADFSupportsDuplex=0`` and that exposes no eSCL
endpoint - and it keeps the Brother driver on the Linux host instead of inside
the immutable HAOS VM.

Endpoints
---------
GET  /health  -> {"ok": true, "device": "...", "listed": bool}
POST /scan    -> body: {"color_mode","resolution","duplex","source","max_pages"}
                 -> {"pages": [<base64 jpeg>...]}

Config
------
Read from ``/data/options.json`` (the HA add-on options mount):
  saned_host          str   e.g. "192.168.178.101"
  saned_device        str   e.g. "brother4:net1;dev0"
  default_color_mode  str   "Color" | "Gray" | "Lineart"
  default_resolution  int   dpi
  port                int
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

OPTIONS_PATH = os.environ.get("OPTIONS_PATH", "/data/options.json")


def load_options() -> dict[str, Any]:
    """Load HA add-on options, falling back to sensible defaults."""
    try:
        with open(OPTIONS_PATH, encoding="utf-8") as f:
            opts = json.load(f) or {}
    except (OSError, ValueError):
        opts = {}
    return {
        "saned_host": str(opts.get("saned_host", "192.168.178.101")),
        "saned_device": str(opts.get("saned_device", "brother4:net1;dev0")),
        "default_color_mode": str(opts.get("default_color_mode", "Color")),
        "default_resolution": int(opts.get("default_resolution", 200)),
        "port": int(opts.get("port", 8661)),
    }


# WSD-style colour tokens (as stored by the integration) -> SANE native modes.
_WSD_TO_SANE_MODE = {
    "blackandwhite1": "Lineart",
    "blackandwhite": "Lineart",
    "grayscale8": "Gray",
    "grayscale": "Gray",
    "rgb24": "Color",
    "color": "Color",
}


def _sane_mode(color_mode: str) -> str:
    """Translate WSD colour tokens, or accept a raw SANE mode name."""
    return _WSD_TO_SANE_MODE.get((color_mode or "").lower(), color_mode)


def _device_string(opts: dict[str, Any]) -> str:
    """Return the full ``net:host:device`` string used with scanimage -d."""
    host = opts["saned_host"]
    dev = opts["saned_device"]
    return f"net:{host}:{dev}"


def _source_for(duplex: bool, requested: Optional[str]) -> str:
    """Pick the ADF source that matches the requested duplex mode.

    Brother's backend requires selecting ``ADF Duplex`` (not just
    ``--duplex=yes``) for double-sided feeds, mirroring the integration.
    """
    if requested:
        return requested
    return "ADF Duplex" if duplex else "ADF Front"


def _scanimage_available() -> Optional[str]:
    return shutil.which("scanimage")


def _list_device(opts: dict[str, Any]) -> bool:
    """Return whether the configured net device appears in ``scanimage -L``."""
    binary = _scanimage_available()
    if not binary:
        return False
    try:
        proc = subprocess.run(
            [binary, "-L"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return False
    dev = opts["saned_device"]
    return any(dev in line for line in out.splitlines())


def _run_scan(
    opts: dict[str, Any],
    *,
    color_mode: str,
    resolution: int,
    duplex: bool,
    source: Optional[str],
    max_pages: int,
) -> list[bytes]:
    """Acquire pages as JPEG blobs via scanimage --batch."""
    binary = _scanimage_available()
    if not binary:
        raise RuntimeError("scanimage is not installed in this add-on")

    device = _device_string(opts)
    src = _source_for(duplex, source)

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            binary,
            "-d", device,
            "--source", src,
            "--mode", _sane_mode(color_mode),
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
            raise RuntimeError(err or "scanimage produced no pages")
        return pages


class ScanHandler(BaseHTTPRequestHandler):
    _opts_cache: tuple[float, dict[str, Any]] = (0.0, {})

    def _opts(self) -> dict[str, Any]:
        # Refresh cached options every 10s so UI changes apply without restart.
        import time
        now = time.time()
        if now - self._opts_cache[0] > 10:
            self._opts_cache = (now, load_options())
        return self._opts_cache[1]

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", ""):
            opts = self._opts()
            self._send(
                200,
                {
                    "ok": True,
                    "device": _device_string(opts),
                    "listed": _list_device(opts),
                },
            )
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/scan":
            length = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                self._send(400, {"error": "invalid JSON"})
                return
            opts = self._opts()
            try:
                pages = _run_scan(
                    opts,
                    color_mode=req.get("color_mode", opts["default_color_mode"]),
                    resolution=int(req.get("resolution", opts["default_resolution"])),
                    duplex=bool(req.get("duplex", False)),
                    source=req.get("source") or None,
                    max_pages=int(req.get("max_pages", 10)),
                )
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"error": str(exc), "pages": []})
                return
            self._send(
                200,
                {
                    "ok": True,
                    "pages": [base64.b64encode(p).decode("ascii") for p in pages],
                },
            )
            return
        self._send(404, {"error": "not found"})

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        import sys
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    opts = load_options()
    port = opts["port"]
    server = ThreadingHTTPServer(("0.0.0.0", port), ScanHandler)
    print(f"Brother SANE scan bridge listening on 0.0.0.0:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
