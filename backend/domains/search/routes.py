"""
Search routes: /v1/search/*
All results include { data: [...], total, limit, offset } for pagination.
"""
from flask import Blueprint, request
from backend.domains.search.service import search_people, search_hubs, search_jobs, search_events
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response

search_bp = Blueprint('v1_search', __name__, url_prefix='/v1/search')


@search_bp.route('/people', methods=['GET'])
@lu_jwt_required
def people(account):
    """Search people by name, handle, headline, or bio. Supports ?q=, ?page=, ?per_page=."""
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


@search_bp.route('/events', methods=['GET'])
@lu_jwt_required
def events(account):
    """Search events by title, description, or location."""
    q = request.args.get('q', '').strip()
    if not q:
        return error_response('Search query q is required.')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page
    results = search_events(q, limit=per_page, offset=offset)
    return success_response('Event search results.', results)


@search_bp.route('/all', methods=['GET'])
@lu_jwt_required
def search_all(account):
    """
    Universal search across people, hubs, jobs, and events.
    Returns { people, hubs, jobs, events } each with top 5 matches.
    Useful for a global search bar.
    """
    q = request.args.get('q', '').strip()
    if not q:
        return error_response('Search query q is required.')
    return success_response('Search results.', {
        'people': search_people(q, account_id=account.id, limit=5)['data'],
        'hubs': search_hubs(q, limit=5)['data'],
        'jobs': search_jobs(q, limit=5)['data'],
        'events': search_events(q, limit=5)['data'],
    })
