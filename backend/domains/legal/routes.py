"""
Legal domain: hosted Privacy Policy, Terms of Service, Data Deletion, and
Support pages — one URL per brand per page, under /legal/<app-slug>/<page>.

Both Apple App Store Connect and Google Play Console require a working,
publicly-reachable privacy policy URL before an app can be submitted — the
in-app settings screens only ever linked to a placeholder ("linkup.ug/privacy")
that was never actually built. These routes are that missing page, shared
across every brand on this backend (LinkUp, Abanoonya Pro, Uganda Dating App,
and any future franchise) — one template, the resolved brand's display name
substituted in per slug, so store-listing URLs read as a real page for that
specific app rather than a generic query-string trick.

No auth required: these must be reachable by a logged-out browser (a store
reviewer, a prospective user) and by the in-app WebView alike.
"""
from flask import Blueprint, abort
from backend.shared.app_brand import APP_DISPLAY_NAMES

legal_bp = Blueprint('legal', __name__, url_prefix='/legal')

_EFFECTIVE_DATE = '2026-08-31'
_SUPPORT_EMAIL = 'support@abanoonyapro.online'

# URL slug -> normalized app_id. Deliberately separate from the X-App header
# aliases in app_brand.py — these are public, permanent URLs (store listings
# link to them), so they get their own explicit whitelist rather than
# inheriting header-resolution's "unknown -> linkup" fallback, which would
# silently serve LinkUp's page under a mistyped slug instead of 404ing.
_SLUG_APP_IDS = {
    'linkup': 'linkup',
    'abanoonya': 'abanoonya',
    'uganda-dating': 'uganda_dating',
}


def _app_name_for_slug(slug: str) -> str:
    app_id = _SLUG_APP_IDS.get(slug)
    if app_id is None:
        abort(404)
    return APP_DISPLAY_NAMES[app_id]


def _page(title: str, app_name: str, body_html: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — {app_name}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 720px; margin: 0 auto; padding: 32px 20px 64px;
    line-height: 1.6; color: #1a1a2e; background: #fff;
  }}
  h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
  .meta {{ color: #71717a; font-size: 0.85rem; margin-bottom: 28px; }}
  h2 {{ font-size: 1.05rem; margin-top: 28px; color: #7C3AED; }}
  p, li {{ font-size: 0.95rem; }}
  a {{ color: #7C3AED; }}
  ul {{ padding-left: 20px; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #14141c; color: #e4e4e7; }}
    .meta {{ color: #a1a1aa; }}
  }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">{app_name} — effective {_EFFECTIVE_DATE}</div>
{body_html}
</body>
</html>"""


def _privacy_body(app_name: str) -> str:
    return f"""
<p>{app_name} ("we", "us") is a mobile dating and social-connection app for
members in Uganda. This policy explains what information we collect, how we
use it, and the choices you have.</p>

<h2>1. Information we collect</h2>
<ul>
  <li><strong>Account information</strong> — phone number and/or email address, and a password (stored as a salted hash, never in plain text).</li>
  <li><strong>Profile information</strong> — display name, photos, bio, and dating attributes you choose to share (age, gender, interests, preferences, and similar).</li>
  <li><strong>Location</strong> — used to show you nearby matches and the nearest safety/emergency resources. Only read while the app is open; we do not track location in the background.</li>
  <li><strong>Messages</strong> — chat messages you send to other members, stored so conversations persist across your devices.</li>
  <li><strong>Identity verification (optional)</strong> — if you choose to verify your profile, a national ID number, a photo of your ID, and a selfie, reviewed to confirm you match your documents and then handled as sensitive data.</li>
  <li><strong>Payment records</strong> — subscription and in-app coin purchases are processed by Flutterwave; we receive transaction status and amount, not your full card or mobile money credentials.</li>
  <li><strong>Device &amp; usage data</strong> — device type, app version, crash logs, and a push-notification token, used to keep the app working and to reach you with notifications.</li>
</ul>

<h2>2. How we use your information</h2>
<ul>
  <li>To create and secure your account, and to show your profile to other members.</li>
  <li>To power discovery, matching, and messaging.</li>
  <li>To process payments for subscriptions and in-app coins.</li>
  <li>To send notifications about matches, messages, and account activity.</li>
  <li>To review reports, enforce our community guidelines, and keep the app safe.</li>
  <li>To respond to support requests.</li>
</ul>

<h2>3. Who we share it with</h2>
<p>We do not sell your personal information. We share data only with the
service providers that help us run the app, each bound to use it only for
that purpose:</p>
<ul>
  <li><strong>Flutterwave</strong> — payment processing for subscriptions and coin purchases.</li>
  <li><strong>OneSignal</strong> — delivering push notifications.</li>
  <li><strong>Google Maps</strong> — showing your approximate location and nearby places.</li>
</ul>
<p>Other members only ever see what your profile settings choose to show —
never your phone number, email, or exact location, unless you explicitly
reveal contact details to a match.</p>

<h2>4. Data retention</h2>
<p>We keep your information for as long as your account is active. If you
delete your account, we remove your profile from discovery immediately and
delete your personal data within a reasonable period afterward, except where
we're required to retain records (for example, payment records) for legal or
accounting purposes.</p>

<h2>5. Your rights</h2>
<p>You can review and edit most of your profile information directly in the
app. To request a copy of your data, ask us to correct it, or delete your
account entirely, see our <a href="data-deletion">Data Deletion</a> page or
email <a href="mailto:{_SUPPORT_EMAIL}">{_SUPPORT_EMAIL}</a>.</p>

<h2>6. Security</h2>
<p>Passwords are stored as salted bcrypt hashes, never in plain text.
Sessions use short-lived access tokens with a separate refresh token. Traffic
between the app and our servers is encrypted (HTTPS/TLS).</p>

<h2>7. Age requirement</h2>
<p>{app_name} is for adults only — you must be at least 18 years old to
create an account. We do not knowingly collect information from anyone
under 18.</p>

<h2>8. Changes to this policy</h2>
<p>We may update this policy from time to time. We'll let you know about
material changes through an in-app notice or an email to your registered
address. Continuing to use {app_name} after a change takes effect means you
accept the updated policy.</p>

<h2>9. Contact us</h2>
<p>Questions about this policy, or a privacy concern to report:<br>
Email: <a href="mailto:{_SUPPORT_EMAIL}">{_SUPPORT_EMAIL}</a></p>
"""


def _terms_body(app_name: str) -> str:
    return f"""
<p>Welcome to {app_name}. {app_name} is a dating and social-connection
platform that helps members meet, chat, and build relationships. By creating
an account or using the app, you agree to these Terms of Service. Please
read them carefully. These terms are governed by the laws of Uganda.</p>

<h2>1. What {app_name} offers</h2>
<p>{app_name} lets members create a profile, discover and connect with other
members, chat, share posts, and optionally purchase a subscription or in-app
coins for extra features such as gifting. We do not guarantee that you will
find a match, a relationship, or any particular outcome from using the app.</p>

<h2>2. Eligibility</h2>
<p>To use {app_name}, you must:</p>
<ul>
  <li>Be at least 18 years of age — {app_name} is not available to anyone under 18, with no exceptions</li>
  <li>Provide accurate, current, and complete registration information</li>
  <li>Not be prohibited from using dating or social platforms under applicable law</li>
  <li>Maintain the security of your account and password</li>
  <li>Comply with all applicable Ugandan laws</li>
</ul>

<h2>3. Your safety</h2>
<p>Your safety matters to us. We encourage you to:</p>
<ul>
  <li>Get to know someone through chat before meeting in person</li>
  <li>Meet for the first time in a public place and tell a friend where you're going</li>
  <li>Never send money or gifts to someone you haven't met in person</li>
  <li>Use the in-app Block and Report features for any user who makes you uncomfortable</li>
  <li>Contact local emergency services immediately if you're ever in danger</li>
</ul>
<p>{app_name} is not a substitute for your own judgment about who to meet or
trust. We offer optional identity verification, block/report tools, and a
panic-alert safety feature, but we cannot guarantee the identity, intentions,
or conduct of any member.</p>

<h2>4. Identity verification</h2>
<p>{app_name} offers an optional identity verification process where you may
submit a national ID number, a photo of your ID, and a selfie for review.
Verified accounts may display a verification badge. Submitting false or
someone else's identity documents is a violation of these terms and may
result in account termination.</p>

<h2>5. Subscriptions &amp; payments</h2>
<p>{app_name} offers optional paid subscriptions (weekly, biweekly, or
monthly) that unlock additional features, and an in-app coin/wallet system
for gifting other members. Payments are processed securely through
Flutterwave via card or mobile money. Subscription prices and included
features are shown in the app before purchase and may change with notice.
Subscriptions renew for the selected period unless cancelled before the
renewal date; cancelling stops future renewals but does not refund the
current period already paid for.</p>

<h2>6. Community guidelines</h2>
<p>Members must treat each other with respect. The following are prohibited
on {app_name}:</p>
<ul>
  <li>Harassment, threats, hate speech, or discriminatory behaviour</li>
  <li>Impersonating another person or misrepresenting your age, identity, or intentions</li>
  <li>Soliciting money, gifts, or financial information from other members (romance-scam behaviour)</li>
  <li>Posting sexually explicit content involving minors, non-consensual imagery, or content that violates Ugandan law</li>
  <li>Creating multiple accounts to evade a block, ban, or report</li>
  <li>Using the app for commercial solicitation, spam, or advertising without our permission</li>
</ul>
<p>Violations may result in content removal, a warning, account suspension,
or permanent termination, at our discretion.</p>

<h2>7. Your content</h2>
<p>You retain ownership of the photos, posts, and messages you share on
{app_name}, but you grant us a licence to host, display, and transmit that
content as needed to operate the app (for example, showing your profile
photo to other members). You are solely responsible for the content you
post and must have the right to share it.</p>

<h2>8. Intellectual property</h2>
<p>The {app_name} app, logo, trademarks, and platform (excluding
user-submitted content) are owned by us or our licensors and protected by
applicable copyright and trademark law. You may not copy, modify,
distribute, reverse-engineer, or create derivative works from the app or
platform without our written permission.</p>

<h2>9. Liability</h2>
<p>To the maximum extent permitted by Ugandan law: {app_name} is not liable
for the conduct of any member, on or off the platform, including any
meeting arranged through the app. Our total liability for any claim
relating to the app is limited to the amount you paid us in the 3 months
before the claim arose. Nothing in these terms excludes liability that
cannot be excluded under applicable law.</p>

<h2>10. Disputes</h2>
<p>For any disputes arising from your use of {app_name}: please contact our
customer support team first so we can try to resolve it directly. If
unresolved, disputes will be governed by and interpreted under the laws of
Uganda, and subject to the jurisdiction of Ugandan courts.</p>

<h2>11. Changes to these terms</h2>
<p>We may update these Terms of Service from time to time. We'll let you
know about material changes through an in-app notice or an email to your
registered address. Continuing to use {app_name} after a change takes
effect means you accept the updated terms.</p>

<h2>12. Contact us</h2>
<p>For questions about these Terms of Service, or to report a safety
concern:<br>
Email: <a href="mailto:{_SUPPORT_EMAIL}">{_SUPPORT_EMAIL}</a><br>
In-app: Settings → Help &amp; Support</p>
<p>For an emergency, please contact local emergency services directly — do
not wait for a response from us.</p>
"""


def _data_deletion_body(app_name: str) -> str:
    return f"""
<p>You can delete your {app_name} account and data at any time, in two ways:</p>

<h2>In the app (fastest)</h2>
<ol>
  <li>Open {app_name} and go to <strong>Settings</strong></li>
  <li>Scroll to <strong>Delete account</strong></li>
  <li>Confirm — your account is deleted immediately</li>
</ol>

<h2>By email</h2>
<p>If you no longer have access to the app, email
<a href="mailto:{_SUPPORT_EMAIL}">{_SUPPORT_EMAIL}</a> from the address on
your account (or include your registered phone number) and ask us to delete
your account. We'll confirm once it's done, usually within a few days.</p>

<h2>What gets deleted</h2>
<p>Your profile, photos, messages, and matches are removed from the app
immediately and are no longer visible to other members. Records we're
legally required to keep — such as payment/transaction history for tax and
accounting purposes — are retained for the period the law requires, then
deleted. Deletion is permanent and cannot be undone.</p>
"""


def _child_safety_body(app_name: str) -> str:
    return f"""
<p>{app_name} has zero tolerance for child sexual abuse and exploitation
(CSAE) in any form. This page describes the standards we hold the app to
and how to reach us about a concern.</p>

<h2>Adults only</h2>
<p>{app_name} is restricted to users 18 and older, with no exceptions.
Age is collected and checked at signup, and any account we determine
belongs to someone under 18 is removed. The app is not directed at
children, does not market to children, and none of its features are
designed to appeal to or engage minors.</p>

<h2>Prevention</h2>
<ul>
  <li>Age is required at account creation and cannot be skipped.</li>
  <li>Optional identity verification (ID photo + selfie) lets members
  build extra trust in who they're talking to.</li>
  <li>Every profile, message, and photo can be reported in one tap,
  by anyone, at any time — reporting doesn't require a match or a prior
  conversation.</li>
</ul>

<h2>Detection and response</h2>
<p>Reports of CSAE, or any content or behaviour involving a minor, go
straight to our safety team and are treated as priority. We remove the
content and the account immediately on confirmation, and we do not wait
for a full investigation to take that first action. Where a report
involves suspected CSAE, we escalate it for review by someone specifically
responsible for these cases before deciding next steps.</p>

<h2>Reporting to authorities</h2>
<p>Where required by law, we report confirmed or suspected CSAE to the
appropriate authorities — including Uganda's Police Child and Family
Protection Unit and, for content meeting the relevant criteria, the
National Center for Missing &amp; Exploited Children (NCMEC). We cooperate
with law enforcement investigations into CSAE and retain the records
needed to do so.</p>

<h2>Report a concern</h2>
<p>Use Block and Report on the profile, message, or photo in question —
reports reach our safety team directly. To reach us outside the app, or
to report something you can no longer see in-app (a deleted account, for
example), email <a href="mailto:{_SUPPORT_EMAIL}">{_SUPPORT_EMAIL}</a>.
We read every report personally; none of this goes through an automated
queue with no human on the other end.</p>

<p>If a child is in immediate danger, contact local emergency services or
police directly — don't wait on a response from us.</p>
"""


def _support_body(app_name: str) -> str:
    return f"""
<p>Need help with {app_name}? We're here.</p>

<h2>Email support</h2>
<p><a href="mailto:{_SUPPORT_EMAIL}">{_SUPPORT_EMAIL}</a> — for account
issues, billing questions, reporting a safety concern, or general feedback.
We usually reply within a couple of days.</p>

<h2>In the app</h2>
<p>Settings → Help Centre opens a message straight to our support inbox.
Settings → Report or the report option on any profile/message reports that
specific user or content directly to our safety team.</p>

<h2>Safety concerns</h2>
<p>If you feel unsafe or witness something that violates our
<a href="terms">Terms of Service</a>, use the in-app Block and Report
tools first — reports go to our team immediately. For an emergency, contact
local emergency services directly rather than waiting for a response from us.</p>

<h2>Other links</h2>
<p><a href="privacy">Privacy Policy</a> &middot;
<a href="terms">Terms of Service</a> &middot;
<a href="data-deletion">Delete your account</a> &middot;
<a href="child-safety">Child Safety Standards</a></p>
"""


@legal_bp.route('/<slug>/privacy', methods=['GET'])
def privacy_policy(slug):
    app_name = _app_name_for_slug(slug)
    return _page('Privacy Policy', app_name, _privacy_body(app_name))


@legal_bp.route('/<slug>/terms', methods=['GET'])
def terms_of_service(slug):
    app_name = _app_name_for_slug(slug)
    return _page('Terms of Service', app_name, _terms_body(app_name))


@legal_bp.route('/<slug>/data-deletion', methods=['GET'])
def data_deletion(slug):
    app_name = _app_name_for_slug(slug)
    return _page('Data Deletion', app_name, _data_deletion_body(app_name))


@legal_bp.route('/<slug>/support', methods=['GET'])
def support(slug):
    app_name = _app_name_for_slug(slug)
    return _page('Support', app_name, _support_body(app_name))


@legal_bp.route('/<slug>/child-safety', methods=['GET'])
def child_safety(slug):
    app_name = _app_name_for_slug(slug)
    return _page('Child Safety Standards', app_name, _child_safety_body(app_name))
