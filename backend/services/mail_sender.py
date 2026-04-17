import email as email_lib
import imaplib
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

logger = logging.getLogger(__name__)


def _fetch_real_message_id(settings: dict) -> str | None:
    """After sending via SMTP, fetch the real Message-ID of the LAST
    message in the Sent folder. Aruba rewrites Message-IDs."""
    try:
        server = settings.get("imap_server", "")
        port = int(settings.get("imap_port", "993"))
        user = settings.get("imap_user", "")
        password = settings.get("imap_password", "")

        conn = imaplib.IMAP4_SSL(server, port, timeout=15)
        conn.login(user, password)

        # Try common Sent folder names
        sent_folder = None
        for name in ("INBOX.Sent", "Sent", "Posta inviata"):
            try:
                typ, _ = conn.select(name, readonly=True)
                if typ == "OK":
                    sent_folder = name
                    break
            except Exception:
                continue

        if not sent_folder:
            conn.logout()
            return None

        _, data = conn.search(None, "ALL")
        uids = data[0].split() if data[0] else []
        if not uids:
            conn.logout()
            return None

        # Get the LAST message (most recently sent)
        _, hdata = conn.fetch(uids[-1], "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        if hdata and isinstance(hdata[0], tuple):
            msg = email_lib.message_from_bytes(hdata[0][1])
            mid = msg.get("Message-ID", "").strip().strip("<>")
            conn.logout()
            if mid:
                logger.info("Real Message-ID from Sent: %s", mid)
                return mid

        conn.logout()
    except Exception as ex:
        logger.warning("Could not fetch real Message-ID from Sent: %s", ex)
    return None


def send_email(
    to_addr: str,
    subject: str,
    body: str,
    settings: dict,
    reply_to_message_id: str | None = None,
) -> str:
    """Send an email via SMTP with TLS.

    *settings* must contain smtp_server, smtp_port, smtp_user, smtp_password,
    email_mittente.

    Returns the new Message-ID of the sent email.
    Raises on failure so callers can handle errors explicitly.
    """
    smtp_server = settings.get("smtp_server", "")
    smtp_port = int(settings.get("smtp_port", "587"))
    smtp_user = settings.get("smtp_user", "")
    smtp_password = settings.get("smtp_password", "")
    from_addr = settings.get("email_mittente", smtp_user)

    msg = MIMEMultipart("alternative")
    new_message_id = make_msgid(domain=from_addr.split("@")[-1] if "@" in from_addr else "localhost")
    msg["Message-ID"] = new_message_id
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Date"] = formatdate(localtime=True)

    # Threading headers
    if reply_to_message_id:
        msg["In-Reply-To"] = reply_to_message_id
        msg["References"] = reply_to_message_id

    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Port 465 = SSL diretto (Aruba), port 587 = STARTTLS
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
    else:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, [to_addr], msg.as_string())

    logger.info("Mail inviata a %s — %s (local ID: %s)", to_addr, subject, new_message_id)

    # Wait briefly then fetch real Message-ID from Sent folder
    # (Aruba SMTP rewrites Message-IDs)
    time.sleep(2)
    real_mid = _fetch_real_message_id(settings)
    if real_mid:
        return real_mid

    # Fallback to our generated ID (stripped of angle brackets)
    return new_message_id.strip("<>")


def test_smtp(settings: dict) -> dict:
    """Test SMTP connection. Returns {"ok": True} or {"ok": False, "error": "..."}."""
    try:
        smtp_server = settings.get("smtp_server", "")
        smtp_port = int(settings.get("smtp_port", "587"))
        smtp_user = settings.get("smtp_user", "")
        smtp_password = settings.get("smtp_password", "")

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15) as server:
                server.login(smtp_user, smtp_password)
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_password)

        return {"ok": True}
    except Exception as e:
        logger.error("Test SMTP fallito: %s", e)
        return {"ok": False, "error": str(e)}


def test_imap(settings: dict) -> dict:
    """Test IMAP connection. Returns {"ok": True} or {"ok": False, "error": "..."}."""
    try:
        imap_server = settings.get("imap_server", "")
        imap_port = int(settings.get("imap_port", "993"))
        imap_user = settings.get("imap_user", "")
        imap_password = settings.get("imap_password", "")

        conn = imaplib.IMAP4_SSL(imap_server, imap_port)
        conn.login(imap_user, imap_password)
        conn.logout()

        return {"ok": True}
    except Exception as e:
        logger.error("Test IMAP fallito: %s", e)
        return {"ok": False, "error": str(e)}
