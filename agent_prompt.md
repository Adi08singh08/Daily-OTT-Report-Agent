# Daily OTT Report Agent — Execution Instructions

You are running as an autonomous scheduled agent. Execute the steps below silently and completely. Do not ask for confirmation at any step. If a single metric fails, use `null` for that value and continue.

---

## Project Directory
`c:\Users\aditya.singh\Desktop\AI project\Daily OTT Report Agent`

---

## Step 1 — Compute Dates

```python
from datetime import date, timedelta
today        = date.today()
report_date  = today - timedelta(days=1)          # yesterday  (D-1)
compare_date = report_date - timedelta(days=7)    # D-8
month_start  = report_date.replace(day=1)         # 1st of current month
```

Log: `[START] report_date={report_date}  compare_date={compare_date}  month_start={month_start}`

---

## Step 2 — Fetch Hungama OTT Metrics

**Project ID:** `3027789` | **Workspace ID:** `3545613`
**App Open event:** `App Open` | **Stream event:** `stream`

### 2a. MAU — rolling 30-day unique users of "App Open"

Run two queries (one for each date window):

```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT MAU current",
    "metrics": [{
      "eventName": "App Open",
      "measurement": { "type": "basic", "math": "mau" }
    }],
    "chartType": "table",
    "unit": "day",
    "dateRange": { "type": "between", "from": "{report_date}", "to": "{report_date}" }
  }
}
```

Repeat with `"from": "{compare_date}", "to": "{compare_date}"` for the previous value.
Extract: the single numeric value for the date. Store as `ott.mau.current` and `ott.mau.previous`.

### 2b. WAU — rolling 7-day unique users of "App Open"

Same as 2a but use `"math": "wau"`.

### 2c. DAU 7-Day Moving Average

Fetch DAU (daily unique users) over a 14-day window:

```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT DAU series",
    "metrics": [{
      "eventName": "App Open",
      "measurement": { "type": "basic", "math": "dau" }
    }],
    "chartType": "line",
    "unit": "day",
    "dateRange": { "type": "between", "from": "{compare_date - 6 days}", "to": "{report_date}" }
  }
}
```

Compute:
- `dau_7dma.current`  = average of DAU values for the 7 days ending on `report_date`
- `dau_7dma.previous` = average of DAU values for the 7 days ending on `compare_date`

For **sparkline**: fetch DAU over 30 days ending on `report_date` and store as an ordered list of integers (oldest → newest) in `ott.dau_sparkline`.

### 2d. Active Paid Base

Unique users who performed `npay_display_success` OR `npay_renewal_success` and whose `npay_expiry` property is >= `{report_date}`.

Run an insights query with a formula (A+B unique users):

```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT Active Paid Base current",
    "metrics": [
      { "eventName": "npay_display_success",  "measurement": { "type": "basic", "math": "unique" } },
      { "eventName": "npay_renewal_success",  "measurement": { "type": "basic", "math": "unique" } }
    ],
    "filters": {
      "operator": "and",
      "conditions": [
        { "property": "npay_expiry", "operator": ">=", "value": "{report_date}", "type": "event" }
      ]
    },
    "chartType": "table",
    "unit": "day",
    "dateRange": { "type": "between", "from": "2020-01-01", "to": "{report_date}" }
  }
}
```

If the MCP does not support combining two events into a union of unique users in one query, run each event separately and sum the unique user counts (note: this slightly over-counts users who did both events — acceptable approximation).

Repeat with `to: "{compare_date}"` and `npay_expiry >= "{compare_date}"` for the previous value.

### 2e. Unbilled Users — npay_renewal_failure (rolling 30 days)

```json
{
  "report_type": "insights",
  "project_id": 3027789,
  "workspace_id": 3545613,
  "report": {
    "name": "OTT Unbilled current",
    "metrics": [{
      "eventName": "npay_renewal_failure",
      "measurement": { "type": "basic", "math": "unique" }
    }],
    "chartType": "table",
    "unit": "day",
    "dateRange": { "type": "between", "from": "{report_date - 29 days}", "to": "{report_date}" }
  }
}
```

Sum the unique users across the 30-day window (or use the total if the MCP returns a single aggregate).
Repeat the 30-day window ending on `compare_date` for previous.

### 2f. Revenue — sum of npay_paymentvalue

Apply these filters to **both** `npay_display_success` and `npay_renewal_success`:
- `npay_transaction_mode` = `Currency`
- `npay_currency` = `INR`
- `npay_paymentmode` ≠ `e-Coupon`
- `npay_paymentmode` ≠ `Google Wallet`

Date range: `month_start → report_date` (current), `month_start → compare_date` (previous).

Query each event separately with a `sum` measurement on `npay_paymentvalue`, then add them together.

```json
{
  "metrics": [{
    "eventName": "npay_display_success",
    "measurement": { "type": "property", "math": "sum", "property": "npay_paymentvalue" }
  }],
  "filters": {
    "operator": "and",
    "conditions": [
      { "property": "npay_transaction_mode", "operator": "=",  "value": "Currency",      "type": "event" },
      { "property": "npay_currency",          "operator": "=",  "value": "INR",           "type": "event" },
      { "property": "npay_paymentmode",       "operator": "!=", "value": "e-Coupon",      "type": "event" },
      { "property": "npay_paymentmode",       "operator": "!=", "value": "Google Wallet", "type": "event" }
    ]
  },
  "chartType": "table",
  "unit": "month",
  "dateRange": { "type": "between", "from": "{month_start}", "to": "{report_date}" }
}
```

Repeat for `npay_renewal_success`. Sum both event totals → `ott.revenue.current`.
Repeat entire calculation with `to: "{compare_date}"` → `ott.revenue.previous`.

### 2g. Stream Count + Revenue per Stream

```json
{
  "metrics": [{
    "eventName": "stream",
    "measurement": { "type": "basic", "math": "total" }
  }],
  "chartType": "table",
  "unit": "month",
  "dateRange": { "type": "between", "from": "{month_start}", "to": "{report_date}" }
}
```

- `ott.rev_stream.current`  = `ott.revenue.current / stream_count_current`
- `ott.rev_stream.previous` = `ott.revenue.previous / stream_count_previous`

---

## Step 3 — Fetch FastTV Metrics

**Project ID:** `3976933` | **Workspace ID:** `4472622`
**App Open event:** `app_open` | **Stream event:** `stream_finished`

Repeat all sub-steps from Step 2 with:
- Project ID `3976933` and Workspace ID `4472622`
- `app_open` instead of `App Open`
- `stream_finished` instead of `stream`
- Same payment events and filters

---

## Step 4 — Write data.json

Write the following JSON to:
`c:\Users\aditya.singh\Desktop\AI project\Daily OTT Report Agent\data.json`

```json
{
  "report_date": "{report_date}",
  "compare_date": "{compare_date}",
  "ott": {
    "name": "Hungama OTT Production",
    "brand_color": "#E8001C",
    "mau":         { "current": <number|null>, "previous": <number|null> },
    "wau":         { "current": <number|null>, "previous": <number|null> },
    "dau_7dma":    { "current": <number|null>, "previous": <number|null> },
    "active_paid": { "current": <number|null>, "previous": <number|null> },
    "unbilled":    { "current": <number|null>, "previous": <number|null> },
    "revenue":     { "current": <number|null>, "previous": <number|null> },
    "rev_stream":  { "current": <number|null>, "previous": <number|null> },
    "dau_sparkline": [<30 integers, oldest to newest>]
  },
  "fasttv": {
    "name": "FastTV Production",
    "brand_color": "#FF6B35",
    "mau":         { "current": <number|null>, "previous": <number|null> },
    "wau":         { "current": <number|null>, "previous": <number|null> },
    "dau_7dma":    { "current": <number|null>, "previous": <number|null> },
    "active_paid": { "current": <number|null>, "previous": <number|null> },
    "unbilled":    { "current": <number|null>, "previous": <number|null> },
    "revenue":     { "current": <number|null>, "previous": <number|null> },
    "rev_stream":  { "current": <number|null>, "previous": <number|null> },
    "dau_sparkline": [<30 integers, oldest to newest>]
  }
}
```

---

## Step 5 — Render HTML

Run from the project directory:
```bash
cd "c:\Users\aditya.singh\Desktop\AI project\Daily OTT Report Agent"
python email_renderer.py data.json report.html
```

Confirm output: `[✓] Report written to report.html`

---

## Step 6 — Send Email via Gmail MCP

Read `report.html`, then use the Gmail MCP `send_email` tool:
- **To:** `[CONFIGURE_RECIPIENT_EMAIL_HERE]`
- **Subject:** `📊 Daily OTT Report — Hungama OTT vs FastTV | {report_date formatted as DD MMM YYYY}`
- **Body:** the full HTML content of `report.html`
- **Content-Type:** HTML

Confirm: `[✓] Email sent to [recipient]`

---

## Step 7 — Log Completion

Print: `✅ Daily report complete for {report_date}`

If email fails after retry: print `[✗] Email delivery failed. HTML saved at report.html for manual inspection.` and exit with error.

---

## Error Handling

- Any single Mixpanel query fails → log `[⚠] {metric} failed: {error}`, set value to `null`, continue.
- If **all** Mixpanel queries fail for **both** projects → log `[✗] All data unavailable. Report not sent.` and stop.
- If `data.json` write fails → log error and stop.
- If HTML render fails → log error and stop.
- If email fails → retry once after 60 s. If still failing, log and stop.
