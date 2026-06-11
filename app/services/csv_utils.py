"""Helpers voor CSV-exports."""


def csv_safe(value: str | None) -> str:
    """Neutraliseer formule-injectie in spreadsheets (cellen die met =, +, - of @ beginnen)."""
    if not value:
        return ""
    return f"'{value}" if value[0] in "=+-@" else value
