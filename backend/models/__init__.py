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

# LinkUp domain models (lu_ tables)
from backend.domains.reference.models import Location, Institution, Org
from backend.domains.identity.models import Account, AccountDevice, OtpRequest, RefreshToken
from backend.domains.profile.models import ProfessionalProfile, DatingProfile, Education, Experience, Certification
from backend.domains.interest.models import InterestTag, InterestProfile
from backend.domains.links.models import Link
from backend.domains.sparks.models import Spark, Match
from backend.domains.hubs.models import Hub, HubMembership, HubPost
from backend.domains.chat.models import Thread, ThreadParticipant, Message
from backend.domains.jobs.models import Job, Application, SavedJob
from backend.domains.events.models import Event, EventRSVP
from backend.domains.notifications.models import Notification
from backend.domains.safety.models import Report, Block
