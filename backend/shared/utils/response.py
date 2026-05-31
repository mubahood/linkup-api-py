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


def paginated_response(items, total, page, per_page, message="Success"):
    last_page = math.ceil(total / per_page) if per_page > 0 else 1
    return jsonify({
        "code": 1,
        "message": message,
        "data": {
            "current_page": page,
            "data": items,
            "per_page": per_page,
            "total": total,
            "last_page": last_page,
        }
    }), 200
