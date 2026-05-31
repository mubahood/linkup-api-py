"""
LinkUp ratings/endorsements — Phase 0 stub.
Full Endorsement model built in T-API-010 (Phase 3).
"""
from flask import Blueprint
from backend.utils.response import success_response

ratings_bp = Blueprint('ratings', __name__)


@ratings_bp.route('/api/endorsements', methods=['GET'])
def list_endorsements():
    # TODO T-API-010: Endorsement model (Phase 3)
    return success_response("Endorsements", {'data': [], 'total': 0})
