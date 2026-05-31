"""
Reference routes: /v1/reference/*
"""
from flask import Blueprint, request
from backend.domains.reference.models import Location, Institution, Org
from backend.shared.utils.response import success_response, error_response

reference_bp = Blueprint('v1_reference', __name__, url_prefix='/v1/reference')


@reference_bp.route('/locations', methods=['GET'])
def locations():
    q = request.args.get('q', '')
    level = request.args.get('level', '')
    query = Location.query
    if q:
        query = query.filter(Location.name.ilike(f'%{q}%'))
    if level:
        query = query.filter(Location.level == level)
    items = query.order_by(Location.name).limit(50).all()
    return success_response('Locations loaded.', [i.to_dict() for i in items])


@reference_bp.route('/institutions', methods=['GET'])
def institutions():
    q = request.args.get('q', '')
    query = Institution.query
    if q:
        query = query.filter(Institution.name.ilike(f'%{q}%'))
    items = query.order_by(Institution.name).limit(50).all()
    return success_response('Institutions loaded.', [i.to_dict() for i in items])


@reference_bp.route('/orgs', methods=['GET'])
def orgs():
    q = request.args.get('q', '')
    query = Org.query
    if q:
        query = query.filter(Org.name.ilike(f'%{q}%'))
    items = query.order_by(Org.name).limit(50).all()
    return success_response('Organisations loaded.', [i.to_dict() for i in items])
