"""Normalize scanned serial numbers.

The Lenovo ThinkBooks carry two scannable codes on the bottom label:

- a service QR code: ``https://support.lenovo.com/qrcode?sn=PW0P8KG5&mtm=21MVS04B00``
- a 20-character barcode that starts with the 8-character serial:
  ``PW0P8KG5PW90B6321007``

Both are reduced to the bare serial (``PW0P8KG5``). Keep in sync with
``static/js/serial.js``.
"""
import re
from urllib.parse import parse_qs, urlsplit

_LENOVO_LONG_BARCODE = re.compile(r"^P[A-Z0-9]{19}$")
_LENOVO_SERIAL_LENGTH = 8


def normalize_serial(raw: str | None) -> str:
    """Return the serial number contained in a scan, uppercased and trimmed."""
    value = (raw or "").strip()
    if not value:
        return ""

    if "sn=" in value.lower():
        query = urlsplit(value).query or value.split("?", 1)[-1]
        params = {k.lower(): v for k, v in parse_qs(query).items()}
        if params.get("sn") and params["sn"][0].strip():
            value = params["sn"][0].strip()

    value = value.upper()
    if _LENOVO_LONG_BARCODE.match(value):
        value = value[:_LENOVO_SERIAL_LENGTH]
    return value
