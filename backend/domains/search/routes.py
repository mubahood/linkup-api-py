"""
Search routes: /v1/search/*
"""
from flask import Blueprint, request
from backend.domains.search.service import search_people, search_hubs, search_jobs
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response

search_bp = Blueprint('v1_search', __name__, url_prefix='/v1/search')


@search_bp.route('/people', methods=['GET'])
@lu_jwt_required
def people(account):
    q = request.args.get('q', '').strip()
    if not q:
        return error_response('Search query q is required.')
    dimension = request.args.get('dimension', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page
    results = search_people(q, account_id=account.id, dimension=dimension, limit=per_page, offset=offset)
    return success_response('Search results.', results)


@search_bp.route('/hubs', methods=['GET'])
@lu_jwt_required
def hubs(account):
    q = request.args.get('q', '').strip()
    if not q:
        return error_response('Search query q is required.')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page
    results = search_hubs(q, limit=per_page, offset=offset)
    return success_response('Hub search results.', results)


@search_bp.route('/jobs', methods=['GET'])
@lu_jwt_required
def jobs(account):
    q = request.args.get('q', '').strip()
    if not q:
        return error_response('Search query q is required.')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page
    results = search_jobs(q, limit=per_page, offset=offset)
    return success_response('Job search results.', results)
