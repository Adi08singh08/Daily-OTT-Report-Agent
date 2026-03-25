"""
SendGrid email sender.

CLI usage (called by the Claude Code agent):
  python emailer.py <html_file> <subject> <recipients_csv>

Example:
  python emailer.py report.html "Daily OTT Report" "a@b.com,c@d.com"

Env vars required:
  SENDGRID_API_KEY   — SendGrid API key (starts with SG.)
  SENDGRID_SENDER    — verified sender address in SendGrid
  REPORT_RECIPIENTS  — comma-separated recipient addresses (used as default if not passed via CLI)
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
import os

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, To
except ImportError:
    sendgrid = None  # type: ignore


def send_report(
    html_body: str,
    subject: str,
    recipients: list[str],
    sender: str,
    api_key: str,
    logger: logging.Logger,
) -> bool:
    """
    Sends html_body as an HTML email via SendGrid API.
    Retries once after 60 s on failure. Returns True on success.
    """
    if sendgrid is None:
        logger.error("[✗] sendgrid package not installed. Run: pip install sendgrid")
        return False

    for attempt in (1, 2):
        try:
            _attempt_send(html_body, subject, recipients, sender, api_key)
            logger.info(f"[✓] Email sent to {', '.join(recipients)}")
            return True
        except Exception as exc:
            logger.error(f"[✗] Send attempt {attempt} failed: {exc}")
            if attempt == 1:
                logger.info("Retrying in 60 seconds...")
                time.sleep(60)

    return False


def _attempt_send(html_body, subject, recipients, sender, api_key):
    sg = sendgrid.SendGridAPIClient(api_key=api_key)
    message = Mail(
        from_email=sender,
        to_emails=[To(r) for r in recipients],
        subject=subject,
        html_content=html_body,
    )
    response = sg.send(message)
    if response.status_code not in (200, 202):
        raise RuntimeError(f"SendGrid returned HTTP {response.status_code}: {response.body}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python emailer.py <html_file> <subject> <recipients_csv>")
        sys.exit(1)

    html_file, subject, recipients_csv = sys.argv[1], sys.argv[2], sys.argv[3]

    load_dotenv()
    api_key = os.environ.get("SENDGRID_API_KEY")
    sender  = os.environ.get("SENDGRID_SENDER")

    if not api_key or not sender:
        print("ERROR: SENDGRID_API_KEY and SENDGRID_SENDER must be set in .env")
        sys.exit(1)

    html_body  = Path(html_file).read_text(encoding="utf-8")
    recipients = [r.strip() for r in recipients_csv.split(",") if r.strip()]

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("emailer")

    ok = send_report(html_body, subject, recipients, sender, api_key, logger)
    sys.exit(0 if ok else 1)
