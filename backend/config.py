import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# Random per-process fallback, not a fixed string — a missing env var in an
# unconfigured environment now fails safe (a random, unguessable key that
# invalidates on restart) instead of silently using the same hardcoded
# secret every deployment of this codebase has ever shipped with.
_FALLBACK_SECRET = secrets.token_hex(32)
_FALLBACK_JWT_SECRET = secrets.token_hex(32)


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', _FALLBACK_SECRET)
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', _FALLBACK_JWT_SECRET)
    # 24h — a stolen/leaked access token self-expires quickly. The mobile
    # client holds a separate 30-day refresh_token (backend/domains/identity)
    # and silently exchanges it for a new access token on a 401, so this
    # doesn't cost users a re-login. Existing tokens already issued under the
    # old ~30-year expiry keep that expiry (it's baked into the token at
    # issuance) — this only shortens tokens issued from now on.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 86400)))

    # MySQL via MAMP socket (Unix) or TCP/IP (Windows/TCP)
    DB_USER = os.getenv('DB_USERNAME', 'root')
    DB_PASS = os.getenv('DB_PASSWORD', 'root')
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_DATABASE', 'linkup')
    DB_SOCKET = os.getenv('DB_SOCKET', '/Applications/MAMP/tmp/mysql/mysql.sock')

    # Build SQLAlchemy connection string
    _base_uri = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_DATABASE_URI = (
        _base_uri if not os.path.exists(DB_SOCKET)
        else f"{_base_uri}?unix_socket={DB_SOCKET}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Server
    SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.getenv('SERVER_PORT', 5000))

    # Upload settings
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

    # Flutterwave (primary payment gateway)
    FLW_SECRET_KEY = os.getenv('FLW_SECRET_KEY', '')
    FLW_PUBLIC_KEY = os.getenv('FLW_PUBLIC_KEY', '')
    FLW_ENCRYPTION_KEY = os.getenv('FLW_ENCRYPTION_KEY', '')
    FLW_SECRET_HASH = os.getenv('FLW_SECRET_HASH', '')
    FLW_BASE_URL = os.getenv('FLW_BASE_URL', 'https://api.flutterwave.com')
    FLW_CURRENCY = os.getenv('FLW_CURRENCY', 'UGX')
    FLW_PAYMENT_OPTIONS = os.getenv(
        'FLW_PAYMENT_OPTIONS', 'mobilemoneyuganda,card,banktransfer,ussd')
    FLW_TIMEOUT = int(os.getenv('FLW_TIMEOUT', 20))

    # ── Wallet / coins / gifting economy (UGX) ────────────────────────────────
    COIN_RATE_UGX = int(os.getenv('COIN_RATE_UGX', 50))      # 1 coin = UGX 50
    GIFT_PLATFORM_FEE_PCT = int(os.getenv('GIFT_PLATFORM_FEE_PCT', 10))  # recipient keeps 90%
    MIN_TOPUP_UGX = int(os.getenv('MIN_TOPUP_UGX', 500))
    MIN_WITHDRAW_UGX = int(os.getenv('MIN_WITHDRAW_UGX', 1000))
    WITHDRAW_FEE_UGX = int(os.getenv('WITHDRAW_FEE_UGX', 500))
    WITHDRAW_AUTO_LIMIT_UGX = int(os.getenv('WITHDRAW_AUTO_LIMIT_UGX', 100000))  # auto below, manual at/above

    # Service fee
    SERVICE_FEE_PERCENTAGE = int(os.getenv('SERVICE_FEE_PERCENTAGE', 10))

    # Stripe (legacy — kept for DB column compat, not used for new payments)
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

    # OneSignal
    ONESIGNAL_APP_ID = os.getenv('ONESIGNAL_APP_ID', '56ef70cd-45a3-4a66-9838-3146fbbffe77')
    ONESIGNAL_REST_API_KEY = os.getenv('ONESIGNAL_REST_API_KEY', '')
    # Optional — a named Android channel (color/importance/sound) created in
    # the OneSignal dashboard (Settings -> Push & In-App -> Android ->
    # Channels), referenced here by its UUID. Channels are dashboard-managed,
    # not creatable via this REST API; unset falls back to OneSignal's
    # default channel, which still delivers, just without the customization.
    ONESIGNAL_ANDROID_CHANNEL_ID = os.getenv('ONESIGNAL_ANDROID_CHANNEL_ID', '')

    # App URL
    APP_URL = os.getenv('APP_URL', 'https://api.linkup.app')
    APP_NAME = os.getenv('APP_NAME', 'LinkUp')

    # SMTP / Email
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_FROM_NAME = os.getenv('MAIL_FROM_NAME', 'LinkUp')
    MAIL_FROM_ADDRESS = os.getenv('MAIL_FROM_ADDRESS', os.getenv('MAIL_USERNAME', ''))
