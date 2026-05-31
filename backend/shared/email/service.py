"""
Email Service — LinkUp Uganda (shared)
"""
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    from flask import current_app
    HAS_FLASK = True
except Exception:
    HAS_FLASK = False

logger = logging.getLogger(__name__)


def send_email(to_address: str, subject: str, html_body: str) -> bool:
    """Send a single email. Returns True on success."""
    try:
        username = current_app.config.get('MAIL_USERNAME', '')
        password = current_app.config.get('MAIL_PASSWORD', '')
        server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
        port = current_app.config.get('MAIL_PORT', 587)
        use_tls = current_app.config.get('MAIL_USE_TLS', True)
        use_ssl = current_app.config.get('MAIL_USE_SSL', False)
        from_name = current_app.config.get('MAIL_FROM_NAME', 'LinkUp Uganda')
        from_addr = current_app.config.get('MAIL_FROM_ADDRESS', username)
    except Exception:
        username = ''
        password = ''
        server = 'smtp.gmail.com'
        port = 587
        use_tls = True
        use_ssl = False
        from_name = 'LinkUp Uganda'
        from_addr = ''

    if not username or not password:
        logger.warning('[Email] SMTP not configured. Printing email to console.')
        print(f'\n{"=" * 60}')
        print(f'TO: {to_address}')
        print(f'SUBJECT: {subject}')
        print(html_body)
        print('=' * 60 + '\n')
        return True

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{from_name} <{from_addr}>'
    msg['To'] = to_address
    msg.attach(MIMEText(html_body, 'html'))

    try:
        context = ssl.create_default_context()
        if use_ssl:
            with smtplib.SMTP_SSL(server, port, context=context) as smtp:
                smtp.login(username, password)
                smtp.sendmail(from_addr, to_address, msg.as_string())
        else:
            with smtplib.SMTP(server, port) as smtp:
                if use_tls:
                    smtp.starttls(context=context)
                smtp.login(username, password)
                smtp.sendmail(from_addr, to_address, msg.as_string())
        return True
    except Exception as exc:
        logger.error(f'[Email] Failed to send email to {to_address}: {exc}')
        return False


def send_otp_email(to_address: str, name: str, code: str) -> bool:
    subject = 'Your LinkUp OTP Code'
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#1a1a2e">Your LinkUp Verification Code</h2>
      <p>Hi {name},</p>
      <p>Your one-time password is:</p>
      <p style="text-align:center;margin:32px 0;font-size:36px;font-weight:bold;
                letter-spacing:8px;color:#f6b93b">{code}</p>
      <p style="color:#666;font-size:13px">This code expires in 10 minutes.
         Do not share it with anyone.</p>
    </div>
    """
    return send_email(to_address, subject, html)
