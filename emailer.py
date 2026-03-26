"""
SendGrid SMTP email sender.

Uses SendGrid's SMTP relay instead of the HTTP API, so it works in
restricted environments that block outbound HTTPS to api.sendgrid.com.

Tries port 465 (SMTPS/SSL) first, then falls back to port 587 (STARTTLS).

CLI usage:
  python emailer.py <html_file> <subject> <recipients_csv>

Env vars required:
  SENDGRID_API_KEY   — SendGrid API key (starts with SG.)
  SENDGRID_SENDER    — verified sender address in SendGrid
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

import os
from dotenv import load_dotenv

SMTP_HOST = "smtp.sendgrid.net"
SMTP_USER = "apikey"  # SendGrid SMTP username is always the literal string "apikey"


def send_report(
    html_body: str,
    subject: str,
    recipients: list[str],
    sender: str,
    api_key: str,
    logger: logging.Logger,
) -> bool:
    """
    Sends html_body as an HTML email via SendGrid SMTP relay.
    Retries once after 60 s on failure. Returns True on success.
    """
    for attempt in (1, 2):
        try:
            _attempt_send(html_body, subject, recipients, sender, api_key, logger)
            logger.info(f"[OK] Email sent to {', '.join(recipients)}")
            return True
        except Exception as exc:
            logger.error(f"[FAIL] Send attempt {attempt} failed: {exc}")
            if attempt == 1:
                logger.info("Retrying in 60 seconds...")
                time.sleep(60)

    return False


def _build_message(html_body: str, subject: str, sender: str, recipients: list[str]) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _attempt_send(
    html_body: str,
    subject: str,
    recipients: list[str],
    sender: str,
    api_key: str,
    logger: logging.Logger,
) -> None:
    msg = _build_message(html_body, subject, sender, recipients)
    raw = msg.as_string()

    # Try port 465 (SMTPS — SSL from the start) first
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, 465, context=ctx) as smtp:
            smtp.login(SMTP_USER, api_key)
            smtp.sendmail(sender, recipients, raw)
        logger.info("[SMTP] Sent via port 465 (SMTPS)")
        return
    except Exception as e465:
        logger.warning(f"[SMTP] Port 465 failed ({e465}), trying port 587 (STARTTLS)...")

    # Fall back to port 587 (STARTTLS)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, 587) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ctx)
        smtp.ehlo()
        smtp.login(SMTP_USER, api_key)
        smtp.sendmail(sender, recipients, raw)
    logger.info("[SMTP] Sent via port 587 (STARTTLS)")


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
