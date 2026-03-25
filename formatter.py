from __future__ import annotations
import math


# ---------------------------------------------------------------------------
# Number formatting — Indian system
# ---------------------------------------------------------------------------

def _apply_indian_commas(n: int) -> str:
    """
    Applies Indian comma grouping:
      Last 3 digits form the rightmost group, then groups of 2 from the right.
      12345 → "12,345"   |   1234567 → "12,34,567"
    """
    s = str(abs(n))
    if len(s) <= 3:
        return s
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return result


def format_indian(value: float | int | None, prefix: str = "") -> str:
    """
    Formats a number using the Indian number system.

      None          → "N/A"
      < 1,000       → "847"
      1,000–99,999  → "12,345"
      1,00,000–     → "4.87L"
      ≥ 1,00,00,000 → "₹4.02 Cr"  (prefix always prepended for crore)

    The `prefix` argument (e.g. "₹") is prepended for values that don't
    already include a suffix (i.e. < crore range).
    """
    if value is None:
        return "N/A"

    n = float(value)
    negative = n < 0
    abs_n = abs(n)

    if abs_n >= 1_00_00_000:  # 1 crore
        formatted = f"₹{abs_n / 1_00_00_000:.2f} Cr"
    elif abs_n >= 1_00_000:   # 1 lakh
        formatted = f"{abs_n / 1_00_000:.2f}L"
    elif abs_n >= 1_000:
        formatted = _apply_indian_commas(int(round(abs_n)))
    else:
        formatted = str(int(round(abs_n)))
        if abs_n != int(abs_n):
            formatted = f"{abs_n:.0f}"

    if abs_n < 1_00_00_000 and prefix:
        formatted = prefix + formatted

    return ("-" if negative else "") + formatted


def format_currency(value: float | None) -> str:
    """For Revenue-per-Stream: always ₹X.XX format."""
    if value is None:
        return "N/A"
    return f"₹{value:.2f}"


def format_revenue(value: float | None) -> str:
    """For total revenue: uses crore/lakh formatting with ₹ prefix."""
    return format_indian(value, prefix="₹")


# ---------------------------------------------------------------------------
# Delta badge
# ---------------------------------------------------------------------------

def format_delta(
    current: float | None,
    previous: float | None,
    inverted: bool = False,
) -> dict:
    """
    Returns a dict describing how to render the delta badge:
      {
        "arrow":   "▲" | "▼" | "–",
        "pct_str": "3.2%" | "∞" | "N/A",
        "color":   "green" | "red" | "neutral",
        "label":   "▲ 3.2% vs last week"  (full badge text)
      }

    inverted=True is used for Unbilled Users where ▲ (more failures) is bad.
    """
    if current is None or previous is None:
        return {"arrow": "–", "pct_str": "N/A", "color": "neutral", "label": "– N/A"}

    if previous == 0:
        if current == 0:
            return {"arrow": "–", "pct_str": "No change", "color": "neutral", "label": "– No change"}
        pct_str = "∞"
        arrow   = "▲"
        is_positive = True
    else:
        delta = ((current - previous) / previous) * 100
        if abs(delta) < 0.05:
            return {"arrow": "–", "pct_str": "No change", "color": "neutral", "label": "– No change"}
        pct_str     = f"{abs(delta):.1f}%"
        is_positive = delta > 0
        arrow       = "▲" if is_positive else "▼"

    # Determine color: for standard metrics positive=green; for inverted positive=red
    if inverted:
        color = "red" if is_positive else "green"
    else:
        color = "green" if is_positive else "red"

    label = f"{arrow} {pct_str} vs last week"
    return {"arrow": arrow, "pct_str": pct_str, "color": color, "label": label}


# ---------------------------------------------------------------------------
# CSS helpers for delta badge colors
# ---------------------------------------------------------------------------

BADGE_STYLES = {
    "green": {
        "bg":     "#ECFDF5",
        "text":   "#065F46",
        "border": "#6EE7B7",
    },
    "red": {
        "bg":     "#FEF2F2",
        "text":   "#991B1B",
        "border": "#FCA5A5",
    },
    "neutral": {
        "bg":     "#F9FAFB",
        "text":   "#6B7280",
        "border": "#E5E7EB",
    },
}
