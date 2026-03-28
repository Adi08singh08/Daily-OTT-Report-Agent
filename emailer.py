"""
SMTP email sender (Outlook / Office 365).

Works with smtp.office365.com:587 (STARTTLS) using your Outlook credentials.
No external library needed — uses stdlib smtplib only.

CLI usage:
  python emailer.py <html_file> <subject> <recipients_csv>

Env vars required:
  SMTP_USER      — your Outlook email address (e.g. aditya.singh@hungama.com)
  SMTP_PASSWORD  — your Outlook password or app password
"""
from __future__ import annotations

import logging
import os
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587


def send_report(
    html_body: str,
    subject: str,
    recipients: list[str],
    sender: str,
    password: str,
    logger: logging.Logger,
) -> bool:
    for attempt in (1, 2):
        try:
            _attempt_send(html_body, subject, recipients, sender, password)
            logger.info(f"[OK] Email sent to {', '.join(recipients)}")
            return True
        except Exception as exc:
            logger.error(f"[FAIL] Send attempt {attempt} failed: {exc}")
            if attempt == 1:
                logger.info("Retrying in 60 seconds...")
                time.sleep(60)

    return False


def _attempt_send(html_body, subject, recipients, sender, password):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python emailer.py <html_file> <subject> <recipients_csv>")
        sys.exit(1)

    html_file, subject, recipients_csv = sys.argv[1], sys.argv[2], sys.argv[3]

    load_dotenv()
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if not smtp_user or not smtp_password:
        print("ERROR: SMTP_USER and SMTP_PASSWORD must be set in .env")
        sys.exit(1)

    html_body = Path(html_file).read_text(encoding="utf-8")
    recipients = [r.strip() for r in recipients_csv.split(",") if r.strip()]

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("emailer")

    ok = send_report(html_body, subject, recipients, smtp_user, smtp_password, logger)
    sys.exit(0 if ok else 1)
