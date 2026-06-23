"""
seed_links.py — Rich follow-graph seed for LinkUp demo system.
Run: source venv/bin/activate && python -m backend.seed_links

What this does
──────────────
1. Distributes realistic last_seen_at values across all accounts so the
   Active-Now strip is always populated during demos.

2. Creates a clustered follow graph on top of the existing mutual links:
   - Profession clusters  : people in the same industry follow each other
   - Interest clusters    : people sharing 3+ tags follow each other
   - Location clusters    : same city creates follow affinity
   - University alumni    : same institution follow each other
   - Organic one-way follows : 35 % of new edges stay as 'requested'
     (they follow but haven't been accepted back yet) — makes the
     graph feel real and powers the one-way-follow UI surface.

3. Recomputes strength_score on ALL existing links using:
   - Interest tag Jaccard similarity
   - Mutual (accepted) vs one-way bonus
   - Location co-presence bonus
   Safe to re-run: idempotent (checks before inserting, upserts scores).

Graph statistics expected after seeding:
   - ~3 500 existing mutual links (from seed_demo.py)
   - ~4 000–5 000 new follow edges (requested + accepted mix)
   - Avg degree ≈ 15–20 edges per account
   - Active-Now strip shows ≥8 contacts for samuel-ocen at all times
"""
import random
import uuid
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

random.seed(99)          # deterministic but different from seed_demo


def gen_id():  return str(uuid.uuid4())
def now():     return datetime.utcnow()


# ── last_seen_at distribution ─────────────────────────────────────────────────
# Buckets:  (fraction_of_accounts, min_minutes_ago, max_minutes_ago)
ACTIVITY_BUCKETS = [
    (0.07,       0,       5),    #  7 % — truly live (green dot)
    (0.10,       5,      60),    # 10 % — active in last hour
    (0.13,      60,     480),    # 13 % — active today (< 8 h)
    (0.15,     480,    1440),    # 15 % — active last 24 h
    (0.20,    1440,    4320),    # 20 % — last 3 days
    (0.20,    4320,   10080),    # 20 % — last week
    (0.15,   10080,   43200),    # 15 % — last month
]


def _assign_last_seen(accounts: list) -> None:
    """Assign last_seen_at to every account using ACTIVITY_BUCKETS."""
    from backend.models import db
    total = len(accounts)
    random.shuffle(accounts)
    idx = 0
    for frac, min_m, max_m in ACTIVITY_BUCKETS:
        count = max(1, int(total * frac))
        for acc in accounts[idx: idx + count]:
            minutes = random.randint(min_m, max_m)
            acc.last_seen_at = now() - timedelta(minutes=minutes)
        idx += count
    # remaining accounts get a random old last_seen_at
    for acc in accounts[idx:]:
        acc.last_seen_at = now() - timedelta(days=random.randint(30, 180))
    db.session.commit()
    logger.info(f'[seed-links] last_seen_at set for {total} accounts')


# ── Strength score computation ────────────────────────────────────────────────

def _compute_strength(
    a_tags: set,
    b_tags: set,
    a_loc: str | None,
    b_loc: str | None,
    mutual: bool,
) -> float:
    """
    Returns a strength score in [0.0, 1.0].

    Components:
      interest_jaccard  × 0.35  — shared professional interest tags
      location_match    × 0.20  — same city
      mutual_bonus      × 0.15  — accepted (two-way) vs one-way follow
      base              × 0.30  — floor so even strangers get > 0
    """
    # Interest Jaccard
    union = a_tags | b_tags
    jaccard = len(a_tags & b_tags) / len(union) if union else 0.0

    # Location
    loc_score = 0.0
    if a_loc and b_loc:
        loc_score = 1.0 if a_loc == b_loc else 0.3  # same city or same country

    mutual_score = 1.0 if mutual else 0.0

    score = (jaccard * 0.35) + (loc_score * 0.20) + (mutual_score * 0.15) + 0.30
    return min(round(score, 4), 1.0)


# ── Main seed ─────────────────────────────────────────────────────────────────

def seed():
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        _run()


def _run():
    from backend.models import db
    from backend.domains.identity.models import Account
    from backend.domains.links.models import Link
    from backend.domains.interest.models import InterestProfile
    from backend.domains.profile.models import ProfessionalProfile, Education

    logger.info('[seed-links] Starting link graph seed …')

    # ── 1. Load all demo accounts ─────────────────────────────────────────
    accounts = Account.query.filter(
        Account.account_status == 'active',
        Account.deleted_at.is_(None),
    ).all()
    logger.info(f'[seed-links] {len(accounts)} active accounts loaded')

    # ── 2. Set last_seen_at ───────────────────────────────────────────────
    _assign_last_seen(accounts)

    # ── 3. Build lookup structures ────────────────────────────────────────
    acc_ids = [a.id for a in accounts]
    acc_map = {a.id: a for a in accounts}

    # Interest tags per account
    tags_map: dict[str, set] = {aid: set() for aid in acc_ids}
    for ip in InterestProfile.query.filter(InterestProfile.account_id.in_(acc_ids)).all():
        tags_map[ip.account_id].add(ip.tag_id)

    # Location (city name) per account
    from backend.domains.reference.models import Location
    loc_rows = Location.query.filter(Location.id.in_(
        {a.location_id for a in accounts if a.location_id}
    )).all()
    loc_map_id = {l.id: l.name for l in loc_rows}
    def _city(acc):
        return loc_map_id.get(acc.location_id)

    # Institution per account (first education record)
    edu_map: dict[str, str | None] = {aid: None for aid in acc_ids}
    for edu in Education.query.filter(
        Education.account_id.in_(acc_ids),
        Education.institution_id.isnot(None),
    ).all():
        if edu_map[edu.account_id] is None:
            edu_map[edu.account_id] = edu.institution_id

    # Professional headline prefix (for profession clustering)
    prof_industry_map: dict[str, str] = {}
    for prof in ProfessionalProfile.query.filter(
        ProfessionalProfile.account_id.in_(acc_ids)
    ).all():
        if prof.current_role:
            # Bucket by first word of role (Engineer, Doctor, Teacher…)
            prof_industry_map[prof.account_id] = prof.current_role.split()[0]

    # ── 4. Build existing link index (pair → status) ──────────────────────
    existing_links: dict[tuple, Link] = {}
    for lnk in Link.query.all():
        pair = (lnk.requester_id, lnk.addressee_id)
        existing_links[pair] = lnk

    def _already_linked(a: str, b: str) -> bool:
        return (a, b) in existing_links or (b, a) in existing_links

    # ── 5. Build cluster groups ───────────────────────────────────────────

    def _group_by(key_fn) -> dict:
        groups: dict = {}
        for aid in acc_ids:
            k = key_fn(aid)
            if k:
                groups.setdefault(k, []).append(aid)
        return groups

    # Profession clusters
    prof_groups = _group_by(lambda aid: prof_industry_map.get(aid))
    # Location clusters
    city_groups = _group_by(lambda aid: _city(acc_map[aid]))
    # University alumni clusters
    uni_groups  = _group_by(lambda aid: edu_map.get(aid))
    # Interest super-tag clusters (top tag per account)
    def _top_tag(aid):
        tags = list(tags_map.get(aid, set()))
        return tags[0] if tags else None
    interest_groups = _group_by(_top_tag)

    # ── 6. Generate edges ─────────────────────────────────────────────────

    new_edges: list[tuple[str, str, str]] = []  # (req, addr, status)

    def _add_edge(a: str, b: str, status: str):
        if a == b: return
        if _already_linked(a, b): return
        new_edges.append((a, b, status))
        # Register immediately to prevent duplicates within this run
        existing_links[(a, b)] = True   # type: ignore[assignment]

    def _cluster_edges(group_dict, max_group_size=40, follow_frac=0.35):
        for members in group_dict.values():
            if len(members) < 2:
                continue
            sample = random.sample(members, min(len(members), max_group_size))
            for i, a in enumerate(sample):
                for b in sample[i + 1:]:
                    if random.random() > 0.60:   # ~40 % of intra-cluster pairs connect
                        continue
                    status = 'requested' if random.random() < follow_frac else 'accepted'
                    # Randomly choose direction for one-way follows
                    if random.random() < 0.5:
                        _add_edge(a, b, status)
                    else:
                        _add_edge(b, a, status)

    logger.info('[seed-links] Generating profession cluster edges …')
    _cluster_edges(prof_groups,     max_group_size=30, follow_frac=0.30)
    logger.info('[seed-links] Generating location cluster edges …')
    _cluster_edges(city_groups,     max_group_size=25, follow_frac=0.35)
    logger.info('[seed-links] Generating university alumni edges …')
    _cluster_edges(uni_groups,      max_group_size=20, follow_frac=0.25)
    logger.info('[seed-links] Generating interest cluster edges …')
    _cluster_edges(interest_groups, max_group_size=20, follow_frac=0.40)

    # Cross-cluster random follow edges (serendipitous discovery)
    logger.info('[seed-links] Generating random cross-cluster edges …')
    random_pool = random.sample(acc_ids, min(len(acc_ids), 300))
    for _ in range(800):
        a = random.choice(random_pool)
        b = random.choice(random_pool)
        if a == b: continue
        status = 'requested' if random.random() < 0.45 else 'accepted'
        _add_edge(a, b, status)

    # Ensure samuel-ocen has a rich active-now strip
    # He should follow ~40 accounts that are "live" or "active today"
    samuel = Account.query.filter_by(handle='samuel-ocen').first()
    if samuel:
        live_accounts = Account.query.filter(
            Account.id != samuel.id,
            Account.last_seen_at >= now() - timedelta(hours=24),
            Account.account_status == 'active',
        ).order_by(Account.last_seen_at.desc()).limit(60).all()
        for target in live_accounts[:40]:
            status = 'accepted' if random.random() < 0.65 else 'requested'
            _add_edge(samuel.id, target.id, status)
        logger.info(f'[seed-links] samuel-ocen gets follows to {min(40, len(live_accounts))} active accounts')

    logger.info(f'[seed-links] {len(new_edges)} new edges to insert …')

    # ── 7. Bulk insert new links ──────────────────────────────────────────
    inserted = 0
    for batch_start in range(0, len(new_edges), 200):
        batch = new_edges[batch_start: batch_start + 200]
        for req_id, addr_id, status in batch:
            a_tags = tags_map.get(req_id, set())
            b_tags = tags_map.get(addr_id, set())
            a_city = _city(acc_map[req_id]) if req_id in acc_map else None
            b_city = _city(acc_map[addr_id]) if addr_id in acc_map else None
            score  = _compute_strength(a_tags, b_tags, a_city, b_city, status == 'accepted')
            lnk = Link(
                id=gen_id(),
                requester_id=req_id,
                addressee_id=addr_id,
                status=status,
                strength_score=score,
                created_at=now() - timedelta(days=random.randint(1, 120)),
            )
            db.session.add(lnk)
            inserted += 1
        db.session.commit()
        logger.info(f'[seed-links]   … {batch_start + len(batch)} / {len(new_edges)}')

    logger.info(f'[seed-links] {inserted} new link edges inserted.')

    # ── 8. Recompute strength_score on existing accepted links ────────────
    logger.info('[seed-links] Recomputing strength_score on existing links …')
    updated = 0
    for lnk in Link.query.filter_by(status='accepted').all():
        a_tags = tags_map.get(lnk.requester_id, set())
        b_tags = tags_map.get(lnk.addressee_id, set())
        a_city = _city(acc_map[lnk.requester_id]) if lnk.requester_id in acc_map else None
        b_city = _city(acc_map[lnk.addressee_id]) if lnk.addressee_id in acc_map else None
        score  = _compute_strength(a_tags, b_tags, a_city, b_city, mutual=True)
        if abs(float(lnk.strength_score or 0) - score) > 0.001:
            lnk.strength_score = score
            updated += 1
        if updated % 500 == 0 and updated:
            db.session.commit()
    db.session.commit()
    logger.info(f'[seed-links] {updated} strength_scores recomputed.')

    # ── 9. Stats ──────────────────────────────────────────────────────────
    total      = Link.query.count()
    accepted_n = Link.query.filter_by(status='accepted').count()
    requested_n= Link.query.filter_by(status='requested').count()
    live_n     = Account.query.filter(
        Account.last_seen_at >= now() - timedelta(minutes=5)
    ).count()
    today_n    = Account.query.filter(
        Account.last_seen_at >= now() - timedelta(hours=24)
    ).count()

    logger.info(
        f'[seed-links] ✓ Done!\n'
        f'  Links total   : {total:,}  (accepted={accepted_n:,}  requested={requested_n:,})\n'
        f'  Active live   : {live_n} accounts (< 5 min)\n'
        f'  Active today  : {today_n} accounts (< 24 h)\n'
        f'  Test account  : samuel-ocen / +256700000001 / 111111'
    )


if __name__ == '__main__':
    seed()
