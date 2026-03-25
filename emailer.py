"""
Gmail SMTP sender.

CLI usage (called by the Claude Code agent):
  python emailer.py <html_file> <subject> <recipients_csv>

Example:
  python emailer.py report.html "Daily OTT Report" "a@b.com,c@d.com"
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
import os


def send_report(
    html_body: str,
    subject: str,
    recipients: list[str],
    sender: str,
    app_password: str,
    logger: logging.Logger,
) -> bool:
    """
    Sends html_body as an HTML email via Gmail SMTP (port 587, STARTTLS).
    Retries once after 60 s on failure. Returns True on success.
    """
    msg = _build_message(html_body, subject, sender, recipients)

    for attempt in (1, 2):
        try:
            _attempt_send(msg, sender, recipients, app_password)
            logger.info(f"[✓] Email sent to {', '.join(recipients)}")
            return True
        except Exception as exc:
            logger.error(f"[✗] Send attempt {attempt} failed: {exc}")
            if attempt == 1:
                logger.info("Retrying in 60 seconds...")
                time.sleep(60)

    return False


def _build_message(html_body, subject, sender, recipients):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _attempt_send(msg, sender, recipients, app_password):
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ctx)
        smtp.login(sender, app_password)
        smtp.sendmail(sender, recipients, msg.as_string())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python emailer.py <html_file> <subject> <recipients_csv>")
        sys.exit(1)

    html_file, subject, recipients_csv = sys.argv[1], sys.argv[2], sys.argv[3]

    load_dotenv()
    sender       = os.environ.get("GMAIL_SENDER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not sender or not app_password:
        print("ERROR: GMAIL_SENDER and GMAIL_APP_PASSWORD must be set in .env")
        sys.exit(1)

    html_body  = Path(html_file).read_text(encoding="utf-8")
    recipients = [r.strip() for r in recipients_csv.split(",") if r.strip()]

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("emailer")

    ok = send_report(html_body, subject, recipients, sender, app_password, logger)
    sys.exit(0 if ok else 1)
