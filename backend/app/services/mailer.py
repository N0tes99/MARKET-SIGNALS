"""Generic SMTP mailer (shared by alerts and auth verification)."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    """True when SMTP host + user are set."""
    return bool(settings.alert_smtp_host.strip() and settings.alert_smtp_user.strip())


def send_mail(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email via ALERT_SMTP_* settings. Returns True on success."""
    host = settings.alert_smtp_host.strip()
    user = settings.alert_smtp_user.strip()
    password = settings.alert_smtp_password
    to_addr = to.strip()
    if not (to_addr and host and user):
        logger.warning("SMTP not configured; skipping email to %s", to_addr or "(empty)")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.alert_email_from.strip() or user
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        if settings.alert_smtp_use_tls:
            with smtplib.SMTP(host, settings.alert_smtp_port, timeout=15) as server:
                server.starttls()
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, settings.alert_smtp_port, timeout=15) as server:
                server.login(user, password)
                server.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_addr)
        return False
