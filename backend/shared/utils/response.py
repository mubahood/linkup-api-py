import math
from flask import jsonify


def success_response(message="Success", data=None, code=1, status_code=200):
    response = {"code": code, "message": message}
    if data is not None:
        response["data"] = data
    return jsonify(response), status_code


def error_response(message="Error", data=None, code=0, status_code=400):
    response = {"code": code, "message": message}
    if data is not None:
        response["data"] = data
    return jsonify(response), status_code


def paginated_response(items, total, page, per_page, message="Success", empty_state=None):
    last_page = math.ceil(total / per_page) if per_page > 0 else 1
    data = {
        "current_page": page,
        "data": items,
        "per_page": per_page,
        "total": total,
        "last_page": last_page,
    }
    # Zero-state hint so the UI never shows a blank box (T-API-082).
    if total == 0 and empty_state is not None:
        data["empty_state"] = empty_state
    return jsonify({"code": 1, "message": message, "data": data}), 200


# Registry of designed empty-states — {title, body, cta, action_url} (T-API-082).
EMPTY_STATES = {
    "matches": {"title": "No matches yet", "body": "Spark with people you like to start matching.",
                "cta": "Open Sparks", "action_url": "/sparks"},
    "threads": {"title": "No conversations yet", "body": "Your messages will appear here once you connect.",
                "cta": "Find people", "action_url": "/search"},
    "links_requests": {"title": "No pending requests", "body": "When someone wants to Link, you'll see them here.",
                       "cta": "Discover people", "action_url": "/search"},
    "jobs_saved": {"title": "No saved jobs", "body": "Save jobs to revisit them later.",
                   "cta": "Browse jobs", "action_url": "/jobs"},
    "notifications": {"title": "You're all caught up", "body": "New activity will show up here.",
                      "cta": None, "action_url": None},
}
