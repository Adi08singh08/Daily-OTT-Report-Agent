"""
HTML email renderer.

Can also be run as a CLI script:
  python email_renderer.py data.json report.html
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from formatter import (
    BADGE_STYLES,
    format_currency,
    format_delta,
    format_indian,
    format_revenue,
)


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
    name:        str
    brand_color: str
    mau:         MetricPair
    wau:         MetricPair
    dau_7dma:    MetricPair
    active_paid: MetricPair
    unbilled:    MetricPair
    revenue:     MetricPair
    rev_stream:  MetricPair
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

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily OTT Report — {date_label}</title>
</head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F3F4F6;padding:24px 0;">
  <tr><td align="center">
    <table width="680" cellpadding="0" cellspacing="0" style="max-width:680px;width:100%;">

      {_render_header(date_label)}
      {_render_summary_strip(ott, fasttv)}
      {_render_metrics_grid(ott, fasttv)}
      {_render_sparklines(ott, fasttv)}
      {_render_revenue_deep_dive(ott, fasttv)}
      {_render_unbilled_alert(ott, fasttv)}
      {_render_footer(ts_label)}

    </table>
  </td></tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_header(date_label: str) -> str:
    return f"""
      <!-- HEADER -->
      <tr><td style="background:#E8001C;border-radius:12px 12px 0 0;padding:24px 32px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <p style="margin:0;font-size:11px;color:#FECACA;letter-spacing:0.1em;text-transform:uppercase;">Hungama Digital Media</p>
              <p style="margin:4px 0 0;font-size:22px;font-weight:700;color:#FFFFFF;">Daily OTT Analytics Report</p>
            </td>
            <td align="right">
              <p style="margin:0;font-size:13px;color:#FECACA;">{date_label}</p>
              <p style="margin:4px 0 0;font-size:11px;color:#FCA5A5;">vs same day last week</p>
            </td>
          </tr>
        </table>
      </td></tr>"""


def _render_summary_strip(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> str:
    def pill(name: str, color: str) -> str:
        return (
            f'<span style="display:inline-block;background:{color}18;color:{color};'
            f'border:1px solid {color}44;border-radius:999px;padding:4px 14px;'
            f'font-size:12px;font-weight:600;">{name}</span>'
        )

    ott_pill    = pill(ott.name if ott else "Hungama OTT Production",    "#E8001C")
    fasttv_pill = pill(fasttv.name if fasttv else "FastTV Production", "#FF6B35")

    return f"""
      <!-- SUMMARY STRIP -->
      <tr><td style="background:#FFFFFF;padding:14px 32px;border-left:1px solid #E5E7EB;border-right:1px solid #E5E7EB;">
        {ott_pill}&nbsp;&nbsp;{fasttv_pill}
      </td></tr>"""


def _render_metrics_grid(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> str:
    metrics = [
        ("MAU (D-30)",          "mau",         False, format_indian,  None),
        ("WAU (D-7)",           "wau",         False, format_indian,  None),
        ("DAU 7-Day Avg",       "dau_7dma",    False, format_indian,  None),
        ("Active Paid Base",    "active_paid", False, format_indian,  None),
        ("Unbilled Users",      "unbilled",    True,  format_indian,  None),
        ("Month Revenue",       "revenue",     False, format_revenue, None),
        ("Revenue / Stream",    "rev_stream",  False, format_currency,None),
    ]

    rows = []
    for label, attr, inverted, fmt_fn, _ in metrics:
        ott_pair    = getattr(ott,    attr) if ott    else None
        fasttv_pair = getattr(fasttv, attr) if fasttv else None

        ott_card    = _render_metric_card(
            label,
            fmt_fn(ott_pair.current if ott_pair else None),
            format_delta(
                ott_pair.current if ott_pair else None,
                ott_pair.previous if ott_pair else None,
                inverted=inverted,
            ),
            ott.brand_color if ott else "#E8001C",
        )
        fasttv_card = _render_metric_card(
            label,
            fmt_fn(fasttv_pair.current if fasttv_pair else None),
            format_delta(
                fasttv_pair.current if fasttv_pair else None,
                fasttv_pair.previous if fasttv_pair else None,
                inverted=inverted,
            ),
            fasttv.brand_color if fasttv else "#FF6B35",
        )

        rows.append(f"""
        <tr>
          <td style="padding:6px 4px 0 0;">{ott_card}</td>
          <td style="padding:6px 0 0 4px;">{fasttv_card}</td>
        </tr>""")

    rows_html = "\n".join(rows)
    ott_label    = ott.name    if ott    else "Hungama OTT Production"
    fasttv_label = fasttv.name if fasttv else "FastTV Production"

    return f"""
      <!-- METRICS GRID -->
      <tr><td style="background:#FFFFFF;padding:20px 32px 8px;border-left:1px solid #E5E7EB;border-right:1px solid #E5E7EB;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <!-- Column headers -->
          <tr>
            <td width="50%" style="padding:0 4px 8px 0;">
              <p style="margin:0;font-size:11px;font-weight:700;color:#E8001C;text-transform:uppercase;letter-spacing:0.05em;">{ott_label}</p>
            </td>
            <td width="50%" style="padding:0 0 8px 4px;">
              <p style="margin:0;font-size:11px;font-weight:700;color:#FF6B35;text-transform:uppercase;letter-spacing:0.05em;">{fasttv_label}</p>
            </td>
          </tr>
          {rows_html}
        </table>
      </td></tr>"""


def _render_metric_card(
    label: str,
    value_str: str,
    delta: dict,
    brand_color: str,
) -> str:
    style = BADGE_STYLES[delta["color"]]
    badge_html = (
        f'<span style="display:inline-block;background:{style["bg"]};color:{style["text"]};'
        f'border:1px solid {style["border"]};border-radius:999px;padding:2px 10px;'
        f'font-size:12px;font-weight:500;">{delta["label"]}</span>'
    )
    return f"""<table width="100%" cellpadding="0" cellspacing="0"
  style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:8px;border-top:3px solid {brand_color};">
  <tr><td style="padding:14px 16px;">
    <p style="font-size:10px;color:#6B7280;margin:0 0 4px;text-transform:uppercase;letter-spacing:0.06em;">{label}</p>
    <p style="font-size:26px;font-weight:700;color:#111827;margin:0 0 8px;line-height:1.1;">{value_str}</p>
    {badge_html}
  </td></tr>
</table>"""


# ---------------------------------------------------------------------------
# Sparklines
# ---------------------------------------------------------------------------

def _render_sparklines(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> str:
    ott_svg    = _render_sparkline_svg(ott.dau_sparkline    if ott    else [], ott.brand_color    if ott    else "#E8001C")
    fasttv_svg = _render_sparkline_svg(fasttv.dau_sparkline if fasttv else [], fasttv.brand_color if fasttv else "#FF6B35")

    ott_label    = ott.name    if ott    else "Hungama OTT"
    fasttv_label = fasttv.name if fasttv else "FastTV"

    return f"""
      <!-- SPARKLINES -->
      <tr><td style="background:#FFFFFF;padding:16px 32px;border-left:1px solid #E5E7EB;border-right:1px solid #E5E7EB;">
        <p style="margin:0 0 12px;font-size:12px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:0.05em;">DAU Trend (Last 30 Days)</p>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="50%" style="padding-right:12px;">
              <p style="margin:0 0 6px;font-size:11px;color:#E8001C;font-weight:600;">{ott_label}</p>
              {ott_svg}
            </td>
            <td width="50%" style="padding-left:12px;">
              <p style="margin:0 0 6px;font-size:11px;color:#FF6B35;font-weight:600;">{fasttv_label}</p>
              {fasttv_svg}
            </td>
          </tr>
        </table>
      </td></tr>"""


def _render_sparkline_svg(
    daily_values: list[int],
    brand_color: str,
    bar_width: int = 8,
    bar_gap: int = 2,
    max_height: int = 40,
) -> str:
    if not daily_values:
        return '<p style="font-size:11px;color:#9CA3AF;margin:0;">No data</p>'

    # Ensure exactly 30 points (pad or trim from the left)
    values = list(daily_values[-30:])
    while len(values) < 30:
        values.insert(0, 0)

    n = len(values)
    total_width = n * (bar_width + bar_gap) - bar_gap
    max_val = max(values) or 1
    light_color = brand_color + "55"  # semi-transparent

    bars = []
    for i, v in enumerate(values):
        x = i * (bar_width + bar_gap)
        bar_h = max(2, int((v / max_val) * max_height))
        y = max_height + 4 - bar_h  # +4 for bottom padding
        fill = brand_color if i == n - 1 else light_color
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_h}" fill="{fill}" rx="1"/>'
        )

    return (
        f'<svg width="{total_width}" height="{max_height + 8}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block;">'
        + "".join(bars)
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# Revenue deep-dive
# ---------------------------------------------------------------------------

def _render_revenue_deep_dive(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> str:
    def rev_block(proj: Optional[ProjectMetrics]) -> str:
        if not proj:
            return "<td><p style='color:#9CA3AF;font-size:13px;'>No data</p></td>"

        rev_delta    = format_delta(proj.revenue.current,   proj.revenue.previous)
        stream_delta = format_delta(proj.rev_stream.current, proj.rev_stream.previous)

        rev_style = BADGE_STYLES[rev_delta["color"]]
        st_style  = BADGE_STYLES[stream_delta["color"]]

        return f"""<td style="width:50%;vertical-align:top;padding:0 8px;">
          <p style="margin:0 0 12px;font-size:12px;font-weight:700;color:{proj.brand_color};">{proj.name}</p>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding-bottom:10px;">
                <p style="margin:0;font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;">Month Revenue</p>
                <p style="margin:2px 0 4px;font-size:20px;font-weight:700;color:#111827;">{format_revenue(proj.revenue.current)}</p>
                <span style="background:{rev_style['bg']};color:{rev_style['text']};border:1px solid {rev_style['border']};border-radius:999px;padding:1px 8px;font-size:11px;">{rev_delta['label']}</span>
              </td>
            </tr>
            <tr>
              <td>
                <p style="margin:0;font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;">Revenue / Stream</p>
                <p style="margin:2px 0 4px;font-size:20px;font-weight:700;color:#111827;">{format_currency(proj.rev_stream.current)}</p>
                <span style="background:{st_style['bg']};color:{st_style['text']};border:1px solid {st_style['border']};border-radius:999px;padding:1px 8px;font-size:11px;">{stream_delta['label']}</span>
              </td>
            </tr>
          </table>
        </td>"""

    return f"""
      <!-- REVENUE DEEP DIVE -->
      <tr><td style="padding:8px 32px 0;border-left:1px solid #E5E7EB;border-right:1px solid #E5E7EB;">
        <table width="100%" cellpadding="0" cellspacing="0"
          style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:8px;padding:20px;">
          <tr><td colspan="2" style="padding:0 8px 14px;">
            <p style="margin:0;font-size:12px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:0.05em;">Revenue Deep Dive</p>
          </td></tr>
          <tr>
            {rev_block(ott)}
            {rev_block(fasttv)}
          </tr>
        </table>
      </td></tr>"""


# ---------------------------------------------------------------------------
# Unbilled alert
# ---------------------------------------------------------------------------

def _render_unbilled_alert(
    ott: Optional[ProjectMetrics],
    fasttv: Optional[ProjectMetrics],
) -> str:
    ott_count    = int(ott.unbilled.current    or 0) if ott    else 0
    fasttv_count = int(fasttv.unbilled.current or 0) if fasttv else 0

    if ott_count == 0 and fasttv_count == 0:
        return ""

    from formatter import format_indian
    ott_str    = format_indian(ott_count)
    fasttv_str = format_indian(fasttv_count)

    return f"""
      <!-- UNBILLED ALERT -->
      <tr><td style="padding:8px 32px 0;border-left:1px solid #E5E7EB;border-right:1px solid #E5E7EB;">
        <table width="100%" cellpadding="0" cellspacing="0"
          style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:8px;">
          <tr><td style="padding:14px 16px;">
            <p style="margin:0;font-size:13px;color:#92400E;">
              ⚠️ <strong>Unbilled Users Alert</strong> —
              Hungama OTT: <strong>{ott_str}</strong> renewal failures (last 30 days)
              &nbsp;|&nbsp;
              FastTV: <strong>{fasttv_str}</strong> renewal failures (last 30 days)
            </p>
          </td></tr>
        </table>
      </td></tr>"""


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def _render_footer(ts_label: str) -> str:
    return f"""
      <!-- FOOTER -->
      <tr><td style="background:#1F2937;border-radius:0 0 12px 12px;padding:16px 32px;margin-top:8px;">
        <p style="margin:0;font-size:11px;color:#9CA3AF;text-align:center;">
          Generated by Hungama Analytics Agent &nbsp;·&nbsp; Data source: Mixpanel &nbsp;·&nbsp; {ts_label} IST
        </p>
      </td></tr>"""


# ---------------------------------------------------------------------------
# Build ProjectMetrics from data.json dict
# ---------------------------------------------------------------------------

def project_metrics_from_dict(d: dict) -> ProjectMetrics:
    """Converts a dict (one project's node from data.json) into a ProjectMetrics."""
    def mp(key: str) -> MetricPair:
        node = d.get(key, {})
        return MetricPair(
            current=node.get("current"),
            previous=node.get("previous"),
        )

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
    print(f"[✓] Report written to {sys.argv[2]} ({len(html):,} bytes)")
