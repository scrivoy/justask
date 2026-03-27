"""Utility functions for justask."""

import json
import os
import secrets
from flask import session, request, abort, current_app


# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

def get_ui_texts():
    """Load UI translations from locales/ui.json. Returns (dict, lang_string)."""
    lang = session.get('lang', os.environ.get('DEFAULT_LANGUAGE', 'de'))
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, 'locales/ui.json'), 'r', encoding='utf-8') as f:
            return json.load(f), lang
    except Exception:
        return {}, lang


def get_questions():
    """Load questions from locales/questions.json. Returns list of question dicts."""
    lang = session.get('lang', os.environ.get('DEFAULT_LANGUAGE', 'de'))
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, 'locales/questions.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('questions', [])
    except Exception:
        return []


def t(key, **kwargs):
    """Translate a UI key to the current session language. Supports {placeholders}."""
    texts, _ = get_ui_texts()
    text = texts.get(key, {})
    lang = session.get('lang', os.environ.get('DEFAULT_LANGUAGE', 'de'))
    value = text.get(lang, key)
    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value
    return value


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

def csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf():
    token = request.form.get('csrf_token', '')
    session_token = session.get('_csrf_token', '')
    if not token or token != session_token:
        abort(403)


# ---------------------------------------------------------------------------
# Authentication decorators
# ---------------------------------------------------------------------------

def require_staff(f):
    """Decorator: require staff or admin session."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('staff_logged_in') and not session.get('admin_logged_in'):
            from flask import redirect, url_for
            return redirect(url_for('intranet.login'))
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    """Decorator: require admin session."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            from flask import redirect, url_for
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)

    return decorated


# ---------------------------------------------------------------------------
# URL + QR helpers
# ---------------------------------------------------------------------------

def get_customer_link(token):
    """Build the public feedback URL for a given form token."""
    base_url = os.environ.get('BASE_URL', '').rstrip('/')
    if base_url:
        return f"{base_url}/form/{token}"
    from flask import url_for
    return url_for('customer.form', token=token, _external=True)


def generate_qr_base64(url):
    """Generate a QR code PNG as base64 string."""
    import qrcode
    from io import BytesIO
    import base64

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------

def send_notification(form):
    """Send email and/or webhook notification for a completed feedback form.
    Called after feedback is saved. Failures are logged but never raise."""
    _send_email_notification(form)
    _send_webhook_notification(form)


def _send_email_notification(form):
    """Send email if NOTIFICATION_EMAIL is configured."""
    email = os.environ.get('NOTIFICATION_EMAIL', '').strip()
    if not email:
        return
    try:
        import smtplib
        from email.mime.text import MIMEText

        offer = form.offer

        subject = f"Neues Feedback: {offer.offer_number} - {offer.title}"
        body = (
            f"Angebot: {offer.offer_number} - {offer.title}\n"
            f"Projektleiter: {offer.leader_name}\n"
            f"Ausgefuellt am: {form.completed_at}\n"
        )

        smtp_user = os.environ.get('SMTP_USER', '')
        smtp_from = os.environ.get('SMTP_FROM', '').strip() or smtp_user or email

        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = email

        smtp_host = os.environ.get('SMTP_HOST', 'localhost')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_pass = os.environ.get('SMTP_PASSWORD', '')

        # Port 465 uses implicit TLS, port 587 uses STARTTLS.
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            if smtp_port == 587:
                server.starttls()

        with server:
            if smtp_user and smtp_pass:
                try:
                    server.login(smtp_user, smtp_pass)
                except UnicodeEncodeError:
                    # Fallback for non-ASCII passwords (e.g. umlauts):
                    # manually send AUTH PLAIN with UTF-8 encoding.
                    import base64
                    auth_string = f'\0{smtp_user}\0{smtp_pass}'
                    auth_b64 = base64.b64encode(
                        auth_string.encode('utf-8')
                    ).decode('ascii')
                    code, resp = server.docmd('AUTH', f'PLAIN {auth_b64}')
                    if code not in (235, 503):
                        raise smtplib.SMTPAuthenticationError(code, resp)
            server.send_message(msg)
    except Exception:
        current_app.logger.exception("Email notification failed")


def _send_webhook_notification(form):
    """Send webhook POST if NOTIFICATION_WEBHOOK_URL is configured."""
    webhook_url = os.environ.get('NOTIFICATION_WEBHOOK_URL', '').strip()
    if not webhook_url:
        return
    try:
        import urllib.request
        import json as json_module

        offer = form.offer

        text = (
            f"Neues Feedback eingegangen:\n"
            f"Angebot: {offer.offer_number} - {offer.title}\n"
            f"Projektleiter: {offer.leader_name}"
        )

        payload = json_module.dumps({"text": text}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}

        webhook_token = os.environ.get('NOTIFICATION_WEBHOOK_TOKEN', '').strip()
        if webhook_token:
            headers['X-Auth-Token'] = webhook_token

        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers=headers
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        current_app.logger.exception("Webhook notification failed")
