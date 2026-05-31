"""
LinkUp Payments — Flutterwave — Phase 0 stub.
Full payment routing (wallet topup, events, subscriptions) built in T-API-015 (Phase 2).
Retained: webhook receiver stub, payment initiation stub.
"""
from flask import Blueprint, request
from backend.utils.response import success_response, error_response

flutterwave_bp = Blueprint('flutterwave', __name__)


@flutterwave_bp.route('/api/payments/flutterwave/initiate', methods=['POST'])
def initiate_payment():
    # TODO T-API-015: wire up Flutterwave checkout for wallet topup / events / subscriptions
    return error_response("Payment not yet configured for this environment", status_code=503)


@flutterwave_bp.route('/webhooks/flutterwave', methods=['POST'])
def flutterwave_webhook():
    # TODO T-API-015: handle charge.completed events
    return success_response("Webhook received", {})
