"""
HTML email renderer — dark professional design (Hungama Analytics Agent).

CLI:
  python email_renderer.py data.json report.html
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from formatter import (
    format_currency,
    format_delta,
    format_indian,
    format_revenue,
)


# ---------------------------------------------------------------------------
# Design tokens — dark dashboard theme (email-client safe, no rgba/8-digit hex)
# ---------------------------------------------------------------------------

BG_OUTER      = "#0D1117"
BG_CARD       = "#161B26"
BG_CARD_ALT   = "#1C2232"
BORDER_CARD   = "#2D3555"
TEXT_PRIMARY  = "#E6EDF3"
TEXT_SECONDARY= "#8B949E"
TEXT_MUTED    = "#586374"

# Delta badge colors — solid 6-digit hex only (Outlook compatible)
BADGE = {
    "green":   {"bg": "#0D2818", "text": "#3FB950", "border": "#238636"},
    "red":     {"bg": "#2D1117", "text": "#F85149", "border": "#DA3633"},
    "neutral": {"bg": "#21262D", "text": "#8B949E", "border": "#30363D"},
}
AMBER    = {"bg": "#271D00", "text": "#E3B341", "border": "#9E6A03"}
CRITICAL = {"bg": "#2D0B0B", "text": "#FF7B72", "border": "#7D2A2A"}

# Sparkline dim bar colors (brand color approximations, no alpha)
_SPARKLINE_DIM = {"#E8001C": "#4A0A12", "#FF6B35": "#4A2510"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MetricPair:
    """Holds current + previous values for a single metric."""
    current:  Optional[float]
    previous: Optional[float]


@dataclass
class ProjectMetrics:
    name:          str
    brand_color:   str
    mau:           MetricPair
    wau:           MetricPair
    dau_7dma:      MetricPair
    active_paid:   MetricPair
    unbilled:      MetricPair
    revenue:       MetricPair
    rev_stream:    MetricPair
    # 30 daily DAU values (oldest → newest) for sparkline
    dau_sparkline: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level renderer
# ---------------------------------------------------------------------------

def render_email(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
    report_date: date,
    generated_at: datetime,
) -> str:
    date_label = report_date.strftime("%d %b %Y")
    ts_label   = generated_at.strftime("%d %b %Y, %I:%M %p")
    has_critical = _any_critical_unbilled(ott, fasttv)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Daily OTT Report — {date_label}</title>
</head>
<body style="margin:0;padding:0;background:{BG_OUTER};font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{BG_OUTER};padding:28px 0;">
  <tr><td align="center">
    <table width="660" cellpadding="0" cellspacing="0"
      style="max-width:660px;width:100%;border-radius:12px;overflow:hidden;border:1px solid {BORDER_CARD};">

      {_render_header(date_label)}
      {_render_summary_strip(ott, fasttv)}
      {_render_metrics_grid(ott, fasttv)}
      {_render_sparklines(ott, fasttv)}
      {_render_revenue_deep_dive(ott, fasttv)}
      {_render_unbilled_alert(ott, fasttv, has_critical)}
      {_render_footer(ts_label)}

    </table>
  </td></tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def _render_header(date_label: str) -> str:
    return f"""
      <!-- HEADER -->
      <tr>
        <td style="background:{BG_CARD};padding:0;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <!-- Two-tone accent bar (email-client safe, no gradient) -->
            <tr>
              <td width="50%" height="4" style="background:#E8001C;font-size:0;">&nbsp;</td>
              <td width="50%" height="4" style="background:#FF6B35;font-size:0;">&nbsp;</td>
            </tr>
            <tr>
              <td style="padding:22px 28px 20px;">
                <p style="margin:0 0 4px;font-size:10px;color:{TEXT_MUTED};letter-spacing:0.14em;
                           text-transform:uppercase;">Hungama Digital Media</p>
                <p style="margin:0;font-size:22px;font-weight:700;color:{TEXT_PRIMARY};
                           letter-spacing:-0.3px;">Daily OTT Analytics Report</p>
              </td>
              <td style="padding:22px 28px 20px;" align="right">
                <p style="margin:0 0 4px;font-size:15px;font-weight:700;color:{TEXT_PRIMARY};">{date_label}</p>
                <p style="margin:0;font-size:11px;color:{TEXT_MUTED};">vs same day last week</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <!-- Header divider -->
      <tr><td height="1" style="background:{BORDER_CARD};font-size:0;">&nbsp;</td></tr>"""


# ---------------------------------------------------------------------------
# Summary strip
# ---------------------------------------------------------------------------

def _render_summary_strip(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> str:
    def pill(name: str, bg: str, text: str, border: str) -> str:
        return (
            f'<span style="display:inline-block;background:{bg};color:{text};'
            f'border:1px solid {border};border-radius:999px;padding:5px 14px;'
            f'font-size:12px;font-weight:700;letter-spacing:0.02em;">{name}</span>'
        )

    ott_pill    = pill(ott.name    if ott    else "Hungama OTT Production",
                       "#290008", "#E8001C", "#5A0010")
    fasttv_pill = pill(fasttv.name if fasttv else "FastTV Production",
                       "#291400", "#FF6B35", "#5A2800")

    return f"""
      <!-- SUMMARY STRIP -->
      <tr><td style="background:{BG_CARD};padding:14px 28px 16px;">
        {ott_pill}&nbsp;&nbsp;{fasttv_pill}
        <p style="margin:8px 0 0;font-size:11px;color:{TEXT_MUTED};">
          Week-over-week comparison &nbsp;·&nbsp; Data source: Mixpanel
        </p>
      </td></tr>
      <tr><td height="1" style="background:{BORDER_CARD};font-size:0;">&nbsp;</td></tr>"""


# ---------------------------------------------------------------------------
# Metrics grid — 7 rows × 2 columns
# ---------------------------------------------------------------------------

def _render_metrics_grid(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> str:
    metrics = [
        ("MAU (D-30)",        "mau",         False, format_indian),
        ("WAU (D-7)",         "wau",         False, format_indian),
        ("DAU 7-Day Avg",     "dau_7dma",    False, format_indian),
        ("Active Paid Base",  "active_paid", False, format_indian),
        ("Unbilled Users",    "unbilled",    True,  format_indian),
        ("Month Revenue",     "revenue",     False, format_revenue),
        ("Revenue / Stream",  "rev_stream",  False, format_currency),
    ]

    ott_label    = ott.name    if ott    else "Hungama OTT Production"
    fasttv_label = fasttv.name if fasttv else "FastTV Production"

    rows = []
    for i, (label, attr, inverted, fmt_fn) in enumerate(metrics):
        ott_pair    = getattr(ott,    attr) if ott    else None
        fasttv_pair = getattr(fasttv, attr) if fasttv else None

        ott_card = _metric_card(
            label,
            fmt_fn(ott_pair.current  if ott_pair else None),
            format_delta(ott_pair.current  if ott_pair else None,
                         ott_pair.previous if ott_pair else None,
                         inverted=inverted),
            "#E8001C",
        )
        fasttv_card = _metric_card(
            label,
            fmt_fn(fasttv_pair.current  if fasttv_pair else None),
            format_delta(fasttv_pair.current  if fasttv_pair else None,
                         fasttv_pair.previous if fasttv_pair else None,
                         inverted=inverted),
            "#FF6B35",
        )

        row_bg = BG_CARD if i % 2 == 0 else BG_CARD_ALT
        rows.append(f"""
        <tr>
          <td width="50%" style="padding:5px 5px 5px 0;vertical-align:top;background:{row_bg};">{ott_card}</td>
          <td width="50%" style="padding:5px 0 5px 5px;vertical-align:top;background:{row_bg};">{fasttv_card}</td>
        </tr>""")

    rows_html = "\n".join(rows)

    return f"""
      <!-- METRICS GRID -->
      <tr><td style="background:{BG_CARD};padding:20px 28px 14px;">
        <!-- Column headers -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;">
          <tr>
            <td width="50%" style="padding-right:5px;">
              <p style="margin:0;font-size:10px;font-weight:700;color:#E8001C;
                         text-transform:uppercase;letter-spacing:0.1em;">{ott_label}</p>
            </td>
            <td width="50%" style="padding-left:5px;">
              <p style="margin:0;font-size:10px;font-weight:700;color:#FF6B35;
                         text-transform:uppercase;letter-spacing:0.1em;">{fasttv_label}</p>
            </td>
          </tr>
        </table>
        <table width="100%" cellpadding="0" cellspacing="0">
          {rows_html}
        </table>
      </td></tr>
      <tr><td height="1" style="background:{BORDER_CARD};font-size:0;">&nbsp;</td></tr>"""


def _metric_card(label: str, value_str: str, delta: dict, brand_color: str) -> str:
    bs = BADGE[delta["color"]]
    badge_html = (
        f'<span style="display:inline-block;background:{bs["bg"]};color:{bs["text"]};'
        f'border:1px solid {bs["border"]};border-radius:999px;padding:2px 10px;'
        f'font-size:11px;font-weight:700;">{delta["label"]}</span>'
    )
    return f"""<table width="100%" cellpadding="0" cellspacing="0"
  style="background:{BG_CARD_ALT};border:1px solid {BORDER_CARD};
         border-radius:8px;border-left:3px solid {brand_color};">
  <tr><td style="padding:14px 16px;">
    <p style="font-size:10px;color:{TEXT_MUTED};margin:0 0 6px;
               text-transform:uppercase;letter-spacing:0.09em;">{label}</p>
    <p style="font-size:26px;font-weight:700;color:{TEXT_PRIMARY};margin:0 0 10px;
               line-height:1.1;">{value_str}</p>
    {badge_html}
  </td></tr>
</table>"""


# ---------------------------------------------------------------------------
# DAU Sparklines
# ---------------------------------------------------------------------------

def _render_sparklines(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> str:
    ott_svg    = _sparkline_svg(ott.dau_sparkline    if ott    else [], "#E8001C")
    fasttv_svg = _sparkline_svg(fasttv.dau_sparkline if fasttv else [], "#FF6B35")
    ott_lbl    = ott.name    if ott    else "Hungama OTT"
    fasttv_lbl = fasttv.name if fasttv else "FastTV"

    return f"""
      <!-- SPARKLINES -->
      <tr><td style="background:{BG_CARD};padding:20px 28px;">
        <p style="margin:0 0 16px;font-size:11px;font-weight:700;color:{TEXT_SECONDARY};
                   text-transform:uppercase;letter-spacing:0.1em;">DAU Trend — Last 30 Days</p>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="50%" style="padding-right:16px;vertical-align:top;">
              <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#E8001C;">{ott_lbl}</p>
              {ott_svg}
            </td>
            <td width="50%" style="padding-left:16px;vertical-align:top;">
              <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#FF6B35;">{fasttv_lbl}</p>
              {fasttv_svg}
            </td>
          </tr>
        </table>
      </td></tr>
      <tr><td height="1" style="background:{BORDER_CARD};font-size:0;">&nbsp;</td></tr>"""


def _sparkline_svg(
    daily_values: list[int],
    brand_color: str,
    bar_width: int = 7,
    bar_gap: int = 2,
    max_height: int = 44,
) -> str:
    if not daily_values:
        return f'<p style="font-size:11px;color:{TEXT_MUTED};margin:0;">No data</p>'

    # Pad or trim to exactly 30 points
    values = list(daily_values[-30:])
    while len(values) < 30:
        values.insert(0, 0)

    n           = len(values)
    total_width = n * (bar_width + bar_gap) - bar_gap
    max_val     = max(values) or 1
    dim_color   = _SPARKLINE_DIM.get(brand_color, "#333344")

    bars = []
    for i, v in enumerate(values):
        x     = i * (bar_width + bar_gap)
        bar_h = max(2, int((v / max_val) * max_height))
        y     = max_height + 8 - bar_h
        fill  = brand_color if i == n - 1 else dim_color
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_h}" fill="{fill}" rx="2"/>'
        )

    return (
        f'<svg width="{total_width}" height="{max_height + 12}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block;">'
        + "".join(bars)
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# Revenue deep dive
# ---------------------------------------------------------------------------

def _render_revenue_deep_dive(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> str:
    def rev_col(proj: Optional[ProjectMetrics], color: str, divider: bool) -> str:
        if not proj:
            return f"<td><p style='color:{TEXT_MUTED};font-size:13px;'>No data</p></td>"

        rev_d = format_delta(proj.revenue.current,    proj.revenue.previous)
        rs_d  = format_delta(proj.rev_stream.current, proj.rev_stream.previous)

        def mini_badge(d: dict) -> str:
            bs = BADGE[d["color"]]
            return (
                f'<span style="display:inline-block;background:{bs["bg"]};color:{bs["text"]};'
                f'border:1px solid {bs["border"]};border-radius:999px;padding:1px 8px;'
                f'font-size:10px;font-weight:700;">{d["label"]}</span>'
            )

        right_border = f"border-right:1px solid {BORDER_CARD};" if divider else ""

        return f"""<td style="width:50%;vertical-align:top;padding:0 20px;{right_border}">
          <p style="margin:0 0 14px;font-size:10px;font-weight:700;color:{color};
                     text-transform:uppercase;letter-spacing:0.1em;">{proj.name}</p>
          <p style="margin:0;font-size:10px;color:{TEXT_MUTED};text-transform:uppercase;
                     letter-spacing:0.06em;">Month Revenue</p>
          <p style="margin:4px 0 6px;font-size:22px;font-weight:700;color:{TEXT_PRIMARY};">
            {format_revenue(proj.revenue.current)}</p>
          {mini_badge(rev_d)}
          <p style="margin:16px 0 0;font-size:10px;color:{TEXT_MUTED};text-transform:uppercase;
                     letter-spacing:0.06em;">Revenue / Stream</p>
          <p style="margin:4px 0 6px;font-size:22px;font-weight:700;color:{TEXT_PRIMARY};">
            {format_currency(proj.rev_stream.current)}</p>
          {mini_badge(rs_d)}
        </td>"""

    return f"""
      <!-- REVENUE DEEP DIVE -->
      <tr><td style="background:{BG_CARD};padding:20px 28px;">
        <p style="margin:0 0 14px;font-size:11px;font-weight:700;color:{TEXT_SECONDARY};
                   text-transform:uppercase;letter-spacing:0.1em;">Revenue Deep Dive — Month to Date</p>
        <table width="100%" cellpadding="0" cellspacing="0"
          style="background:{BG_CARD_ALT};border:1px solid {BORDER_CARD};border-radius:8px;">
          <tr style="padding:18px 0;">
            <td height="18" style="font-size:0;">&nbsp;</td>
          </tr>
          <tr>
            {rev_col(ott,    "#E8001C", divider=True)}
            {rev_col(fasttv, "#FF6B35", divider=False)}
          </tr>
          <tr>
            <td height="18" style="font-size:0;">&nbsp;</td>
          </tr>
        </table>
      </td></tr>
      <tr><td height="1" style="background:{BORDER_CARD};font-size:0;">&nbsp;</td></tr>"""


# ---------------------------------------------------------------------------
# Unbilled alert (standard) / critical alert (spike > 500%)
# ---------------------------------------------------------------------------

def _any_critical_unbilled(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> bool:
    for proj in (ott, fasttv):
        if proj is None:
            continue
        c, p = proj.unbilled.current, proj.unbilled.previous
        if c is not None and p is not None and p > 0:
            if ((c - p) / p) * 100 > 500:
                return True
    return False


def _render_unbilled_alert(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
    is_critical: bool,
) -> str:
    ott_count    = int(ott.unbilled.current    or 0) if ott    else 0
    fasttv_count = int(fasttv.unbilled.current or 0) if fasttv else 0

    if ott_count == 0 and fasttv_count == 0:
        return ""

    ott_str    = format_indian(ott_count)
    fasttv_str = format_indian(fasttv_count)

    if is_critical:
        theme = CRITICAL
        # Find which product has the spike
        spike_parts = []
        for proj, label in ((fasttv, "FastTV"), (ott, "Hungama OTT")):
            if proj is None:
                continue
            c, p = proj.unbilled.current, proj.unbilled.previous
            if c is not None and p is not None and p > 0 and ((c - p) / p) * 100 > 500:
                pct = int(((c - p) / p) * 100)
                spike_parts.append(
                    f"{label}: <strong>{format_indian(int(c))}</strong> failures "
                    f"(+{pct:,}% vs {format_indian(int(p))} last week)"
                )
        spike_text = " &nbsp;|&nbsp; ".join(spike_parts) if spike_parts else ""

        title = "&#128680; CRITICAL — Unbilled Users Spike Detected"
        body  = f"{spike_text}. Immediate investigation recommended."
    else:
        theme = AMBER
        title = "&#9888;&#65039; Unbilled Users Alert"
        body  = (
            f"Hungama OTT: <strong>{ott_str}</strong> renewal failures (last 30 days)"
            f"&nbsp;|&nbsp; FastTV: <strong>{fasttv_str}</strong> renewal failures (last 30 days)"
        )

    return f"""
      <!-- UNBILLED ALERT -->
      <tr><td style="background:{BG_CARD};padding:0 28px 20px;">
        <table width="100%" cellpadding="0" cellspacing="0"
          style="background:{theme['bg']};border:1px solid {theme['border']};border-radius:8px;">
          <tr><td style="padding:14px 18px;">
            <p style="margin:0 0 5px;font-size:12px;font-weight:700;color:{theme['text']};">{title}</p>
            <p style="margin:0;font-size:12px;color:{theme['text']};line-height:1.5;">{body}</p>
          </td></tr>
        </table>
      </td></tr>"""


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def _render_footer(ts_label: str) -> str:
    return f"""
      <!-- FOOTER -->
      <tr><td style="background:#0A0D14;border-top:1px solid {BORDER_CARD};padding:16px 28px;">
        <p style="margin:0;font-size:11px;color:{TEXT_MUTED};text-align:center;letter-spacing:0.03em;">
          Generated by Hungama Analytics Agent &nbsp;·&nbsp; Data source: Mixpanel &nbsp;·&nbsp; {ts_label} IST
        </p>
      </td></tr>"""


# ---------------------------------------------------------------------------
# Build ProjectMetrics from data.json dict
# ---------------------------------------------------------------------------

def project_metrics_from_dict(d: dict) -> ProjectMetrics:
    """Converts a dict (one project node from data.json) into a ProjectMetrics."""
    def mp(key: str) -> MetricPair:
        node = d.get(key, {})
        return MetricPair(current=node.get("current"), previous=node.get("previous"))

    return ProjectMetrics(
        name=d["name"],
        brand_color=d["brand_color"],
        mau=mp("mau"),
        wau=mp("wau"),
        dau_7dma=mp("dau_7dma"),
        active_paid=mp("active_paid"),
        unbilled=mp("unbilled"),
        revenue=mp("revenue"),
        rev_stream=mp("rev_stream"),
        dau_sparkline=d.get("dau_sparkline", []),
    )


# ---------------------------------------------------------------------------
# CLI: python email_renderer.py data.json report.html
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python email_renderer.py data.json output.html")
        sys.exit(1)

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    ott_data    = data.get("ott")
    fasttv_data = data.get("fasttv")

    ott    = project_metrics_from_dict(ott_data)    if ott_data    else None
    fasttv = project_metrics_from_dict(fasttv_data) if fasttv_data else None

    report_date  = date.fromisoformat(data["report_date"])
    generated_at = datetime.now()

    html = render_email(ott, fasttv, report_date, generated_at)
    Path(sys.argv[2]).write_text(html, encoding="utf-8")
    print(f"[OK] Report written to {sys.argv[2]} ({len(html):,} bytes)")
