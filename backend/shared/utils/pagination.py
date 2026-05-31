import math


def paginate_query(query, page=1, per_page=20):
    """
    Paginate a SQLAlchemy query.
    Returns (items, total, current_page, last_page, per_page)
    """
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    last_page = math.ceil(total / per_page) if per_page > 0 else 1
    return items, total, page, last_page, per_page
