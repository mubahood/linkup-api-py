import bcrypt
from datetime import datetime
from backend.models import db
from backend.utils.helpers import my_date_time


class AdminUser(db.Model):
    """Legacy account model (table `admin_users`).

    Retained only as the authentication/identity record for the legacy `/api`
    admin surface and as a fallback identity in the calling stack. All
    transport-era service columns were removed in T-API-044; the underlying DB
    columns may still exist but are no longer mapped or used. The canonical
    LinkUp member record is `Account` (`lu_accounts`).
    """
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(500), unique=True, nullable=False)
    password = db.Column(db.String(500), nullable=False)
    name = db.Column(db.String(500), nullable=True)
    avatar = db.Column(db.Text, nullable=True)
    remember_token = db.Column(db.String(1000), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.Text, nullable=True)
    date_of_birth = db.Column(db.Text, nullable=True)
    sex = db.Column(db.Text, nullable=True)
    current_address = db.Column(db.Text, nullable=True)
    phone_number = db.Column(db.Text, nullable=True)
    country_code = db.Column(db.String(5), default='+256')
    country_name = db.Column(db.String(20), default='Uganda')
    country_short_name = db.Column(db.String(3), default='UG')
    email = db.Column(db.Text, nullable=True)
    user_type = db.Column(db.String(25), default='Customer')
    deleted_at = db.Column(db.Date, nullable=True)
    status = db.Column(db.Integer, default=1)
    otp = db.Column(db.BigInteger, nullable=True)
    nin = db.Column(db.Text, nullable=True)

    # Email verification
    email_verified_at = db.Column(db.DateTime, nullable=True)
    email_verification_token = db.Column(db.String(64), nullable=True)
    verification_token_expires = db.Column(db.DateTime, nullable=True)

    # Password reset
    password_reset_token = db.Column(db.String(64), nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)

    # Relationships
    wallet = db.relationship('UserWallet', backref='user', uselist=False, lazy=True)

    def set_password(self, password):
        self.password = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password):
        stored_hash = self.password
        if stored_hash.startswith('$2y$'):
            stored_hash = '$2b$' + stored_hash[4:]
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone_number': self.phone_number,
            'avatar': self.avatar,
            'country_name': self.country_name,
            'country_code': self.country_code,
            'country_short_name': self.country_short_name,
            'date_of_birth': self.date_of_birth,
            'sex': self.sex,
            'current_address': self.current_address,
            'user_type': self.user_type,
            'status': 'active' if self.status == 1 else 'inactive',
            'nin': self.nin,
            'created_at': my_date_time(self.created_at),
            'updated_at': my_date_time(self.updated_at),
        }
