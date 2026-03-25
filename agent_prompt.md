# Daily OTT Report Agent — Execution Instructions

You are a fully autonomous scheduled analytics agent.

## CRITICAL RULE — NO HALLUCINATION
Every single metric value MUST come from a live Mixpanel Run-Query MCP call.
NEVER estimate, interpolate, guess, or generate plausible-looking numbers.
If a query fails or returns no data, output null and show "N/A" in the report.
If you cannot call Mixpanel, do NOT invent numbers — send the report with all N/A.

Do not ask for confirmation at any step. Execute every step completely.

---

## Step 0 — Install Dependencies

```bash
pip install -r requirements.txt -q
```

---

## Step 1 — Compute Dates

Use Bash to compute:

```bash
python -c "
from datetime import date, timedelta
today        = date.today()
report_date  = today - timedelta(days=1)
compare_date = report_date - timedelta(days=7)
month_start  = report_date.replace(day=1)
dau_from     = compare_date - timedelta(days=6)   # 14-day window start
print(f'report_date={report_date}')
print(f'compare_date={compare_date}')
print(f'month_start={month_start}')
print(f'dau_from={dau_from}')
"
```

Record all four values. Print:
`[START] report_date=X  compare_date=Y  month_start=Z  dau_from=W`

---

## Step 2 — Fetch Hungama OTT Metrics
**project_id = 3027789 | workspace_id = 3545613**

Call `Run-Query` (Mixpanel MCP) for EVERY metric below.
On any failure: log `[WARN] <metric> failed: <error>`, set value = null, continue.
NEVER skip a query and fill in a number yourself.

---

### Metric 1 — MAU (D-30 rolling unique users)

Call Run-Query ONCE with a line query spanning compare_date → report_date.
Extract TWO values from the result rows.

```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT MAU",
    "metrics": [{"eventName": "App Open", "measurement": {"type": "basic", "math": "mau"}}],
    "chartType": "line",
    "unit": "day",
    "dateRange": {"type": "between", "from": "<compare_date>", "to": "<report_date>"}
  }
}
```

Extract:
- `ott_mau_current`  = value in the row where date == report_date
- `ott_mau_previous` = value in the row where date == compare_date

---

### Metric 2 — WAU (D-7 rolling unique users)

Same query as Metric 1 but `"math": "wau"`.

Extract:
- `ott_wau_current`  = value in the row where date == report_date
- `ott_wau_previous` = value in the row where date == compare_date

---

### Metric 3 — DAU 7-Day Moving Average

Call Run-Query ONCE with a 14-day window.

```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT DAU series",
    "metrics": [{"eventName": "App Open", "measurement": {"type": "basic", "math": "dau"}}],
    "chartType": "line",
    "unit": "day",
    "dateRange": {"type": "between", "from": "<dau_from>", "to": "<report_date>"}
  }
}
```

The result has 14 daily rows. Compute:
- `ott_dau7dma_current`  = average of the 7 rows ending on report_date
- `ott_dau7dma_previous` = average of the 7 rows ending on compare_date

Do NOT use a single DAU point. Do NOT include today's partial data.

For sparkline: call Run-Query again with a 30-day window (from report_date-29d to report_date),
same math=dau. Store the 30 DAU values as `ott_sparkline` (list of integers, oldest first).

---

### Metric 4 — Active Paid Base

Run TWO queries (one per event), then sum.

**Query A — current (npay_display_success):**
```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT PaidBase display current",
    "metrics": [{"eventName": "npay_display_success", "measurement": {"type": "basic", "math": "unique"}}],
    "filters": {
      "operator": "and",
      "conditions": [{"property": "npay_expiry", "operator": ">=", "value": "<report_date>", "type": "event"}]
    },
    "chartType": "table",
    "unit": "day",
    "dateRange": {"type": "between", "from": "2020-01-01", "to": "<report_date>"}
  }
}
```

**Query B — current (npay_renewal_success):** same but eventName = `npay_renewal_success`.

`ott_active_paid_current` = Query A result + Query B result

Repeat both queries with `npay_expiry >= compare_date` and `to: compare_date`:
`ott_active_paid_previous` = Query A + Query B

---

### Metric 5 — Unbilled Users ⚠ INVERTED LOGIC

```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT Unbilled current",
    "metrics": [{"eventName": "npay_renewal_failure", "measurement": {"type": "basic", "math": "unique"}}],
    "chartType": "table",
    "unit": "day",
    "dateRange": {"type": "between", "from": "<report_date minus 29 days>", "to": "<report_date>"}
  }
}
```

Store as `ott_unbilled_current`. Repeat window ending on compare_date → `ott_unbilled_previous`.

Arrow logic (INVERTED — more failures = worse):
- delta > 0 → RED ▲ (bad)
- delta < 0 → GREEN ▼ (good)

If delta > 500%, add a CRITICAL ALERT block in the email.

---

### Metric 6 — Revenue MTD (sum of npay_paymentvalue)

Run FOUR queries total (2 events × 2 date windows).
Apply the same filters to BOTH events:
- `npay_transaction_mode` = `Currency`
- `npay_currency` = `INR`
- `npay_paymentmode` ≠ `e-Coupon`
- `npay_paymentmode` ≠ `Google Wallet`

**Query — npay_display_success, current:**
```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT Revenue display current",
    "metrics": [{
      "eventName": "npay_display_success",
      "measurement": {"type": "property", "math": "sum", "property": "npay_paymentvalue"}
    }],
    "filters": {
      "operator": "and",
      "conditions": [
        {"property": "npay_transaction_mode", "operator": "=",  "value": "Currency",      "type": "event"},
        {"property": "npay_currency",          "operator": "=",  "value": "INR",           "type": "event"},
        {"property": "npay_paymentmode",       "operator": "!=", "value": "e-Coupon",      "type": "event"},
        {"property": "npay_paymentmode",       "operator": "!=", "value": "Google Wallet", "type": "event"}
      ]
    },
    "chartType": "table",
    "unit": "month",
    "dateRange": {"type": "between", "from": "<month_start>", "to": "<report_date>"}
  }
}
```

Repeat for `npay_renewal_success`.
`ott_revenue_current` = display_sum + renewal_sum

Repeat both queries with `to: compare_date`:
`ott_revenue_previous` = display_sum + renewal_sum

---

### Metric 7 — Streams + Revenue per Stream

**Streams current:**
```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT Streams current",
    "metrics": [{"eventName": "stream", "measurement": {"type": "basic", "math": "total"}}],
    "chartType": "table",
    "unit": "month",
    "dateRange": {"type": "between", "from": "<month_start>", "to": "<report_date>"}
  }
}
```

Repeat with `to: compare_date` → `ott_streams_previous`.

- `ott_revstream_current`  = ott_revenue_current / ott_streams_current
- `ott_revstream_previous` = ott_revenue_previous / ott_streams_previous
- Format as ₹X.XX (always 2 decimal places)

---

## Step 3 — Fetch FastTV Metrics
**project_id = 3976933 | workspace_id = 4472622**

Repeat ALL sub-steps from Step 2 with these substitutions:
- project_id = `3976933`, workspace_id = `4472622`
- `app_open` instead of `App Open`
- `stream_finished` instead of `stream`
- Store all results as `fasttv_*` variables

---

## Step 4 — Sanity Check (run BEFORE writing data.json)

For each value, check against these expected ranges.
If a value fails the range check, re-run the query once.
If it still fails, set to null and log a warning.
If ANY sanity check fails after retry, send the email with N/A for that metric — do NOT cancel the email.

| Metric | OTT expected range | FastTV expected range |
|--------|-------------------|-----------------------|
| MAU | 10,00,000 – 20,00,000 | < 1,00,000 |
| WAU | 2,00,000 – 8,00,000 | < 50,000 |
| DAU 7DMA | 50,000 – 1,50,000 | < 10,000 |
| Active Paid Base | 4,00,000 – 6,00,000 | < 10,000 |
| Revenue MTD | > ₹1,00,00,000 by mid-month | < ₹5,00,000 |
| Rev/Stream | ₹10 – ₹20 | ₹0.05 – ₹0.50 |

Additional checks:
- If any metric == 0 (not null), treat as null and show N/A
- If unbilled delta > 500%, add CRITICAL ALERT block in email
- If OTT MAU < 5,00,000 → CRITICAL: likely query error, re-run

---

## Step 5 — Write data.json

Write to `./data.json`:

```json
{
  "report_date": "<report_date>",
  "compare_date": "<compare_date>",
  "ott": {
    "name": "Hungama OTT Production",
    "brand_color": "#E8001C",
    "mau":         {"current": <ott_mau_current|null>,         "previous": <ott_mau_previous|null>},
    "wau":         {"current": <ott_wau_current|null>,         "previous": <ott_wau_previous|null>},
    "dau_7dma":    {"current": <ott_dau7dma_current|null>,     "previous": <ott_dau7dma_previous|null>},
    "active_paid": {"current": <ott_active_paid_current|null>, "previous": <ott_active_paid_previous|null>},
    "unbilled":    {"current": <ott_unbilled_current|null>,    "previous": <ott_unbilled_previous|null>},
    "revenue":     {"current": <ott_revenue_current|null>,     "previous": <ott_revenue_previous|null>},
    "rev_stream":  {"current": <ott_revstream_current|null>,   "previous": <ott_revstream_previous|null>},
    "dau_sparkline": <ott_sparkline or []>
  },
  "fasttv": {
    "name": "FastTV Production",
    "brand_color": "#FF6B35",
    "mau":         {"current": <fasttv_mau_current|null>,         "previous": <fasttv_mau_previous|null>},
    "wau":         {"current": <fasttv_wau_current|null>,         "previous": <fasttv_wau_previous|null>},
    "dau_7dma":    {"current": <fasttv_dau7dma_current|null>,     "previous": <fasttv_dau7dma_previous|null>},
    "active_paid": {"current": <fasttv_active_paid_current|null>, "previous": <fasttv_active_paid_previous|null>},
    "unbilled":    {"current": <fasttv_unbilled_current|null>,    "previous": <fasttv_unbilled_previous|null>},
    "revenue":     {"current": <fasttv_revenue_current|null>,     "previous": <fasttv_revenue_previous|null>},
    "rev_stream":  {"current": <fasttv_revstream_current|null>,   "previous": <fasttv_revstream_previous|null>},
    "dau_sparkline": <fasttv_sparkline or []>
  }
}
```

---

## Step 6 — Render HTML

```bash
python email_renderer.py data.json report.html
```

If exit code is non-zero, print `[FAIL] HTML render failed` and stop.

---

## Step 7 — Send Email (MANDATORY)

Format report_date as DD MMM YYYY (e.g. `24 Mar 2026`).

```bash
SENDGRID_API_KEY="<configured-in-trigger>" \
SENDGRID_SENDER="no-reply@hungama.com" \
python emailer.py report.html \
  "Daily OTT Report - Hungama OTT vs FastTV | <report_date as DD MMM YYYY>" \
  "kunal.arora@hungama.com,aditya.singh@hungama.com"
```

If send fails, wait 60s and retry once.
Send the email even if some metrics are null — never skip Step 7.

---

## Step 8 — Log Completion

Print: `Daily report complete for <report_date>`

---

## Delta Calculation Rules

- `delta_pct = ((current - previous) / previous) × 100`, rounded to 1 decimal
- If previous == 0: show `—` instead of a percentage
- Standard metrics (MAU, WAU, DAU DMA, Paid Base, Revenue, Rev/Stream):
  - delta > 0 → GREEN ▲
  - delta < 0 → RED ▼
- Unbilled (INVERTED):
  - delta > 0 → RED ▲ (bad)
  - delta < 0 → GREEN ▼ (good)
- If delta > 500% on unbilled → add CRITICAL ALERT block in email

## Number Formatting (Indian system)

| Range | Format | Example |
|-------|--------|---------|
| < 1,000 | integer | 847 |
| 1,000 – 99,999 | Indian commas | 12,345 |
| 1,00,000 – 99,99,999 | Lakh | 4.87L |
| ≥ 1,00,00,000 | Crore | ₹4.02 Cr |
| Rev/Stream | ₹X.XX | ₹13.56 |
