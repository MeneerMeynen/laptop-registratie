// Reduce a scanned code to the bare serial number. Mirrors
// app/services/serial_utils.py::normalize_serial — keep both in sync.
//   https://support.lenovo.com/qrcode?sn=PW0P8KG5&mtm=21MVS04B00 → PW0P8KG5
//   pW0P8KG5PW90B6321007                                      → PW0P8KG5
function normalizeSerial(raw) {
  let value = (raw || '').trim();
  if (!value) return '';

  if (/sn=/i.test(value)) {
    const query = value.includes('?') ? value.split('?').slice(1).join('?') : value;
    for (const [key, val] of new URLSearchParams(query)) {
      if (key.toLowerCase() === 'sn' && val.trim()) { value = val.trim(); break; }
    }
  }

  value = value.toUpperCase();
  if (/^P[A-Z0-9]{19}$/.test(value)) value = value.slice(0, 8);
  return value;
}

// For fields that also accept names: only rewrite values that are clearly a
// Lenovo scan (QR URL or long barcode); anything else is returned trimmed.
function scannedSerial(raw) {
  const value = (raw || '').trim();
  return (/sn=/i.test(value) || /^P[A-Z0-9]{19}$/i.test(value)) ? normalizeSerial(value) : value;
}
