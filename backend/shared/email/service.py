"""
LinkUp Email Service — SMTP via Gmail (STARTTLS port 587).
Credentials: info@mru.ac.ug  |  App Password from .env
All sends are async (daemon thread) so they never block a request.
"""
import smtplib
import ssl
import logging
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from flask import request, has_request_context

logger = logging.getLogger(__name__)


# ─── Multi-app branding ───────────────────────────────────────────────────────
# The same backend serves multiple apps (LinkUp, Abanoonya Pro). The client
# identifies itself with an `X-App` header. Branding defaults to LinkUp when the
# header is absent, so existing LinkUp behaviour is completely unchanged.
_APP_BRANDS = {
    'linkup':            'LinkUp',
    'app.linkup.mobile': 'LinkUp',
    'abanoonya':         'Abanoonya Pro',
    'abanoonya.pro':     'Abanoonya Pro',
    'app.abanoonya.pro': 'Abanoonya Pro',
}


def app_brand(default: str = 'LinkUp') -> str:
    """Resolve the calling app's display name from the `X-App` request header.

    Must be called inside a request context (resolve it in the route, then pass
    the resulting string into async email helpers)."""
    if not has_request_context():
        return default
    key = (request.headers.get('X-App') or '').strip().lower()
    return _APP_BRANDS.get(key, default)


# ─── Core send ───────────────────────────────────────────────────────────────

def _cfg() -> dict:
    """Fetch SMTP config from Flask app context (with fallback to env vars)."""
    try:
        from flask import current_app
        c = current_app.config
        return {
            'server':    (c.get('MAIL_SERVER') or 'smtp.gmail.com').strip(),
            'port':      int(c.get('MAIL_PORT', 587)),
            'use_tls':   bool(c.get('MAIL_USE_TLS', True)),
            'use_ssl':   bool(c.get('MAIL_USE_SSL', False)),
            'username':  (c.get('MAIL_USERNAME') or '').strip(),
            # Gmail App Passwords are 16 chars; the UI shows them in 4-char
            # groups separated by spaces. Strip ALL whitespace so a pasted
            # "xxxx xxxx xxxx xxxx" still authenticates.
            'password':  (c.get('MAIL_PASSWORD') or '').replace(' ', '').strip(),
            'from_name': c.get('MAIL_FROM_NAME', 'LinkUp'),
            'from_addr': (c.get('MAIL_FROM_ADDRESS') or c.get('MAIL_USERNAME') or '').strip(),
        }
    except RuntimeError:
        import os
        return {
            'server':    (os.getenv('MAIL_SERVER') or 'smtp.gmail.com').strip(),
            'port':      int(os.getenv('MAIL_PORT', '587')),
            'use_tls':   os.getenv('MAIL_USE_TLS', 'true').lower() == 'true',
            'use_ssl':   os.getenv('MAIL_USE_SSL', 'false').lower() == 'true',
            'username':  (os.getenv('MAIL_USERNAME') or '').strip(),
            'password':  (os.getenv('MAIL_PASSWORD') or '').replace(' ', '').strip(),
            'from_name': os.getenv('MAIL_FROM_NAME', 'LinkUp'),
            'from_addr': (os.getenv('MAIL_FROM_ADDRESS') or os.getenv('MAIL_USERNAME') or '').strip(),
        }


def send_email(to: str, subject: str, body_html: str, body_text: str = '', cc: list = None) -> bool:
    """
    Send an email. Returns True on success, False on failure.
    If SMTP is not configured, logs to console (dev-friendly fallback).
    """
    cfg = _cfg()

    if not cfg['username'] or not cfg['password']:
        logger.warning('[Email] SMTP not configured — printing to console (dev mode).')
        print(f"\n{'='*60}\nTO: {to}\nSUBJECT: {subject}\n{body_text or '(HTML only)'}\n{'='*60}\n")
        return True

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = formataddr((cfg['from_name'], cfg['from_addr']))
    msg['To']      = to
    if cc:
        msg['Cc']  = ', '.join(cc)

    if body_text:
        msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    recipients = [to] + (cc or [])
    ctx = ssl.create_default_context()

    try:
        if cfg['use_ssl']:
            with smtplib.SMTP_SSL(cfg['server'], cfg['port'], context=ctx, timeout=15) as conn:
                conn.login(cfg['username'], cfg['password'])
                conn.sendmail(cfg['from_addr'], recipients, msg.as_string())
        else:
            with smtplib.SMTP(cfg['server'], cfg['port'], timeout=15) as conn:
                if cfg['use_tls']:
                    conn.starttls(context=ctx)
                conn.login(cfg['username'], cfg['password'])
                conn.sendmail(cfg['from_addr'], recipients, msg.as_string())

        logger.info(f'[Email] ✓ "{subject}" → {to}')
        return True
    except Exception as exc:
        logger.error(f'[Email] ✗ "{subject}" → {to} | {exc}')
        return False


def send_email_async(to: str, subject: str, body_html: str, body_text: str = '') -> None:
    """Non-blocking email — runs in a background daemon thread."""
    try:
        from flask import current_app
        app = current_app._get_current_object()

        def _run():
            with app.app_context():
                send_email(to, subject, body_html, body_text)

        threading.Thread(target=_run, daemon=True).start()
    except RuntimeError:
        threading.Thread(
            target=send_email,
            args=(to, subject, body_html, body_text),
            daemon=True,
        ).start()


# ─── Shared HTML wrapper ──────────────────────────────────────────────────────

def _wrap(title: str, body: str, accent: str = '#1a56db', brand: str = 'LinkUp') -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:16px;background:#f3f4f6;font-family:Arial,sans-serif">
<div style="max-width:560px;margin:0 auto">
  <div style="background:{accent};padding:24px;border-radius:10px 10px 0 0;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:26px">{brand}</h1>
    <p style="color:rgba(255,255,255,.7);margin:4px 0 0;font-size:13px">Connect. Grow. Achieve.</p>
  </div>
  <div style="background:#fff;padding:32px;border-radius:0 0 10px 10px;border:1px solid #e5e7eb">
    {body}
    <hr style="border:none;border-top:1px solid #f3f4f6;margin:28px 0 16px">
    <p style="color:#9ca3af;font-size:12px;margin:0">
      {brand} · info@mru.ac.ug · Uganda
    </p>
  </div>
</div>
</body></html>"""


# ─── Email templates ─────────────────────────────────────────────────────────

def send_otp_email(to: str, name: str, code: str, purpose: str = 'login',
                   sync: bool = False, brand: str = None):
    """Send a one-time-code email. By default fire-and-forget (returns None).
    Pass sync=True to send on the calling thread and get a True/False result
    (used by password reset so we never claim 'sent' when SMTP actually failed).
    `brand` defaults to the calling app's name (X-App header → LinkUp fallback)."""
    if brand is None:
        brand = app_brand()  # resolved here, while still in the request context
    label = {'login': 'sign in', 'register': 'verify your account',
             'reset': 'reset your password'}.get(purpose, 'access your account')
    subject = f'Your {brand} code: {code}'
    text = (f"Hi {name},\n\nYour {brand} one-time code to {label} is:\n\n"
            f"    {code}\n\nExpires in 10 minutes. Never share this code.\n")
    html = _wrap('OTP', f"""
      <h2 style="margin-top:0">Verification Code</h2>
      <p>Hi <strong>{name}</strong>,</p>
      <p>Use the code below to {label}:</p>
      <div style="background:#1a56db;color:#fff;font-size:40px;font-weight:bold;
                  text-align:center;padding:24px 16px;border-radius:8px;
                  letter-spacing:10px;margin:24px 0">{code}</div>
      <p style="color:#6b7280;font-size:13px">
        ⏱ Expires in <strong>10 minutes</strong>.<br>
        Never share this code with anyone — {brand} staff will never ask for it.
      </p>
    """, brand=brand)
    if sync:
        return send_email(to, subject, html, text)
    send_email_async(to, subject, html, text)
    return None


def send_welcome_email(to: str, name: str, handle: str, brand: str = None) -> None:
    if brand is None:
        brand = app_brand()
    subject = f'Welcome to {brand}, {name}! 🎉'
    text = (f"Hi {name},\n\nWelcome to {brand}! Your handle is @{handle}.\n\n"
            f"Next steps: complete your profile and start connecting.\n\n"
            f"The {brand} Team\n")
    html = _wrap('Welcome', f"""
      <h2 style="margin-top:0">Welcome to {brand}, {name}! 🎉</h2>
      <p>Your account is live. Your handle is <strong>@{handle}</strong>.</p>
      <p>Complete your profile and start connecting.</p>
      <p>Questions? Reply to this email — we read every message.</p>
    """, brand=brand)
    send_email_async(to, subject, html, text)


def send_kyc_email(to: str, name: str, level: int) -> None:
    details = {
        1: ('KYC Level 1 — Phone Verified ✅',
            'Your phone number has been verified. You can now access professional features on LinkUp.'),
        2: ('KYC Level 2 — National ID Submitted ⏳',
            'Your National ID has been submitted for review. Verification typically takes 1–3 business days. '
            'We will notify you when your identity is confirmed.'),
    }
    title, body_line = details.get(level, (f'KYC Level {level} Update', 'Your KYC status has changed.'))
    subject = f'LinkUp: {title}'
    text = f"Hi {name},\n\n{body_line}\n\nThe LinkUp Team\n"
    html = _wrap('KYC Update', f"""
      <h2 style="margin-top:0">{title}</h2>
      <p>Hi <strong>{name}</strong>,</p>
      <p>{body_line}</p>
    """)
    send_email_async(to, subject, html, text)


def send_account_status_email(to: str, name: str, status: str, reason: str = '',
                              brand: str = None) -> None:
    if brand is None:
        brand = app_brand()
    cfg_map = {
        'suspended': ('#dc2626', 'Your account has been suspended',
                      reason or 'Your account was suspended for violating our community guidelines.',
                      'If you believe this is an error, reply to this email.'),
        'active':    ('#16a34a', 'Your account has been reinstated',
                      f'Good news — your {brand} account is active again.', 'Welcome back!'),
        'closed':    ('#6b7280', 'Your account has been closed',
                      reason or 'Your account has been permanently closed.',
                      'Contact support if you have questions.'),
    }
    accent, subject_line, body_main, body_sub = cfg_map.get(status, (
        '#1a56db', f'Account Status: {status}', f'Your account status is now {status}.', ''
    ))
    subject = f'{brand}: {subject_line}'
    text = f"Hi {name},\n\n{body_main}\n{body_sub}\n\nThe {brand} Team\n"
    html = _wrap('Account Update', f"""
      <h2 style="margin-top:0;color:{accent}">{subject_line}</h2>
      <p>Hi <strong>{name}</strong>,</p>
      <p>{body_main}</p>
      <p>{body_sub}</p>
    """, accent=accent, brand=brand)
    send_email_async(to, subject, html, text)


def send_panic_email(
    to: str, contact_name: str,
    owner_name: str, owner_handle: str,
    location_text: str = '', share_url: str = '',
) -> None:
    subject = f'🚨 SOS Alert from {owner_name} — LinkUp Safety'
    loc = location_text or 'Not shared'
    share_block = (f'\n🔗 Track location: {share_url}' if share_url else '')
    text = (f"Hi {contact_name},\n\n"
            f"⚠️ {owner_name} (@{owner_handle}) triggered a SOS on LinkUp.\n"
            f"📍 Location: {loc}{share_block}\n\n"
            f"Contact them immediately or alert emergency services.\n\nLinkUp Safety\n")
    share_html = (f'<p><a href="{share_url}" style="color:#dc2626;font-weight:bold">'
                  f'🔗 View live location</a></p>' if share_url else '')
    html = _wrap('SOS Alert', f"""
      <h2 style="margin-top:0;color:#dc2626">🚨 {owner_name} needs help!</h2>
      <p>Hi <strong>{contact_name}</strong>,</p>
      <p><strong>{owner_name}</strong> (@{owner_handle}) triggered an SOS alert on LinkUp.</p>
      <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:6px;padding:16px;margin:16px 0">
        <p style="margin:0;font-weight:bold">📍 {loc}</p>
        {share_html}
      </div>
      <p><strong>Please contact them or alert emergency services immediately.</strong></p>
    """, accent='#dc2626')
    send_email_async(to, subject, html, text)


def send_location_share_email(
    to: str, contact_name: str,
    owner_name: str, location_text: str,
    share_url: str, check_time: str, expires_at: str,
) -> None:
    subject = f'{owner_name} shared their date location — LinkUp Safety'
    loc = location_text or 'Not specified'
    text = (f"Hi {contact_name},\n\n{owner_name} shared their date location with you.\n"
            f"Location: {loc}\nCheck-in time: {check_time}\nView location: {share_url}\n"
            f"Link expires: {expires_at}\n\nLinkUp Safety\n")
    html = _wrap('Date Location Share', f"""
      <h2 style="margin-top:0">📍 Date Location Share</h2>
      <p>Hi <strong>{contact_name}</strong>,</p>
      <p><strong>{owner_name}</strong> is going on a date and shared their location with you.</p>
      <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:16px;margin:16px 0">
        <p style="margin:0"><strong>📍 Location:</strong> {loc}</p>
        <p style="margin:8px 0 0"><strong>⏰ Check-in time:</strong> {check_time}</p>
        <p style="margin:8px 0 0">
          <a href="{share_url}" style="color:#1a56db;font-weight:bold">🔗 View live location</a>
          <span style="color:#6b7280;font-size:12px"> (expires {expires_at})</span>
        </p>
      </div>
      <p>If you don't hear from {owner_name} by the check-in time, please reach out to check they are safe.</p>
    """)
    send_email_async(to, subject, html, text)


def send_mentorship_email(to: str, mentor_name: str, mentee_name: str,
                          message: str, goals: str) -> None:
    subject = f'{mentee_name} sent you a mentorship request — LinkUp'
    text = (f"Hi {mentor_name},\n\n{mentee_name} sent you a mentorship request.\n"
            f"Message: {message or 'None'}\nGoals: {goals or 'Not specified'}\n\n"
            f"Log in to LinkUp to accept or decline.\n\nThe LinkUp Team\n")
    html = _wrap('Mentorship Request', f"""
      <h2 style="margin-top:0">🎓 New Mentorship Request</h2>
      <p>Hi <strong>{mentor_name}</strong>,</p>
      <p><strong>{mentee_name}</strong> would like you as their mentor on LinkUp.</p>
      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:16px;margin:16px 0">
        <p style="margin:0"><strong>Message:</strong> {message or 'No message'}</p>
        <p style="margin:8px 0 0"><strong>Goals:</strong> {goals or 'Not specified'}</p>
      </div>
      <p>Open LinkUp to accept or decline this request.</p>
    """)
    send_email_async(to, subject, html, text)


def send_application_status_email(to: str, name: str, job_title: str, status: str) -> None:
    msgs = {
        'shortlisted': ('🎯 You were shortlisted!',
                        f'Great news — you have been shortlisted for <strong>{job_title}</strong>. '
                        'Prepare for the next stage of the hiring process.'),
        'interview':   ('📅 Interview Invitation',
                        f'You have been invited to interview for <strong>{job_title}</strong>. '
                        'Check your email for scheduling details.'),
        'hired':       ('🎉 Congratulations — You got the job!',
                        f'Your application for <strong>{job_title}</strong> was successful. '
                        'Congratulations and welcome aboard!'),
        'rejected':    ('Application Update',
                        f'Thank you for applying for <strong>{job_title}</strong>. '
                        'After careful consideration, the position has been filled. '
                        'Keep applying — your next opportunity is on LinkUp.'),
    }
    title, body_line = msgs.get(status, ('Application Update',
                                         f'Your application status for {job_title} changed to {status}.'))
    subject = f'LinkUp: {title} — {job_title}'
    text = f"Hi {name},\n\n{title}\n\n{job_title}\n\nThe LinkUp Team\n"
    accent = '#16a34a' if status in ('shortlisted', 'interview', 'hired') else '#6b7280'
    html = _wrap('Application Update', f"""
      <h2 style="margin-top:0;color:{accent}">{title}</h2>
      <p>Hi <strong>{name}</strong>,</p>
      <p>{body_line}</p>
    """, accent=accent)
    send_email_async(to, subject, html, text)
