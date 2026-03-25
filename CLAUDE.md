# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Agent Purpose

This is a **fully autonomous daily analytics reporting agent** for Hungama Digital Media. It runs every morning at **9:00 AM IST (03:30 UTC)**, pulls Mixpanel metrics for two OTT products, computes week-over-week deltas, renders an HTML email, and sends it via Gmail MCP. There is no application code — the agent *is* Claude Code executing these instructions.

---

## MCP Servers Required

| Server   | URL                                 | Purpose                          |
|----------|-------------------------------------|----------------------------------|
| Mixpanel | `https://mcp.mixpanel.com/sse`      | Fetch all analytics metrics      |
| Gmail    | `https://gmail.mcp.claude.com/mcp`  | Send the HTML report email       |

---

## Project Configuration

| Property            | Hungama OTT Production | FastTV Production |
|---------------------|------------------------|-------------------|
| Mixpanel Project ID | `3027789`              | `3976933`         |
| Workspace ID        | `3545613`              | `4472622`         |
| App Open event      | `App Open`             | `app_open`        |
| Stream event        | `stream`               | `stream_finished` |

**Recipient email:** `[CONFIGURE_RECIPIENT_EMAIL_HERE]` — replace before first run.

---

## Execution Steps

```
STEP 1 — Compute dates
  report_date  = today − 1 day          (YYYY-MM-DD)
  compare_date = today − 8 days
  month_start  = 1st of report_date's month

STEP 2 — Fetch Hungama OTT metrics (project 3027789)
  2a. MAU  — line query last 35 days; extract report_date and compare_date rows
  2b. WAU  — line query last 35 days; extract report_date and compare_date rows
  2c. DAU  — line query last 21 days; 7-DMA = avg(D-7..D-1) and avg(D-14..D-8)
  2d. Active paid base — unique users (npay_display_success + npay_renewal_success)
        with npay_expiry >= report_date (and >= compare_date for baseline)
  2e. Unbilled users — unique users of npay_renewal_failure, rolling 30d to report_date / compare_date
  2f. Revenue — sum(npay_paymentvalue) with filters below, month_start → report_date and → compare_date
  2g. Streams — count of `stream` events, month_start → report_date and → compare_date
  2h. Rev/Stream = Revenue ÷ Streams for both windows

STEP 3 — Fetch FastTV metrics (project 3976933) — same sub-steps, event = `stream_finished`

STEP 4 — Compute all deltas
  delta_pct = ((current − previous) / previous) × 100   (1 decimal place)

STEP 5 — Compose HTML email (see template section)

STEP 6 — Send via Gmail MCP
  to:      [CONFIGURE_RECIPIENT_EMAIL_HERE]
  subject: "📊 Daily OTT Report — Hungama OTT vs FastTV | {DD MMM YYYY}"
  body:    HTML string

STEP 7 — Log: "✅ Daily report sent for {report_date} at {timestamp}"
  On single-metric failure: log warning, use "N/A", continue.
  On total project failure: log critical error, do not send.
```

### Revenue filters (apply to both npay_display_success and npay_renewal_success)
- `npay_transaction_mode` = `Currency`
- `npay_currency` = `INR`
- `npay_paymentmode` ≠ `e-Coupon`
- `npay_paymentmode` ≠ `Google Wallet`

---

## Delta & Arrow Logic

**Standard metrics** (MAU, WAU, DAU-DMA, Paid Base, Revenue, Rev/Stream):
- `delta > 0` → 🟢 ▲ green badge
- `delta < 0` → 🔴 ▼ red badge

**Inverted metric** (Unbilled Users — more = worse):
- `delta > 0` → 🔴 ▲ red badge
- `delta < 0` → 🟢 ▼ green badge

When `previous = 0`: show `∞` instead of a percentage.

---

## Number Formatting (Indian system)

| Range               | Format       | Example        |
|---------------------|--------------|----------------|
| < 1,000             | integer      | 847            |
| 1,000 – 99,999      | Indian commas| 12,345         |
| 1,00,000 – 99,99,999| Lakh         | 4.87L          |
| ≥ 1,00,00,000       | Crore        | ₹4.02 Cr       |
| Revenue per stream  | ₹X.XX        | ₹13.52         |

---

## HTML Email Template (self-contained, inline CSS only)

### CSS color tokens
```css
--brand-primary: #E8001C;   /* Hungama red */
--fasttv-accent: #FF6B35;   /* FastTV orange */
--green-bg: #ECFDF5; --green-text: #065F46; --green-border: #6EE7B7;
--red-bg: #FEF2F2;   --red-text: #991B1B;   --red-border: #FCA5A5;
--neutral-bg: #F9FAFB; --card-bg: #FFFFFF; --text-primary: #111827;
--text-secondary: #6B7280; --border: #E5E7EB;
```

### Layout sections (in order)
1. **Header** — logo placeholder + title + report date
2. **Summary strip** — two pills: "Hungama OTT Production" | "FastTV Production"
3. **Metrics grid** — 7 rows × 2 columns (OTT left, FastTV right); each cell has metric name, large value, delta badge
4. **MAU sparkline** — 30-point inline SVG bar chart per product (bars 8px wide, 2px gap, max height 40px; last bar in brand color, others in lighter tint)
5. **Revenue deep dive** — Revenue | Streams | Rev/Stream for both products
6. **Unbilled alert** (conditional) — amber `#FFFBEB / #FCD34D` box if unbilled > 0 for either product
7. **Footer** — "Generated by Hungama Analytics Agent · Data source: Mixpanel · {timestamp} IST"

### Metric card pattern
```html
<td style="background:#ffffff;border:1px solid #E5E7EB;border-radius:8px;padding:16px;width:48%;vertical-align:top;">
  <p style="font-size:11px;color:#6B7280;margin:0 0 4px;text-transform:uppercase;letter-spacing:0.05em;">MAU (D-30)</p>
  <p style="font-size:28px;font-weight:600;color:#111827;margin:0 0 8px;font-family:Arial,sans-serif;">12,42,338</p>
  <span style="display:inline-block;background:#ECFDF5;color:#065F46;border:1px solid #6EE7B7;
               border-radius:999px;padding:2px 10px;font-size:12px;font-weight:500;">▲ 3.2% vs last week</span>
</td>
```

---

## Error Handling

| Situation | Behaviour |
|-----------|-----------|
| Empty Mixpanel result | Show `N/A`, continue |
| `previous = 0` | Show `∞` delta |
| Gmail send failure | Retry once after 60 s; log full error if still failing |
| Single metric failure | Log warning, use `N/A`, do not abort |
| Both projects fail entirely | Log critical error, do not send email |

---

## Customisation

- **Recipients:** update `To:` — comma-separate for multiple addresses
- **Schedule:** currently 9:00 AM IST = 03:30 UTC
- **Comparison window:** replace D-8 with D-N; update delta label in email
- **New metric:** add fetch step in Step 2/3 and a card in the metrics grid
- **New project:** duplicate Steps 2–3 with new project ID; add a third column to the grid

---

*Last updated: March 2026 · Maintained by Aditya / Hungama Product & Analytics*
