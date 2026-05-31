from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Retained models (salvaged infrastructure)
from backend.models.user import AdminUser
from backend.models.payment import Payment
from backend.models.transaction import Transaction
from backend.models.user_wallet import UserWallet
from backend.models.chat_head import ChatHead
from backend.models.chat_message import ChatMessage
from backend.models.call_log import CallLog
from backend.models.driver_rating import DriverRating

# TODO T-API-009: AdminUser → Account + ProfessionalProfile + DatingProfile (Phase 1)
# TODO T-API-010: DriverRating → Endorsement (Phase 3)
# TODO T-API-011: ChatHead/ChatMessage → Thread/Message (Phase 1)
