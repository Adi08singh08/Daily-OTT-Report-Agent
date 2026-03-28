# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Agent Purpose

This is a **fully autonomous daily analytics reporting agent** for Hungama Digital Media. It pulls Mixpanel metrics for two OTT products, computes week-over-week deltas, renders an HTML email, and delivers it via Outlook SMTP through a GitHub Actions workflow. There is no application server — the agent *is* Claude Code executing `agent_prompt.md`.

---

## Scheduling

The agent runs via Claude Code's **`/schedule` skill** — *not* Windows Task Scheduler (`scheduler.bat` is a documentation stub only).

- **Cron:** `30 3 * * *` (= 9:00 AM IST = 03:30 UTC)
- **Prompt:** contents of `agent_prompt.md`

---

## MCP Servers Required

| Server   | URL                            | Purpose                     |
|----------|--------------------------------|-----------------------------|
| Mixpanel | `https://mcp.mixpanel.com/sse` | Fetch all analytics metrics |

---

## Python Modules

| File               | Purpose                                                                          |
|--------------------|----------------------------------------------------------------------------------|
| `agent_prompt.md`  | **Authoritative step-by-step execution instructions** (what the scheduled agent runs) |
| `formatter.py`     | `format_indian()`, `format_currency()`, `format_revenue()`, `format_delta()`, `BADGE_STYLES` |
| `email_renderer.py`| `render_email(ott, fasttv, report_date, generated_at)` → HTML string; also a CLI tool |
| `emailer.py`       | `send_report()` via Outlook SMTP (stdlib `smtplib`, no external deps except `dotenv`) |

### Development commands

```bash
pip install -r requirements.txt          # installs python-dotenv (sendgrid entry is legacy/unused)

# Render HTML from any data.json — output is gitignored
python email_renderer.py data.json report_preview.html

# Send email directly (bypassing GitHub Actions) — requires .env with SMTP_USER / SMTP_PASSWORD
python emailer.py report.html "Subject" "recipient@example.com"
```

---

## Git Artefacts

`data.json` and `report.html` are **intentionally tracked in git**. Pushing them to `master` is the delivery trigger — the GitHub Actions workflow fires on any push that touches `report.html`.

`report_preview.html` is gitignored; use it for local rendering tests.

---

## Email Delivery — GitHub Actions

`.github/workflows/send-report.yml` triggers on push of `report.html` to `master`. It runs `emailer.py` using two repository secrets:

| Secret             | Value                              |
|--------------------|------------------------------------|
| `OUTLOOK_USER`     | Outlook sender address             |
| `OUTLOOK_PASSWORD` | Outlook password or app password   |

Recipients are hardcoded in the workflow file (`aditya.singh@hungama.com`). Edit the `python emailer.py ...` line there to change or add recipients.

---

## Project Configuration

| Property            | Hungama OTT Production | FastTV Production |
|---------------------|------------------------|-------------------|
| Mixpanel Project ID | `3027789`              | `3976933`         |
| Workspace ID        | `3545613`              | `4472622`         |
| App Open event      | `App Open`             | `app_open`        |
| Stream event        | `stream`               | `stream_finished` |

---

## Execution Steps (summary — see `agent_prompt.md` for full Mixpanel query payloads)

```
STEP 1 — Compute dates
  report_date  = today − 1 day
  compare_date = today − 8 days        (WoW baseline)
  month_start  = 1st of report_date's month
  dau_from     = compare_date − 6 days (start of 14-day DAU window)

STEP 2 — Fetch Hungama OTT metrics  (project_id=3027789, workspace_id=3545613)
  MAU / WAU    — one line query (compare_date → report_date); extract both date rows
  DAU 7-DMA    — one line query (dau_from → report_date, 14 rows)
                 current  = avg of 7 rows ending on report_date
                 previous = avg of 7 rows ending on compare_date
  DAU sparkline— separate line query (report_date−29d → report_date, 30 rows)
  Active paid  — unique(npay_display_success) + unique(npay_renewal_success)
                 filter: npay_expiry >= report_date; date range: 2020-01-01 → report_date
                 repeat with npay_expiry >= compare_date and to: compare_date
  Unbilled     — unique(npay_renewal_failure), rolling 30d window ending on report_date / compare_date
  Revenue      — sum(npay_paymentvalue) for display + renewal events, month_start → report_date / compare_date
                 (see Revenue Filters below)
  Streams      — total("stream" events), month_start → report_date / compare_date
  Rev/Stream   — Revenue ÷ Streams (computed, not queried)

STEP 3 — Fetch FastTV metrics (project_id=3976933, workspace_id=4472622)
  Same as Step 2; substitute app_open for App Open, stream_finished for stream

STEP 4 — Sanity check all values (re-run once on failure; null + N/A if still failing)

STEP 5 — Write data.json

STEP 6 — Render HTML
  python email_renderer.py data.json report.html

STEP 7 — Commit & push  (triggers GitHub Actions email delivery)
  git add data.json report.html
  git commit -m "Daily OTT Report <report_date>"
  git push origin master
  Retry once after 60 s on push failure. Never skip.

STEP 8 — Log: "Daily report complete for <report_date>"
```

### Revenue filters (both display and renewal events)
- `npay_transaction_mode` = `Currency`
- `npay_currency` = `INR`
- `npay_paymentmode` ≠ `e-Coupon`
- `npay_paymentmode` ≠ `Google Wallet`

### Sanity check expected ranges

| Metric           | OTT                              | FastTV              |
|------------------|----------------------------------|---------------------|
| MAU              | 10,00,000 – 20,00,000            | < 1,00,000          |
| WAU              | 2,00,000 – 8,00,000              | < 50,000            |
| DAU 7-DMA        | 50,000 – 1,50,000                | < 10,000            |
| Active Paid Base | 4,00,000 – 6,00,000              | < 10,000            |
| Revenue MTD      | > ₹1,00,00,000 by mid-month      | < ₹5,00,000         |
| Rev/Stream       | ₹10 – ₹20                        | ₹0.05 – ₹0.50       |

Additional rules: any metric == 0 (not null) → treat as null, show N/A. OTT MAU < 5,00,000 → CRITICAL query error, re-run. Unbilled delta > 500% → add CRITICAL ALERT block in email.

---

## data.json Schema

```json
{
  "report_date":  "YYYY-MM-DD",
  "compare_date": "YYYY-MM-DD",
  "ott": {
    "name": "Hungama OTT Production",
    "brand_color": "#E8001C",
    "mau":         {"current": 1274411,  "previous": 1336985},
    "wau":         {"current": 409430,   "previous": 409543},
    "dau_7dma":    {"current": 78517,    "previous": 78394},
    "active_paid": {"current": 491131,   "previous": 501046},
    "unbilled":    {"current": 109170,   "previous": 119036},
    "revenue":     {"current": 40152949, "previous": 29189623},
    "rev_stream":  {"current": 13.56,    "previous": 13.79},
    "dau_sparkline": [84873, 84234, ...]
  },
  "fasttv": { "brand_color": "#FF6B35", ... }
}
```

`dau_sparkline` targets 30 integers (oldest → newest); the renderer pads shorter arrays with leading zeros. Use `null` for any metric value that could not be fetched.

---

## Delta & Arrow Logic

**Standard metrics** (MAU, WAU, DAU-DMA, Paid Base, Revenue, Rev/Stream):
- `delta > 0` → 🟢 ▲ green badge
- `delta < 0` → 🔴 ▼ red badge

**Inverted metric** (Unbilled Users — more = worse):
- `delta > 0` → 🔴 ▲ red badge
- `delta < 0` → 🟢 ▼ green badge

Edge cases: `|delta| < 0.05%` → "No change" (neutral). `previous = 0, current > 0` → "∞". `both = 0` → "No change".

---

## Number Formatting (Indian system — `formatter.py`)

| Range               | Format        | Example    |
|---------------------|---------------|------------|
| < 1,000             | integer       | 847        |
| 1,000 – 99,999      | Indian commas | 12,345     |
| 1,00,000 – 99,99,999| Lakh          | 4.87L      |
| ≥ 1,00,00,000       | Crore         | ₹4.02 Cr   |
| Revenue per stream  | ₹X.XX         | ₹13.52     |

---

## HTML Email Template (self-contained, inline CSS only)

### CSS color tokens
```
Hungama red:  #E8001C    FastTV orange: #FF6B35
Green badge:  bg #ECFDF5 / text #065F46 / border #6EE7B7
Red badge:    bg #FEF2F2 / text #991B1B / border #FCA5A5
Neutral:      bg #F9FAFB / text #6B7280 / border #E5E7EB
Unbilled:     bg #FFFBEB / border #FCD34D
Footer:       bg #1F2937
```

### Layout sections (rendered by `email_renderer.py`)
1. **Header** — Hungama red banner, title, report date
2. **Summary strip** — brand-color pills for each product
3. **Metrics grid** — 7 rows × 2 columns; cards have brand-color top border, large value, delta badge
4. **DAU sparkline** — inline SVG bar chart, 30 bars × 8 px wide × 2 px gap, max height 40 px; last bar = brand color, others = brand+`55` (semi-transparent)
5. **Revenue deep dive** — Month Revenue + Rev/Stream side-by-side
6. **Unbilled alert** — conditional amber box; shown only when unbilled > 0 for either product
7. **Footer** — dark bar with "Generated by Hungama Analytics Agent · {timestamp} IST"

---

## Error Handling

| Situation                   | Behaviour                                               |
|-----------------------------|---------------------------------------------------------|
| Empty Mixpanel result       | Show `N/A`, continue                                    |
| Metric value == 0           | Treat as null, show `N/A`                               |
| `previous = 0`              | Show `∞` delta                                          |
| Single metric failure       | Log `[WARN]`, use `N/A`, do not abort                   |
| Both projects fail entirely | Log critical error, do not send email                   |
| SMTP send failure           | Retry once after 60 s; log full error if still failing  |
| Sanity check fails (1 retry)| Set null, log `[WARN]`, show `N/A` in email             |

---

## Customisation

- **Recipients:** edit the `python emailer.py ...` line in `.github/workflows/send-report.yml` (comma-separate for multiple)
- **Schedule:** change cron in the `/schedule` skill config (current: `30 3 * * *`)
- **Comparison window:** change D-8 to D-N in Step 1 date computation; update badge label (`"vs last week"`) in `email_renderer.py`
- **New metric:** add fetch queries in `agent_prompt.md` Steps 2/3, add `MetricPair` field to `ProjectMetrics`, add card in `_render_metrics_grid`
- **New project:** duplicate Steps 2–3 with new project ID; add third column to metrics grid

---

*Last updated: March 2026 · Maintained by Aditya / Hungama Product & Analytics*
