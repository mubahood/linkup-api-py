"""
Links service — suggestion engine and Active-Now graph.

═══════════════════════════════════════════════════════════════════════════════
LINK GRAPH MODEL
═══════════════════════════════════════════════════════════════════════════════

A `Link` row represents a directed-intent edge:

  requester ──(follows)──► addressee
    status = 'requested'  : one-way follow   (requester sees addressee in feed)
    status = 'accepted'   : mutual link      (both see each other; stronger signal)
    status = 'declined'   : addressee declined; requester can re-request

"Your network" for any account A is:
  - Everyone A follows    (A.requester_id, status ∈ {requested, accepted})
  - Everyone who follows A (A.addressee_id, status ∈ {requested, accepted})

"Your links" (mutual) is the subset with status = 'accepted'.

strength_score [0.0–1.0] is updated lazily and reflects:
  0.10  × mutual_flag          (accepted vs one-way)
  0.30  × interest_overlap     (Jaccard of tag sets)
  0.30  × profession_overlap   (same industry / bio_key)
  0.20  × location_proximity   (same city → 1.0, same country → 0.5)
  0.10  × recency              (decay over 30 days since last interaction)

═══════════════════════════════════════════════════════════════════════════════
AI MODEL INTEGRATION
═══════════════════════════════════════════════════════════════════════════════

The link graph feeds three AI sub-systems:

1. PEOPLE-YOU-MAY-KNOW (get_link_suggestions)
   Input features:
     - Jaccard(my_tags, candidate_tags)          [interest overlap]
     - 2nd-degree overlap count                  [mutual connections]
     - same city / same university               [context proximity]
     - profession domain similarity              [professional alignment]
   Output: ranked candidate list with compatibility_score.

2. ACTIVE-NOW SURFACE (get_active_now_in_network)
   Used in the home-feed top strip.
   Signals surfaced to the AI recommendation layer:
     - last_seen_at recency bucket (live / today / this_week)
     - link_type: 'mutual' vs 'following' vs 'follower'
       ► mutual accounts weighted 2× in next-action recommendation
     - strength_score as edge weight in graph traversal
   The AI uses active-now data to:
     - Boost "People you may know" cards for people your connections
       are also actively following right now (collaborative filtering)
     - Detect schedule-compatible users (shared active-hours window)
     - Feed the feed-ranking model: posts/hubs from active-now contacts
       appear higher in the home feed

3. INTEREST DECAY & GRAPH WALKS
   - strength_score decays 5% per 30 days without interaction
   - Revived when either side interacts (message, profile view, post like)
   - Graph-walk BFS (depth 2) finds 2nd-degree candidates for suggestions
   - The BFS is capped at 200 nodes and ranked by cumulative strength_score

═══════════════════════════════════════════════════════════════════════════════
"""
from datetime import datetime, timedelta
from sqlalchemy import or_
from backend.domains.links.models import Link
from backend.domains.identity.models import Account
from backend.domains.interest.models import InterestProfile
from backend.domains.safety.models import Block


# ── Active-Now ────────────────────────────────────────────────────────────────

def get_active_now_in_network(
    account_id: str,
    limit: int = 20,
    window_hours: int = 24,
) -> list:
    """
    Return recently-active members in the caller's follow network.

    Network membership (inclusive — no filter on link direction):
      • People the caller FOLLOWS   (requester_id == account_id)
      • People FOLLOWING the caller (addressee_id == account_id)
    Both `requested` (one-way) and `accepted` (mutual) links qualify.

    Activity window: `last_seen_at >= now - window_hours`.
    Default 24 h so the strip always has content; UI can highlight
    the truly-live subset (< 5 min) with a green dot.

    Returns a list of dicts enriched with:
      account:        full account.to_dict()
      headline:       professional headline (from ProfessionalProfile)
      last_seen_at:   ISO timestamp for "X min ago" display
      active_label:   'live' | 'today' | 'this_week'
      link_type:      'mutual' | 'following' | 'follower'
      strength_score: edge weight for AI ranking
    Ordered: mutual first, then by recency.
    """
    from backend.domains.profile.models import ProfessionalProfile

    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    # ── Fetch the caller's full network edges ─────────────────────────────
    edges = Link.query.filter(
        or_(
            Link.requester_id == account_id,
            Link.addressee_id == account_id,
        ),
        Link.status.in_(['requested', 'accepted']),
    ).all()

    if not edges:
        return []

    # Build network_map: other_account_id → (link_type, strength_score)
    network_map: dict[str, tuple[str, float]] = {}
    for edge in edges:
        is_following = (edge.requester_id == account_id)
        other_id = edge.addressee_id if is_following else edge.requester_id
        mutual = (edge.status == 'accepted')
        ltype = 'mutual' if mutual else ('following' if is_following else 'follower')
        score = float(edge.strength_score or 0.0)
        # If duplicate edges exist, keep higher score
        prev = network_map.get(other_id)
        if prev is None or score > prev[1]:
            network_map[other_id] = (ltype, score)

    if not network_map:
        return []

    # ── Fetch active accounts ────────────────────────────────────────────
    active_accounts = Account.query.filter(
        Account.id.in_(list(network_map.keys())),
        Account.last_seen_at >= cutoff,
        Account.account_status == 'active',
        Account.deleted_at.is_(None),
    ).order_by(Account.last_seen_at.desc()).limit(limit * 2).all()

    if not active_accounts:
        return []

    # ── Load headlines in one query ──────────────────────────────────────
    profile_map = {
        p.account_id: p.headline
        for p in ProfessionalProfile.query.filter(
            ProfessionalProfile.account_id.in_([a.id for a in active_accounts])
        ).all()
    }

    now = datetime.utcnow()

    def _active_label(last_seen: datetime) -> str:
        delta = now - last_seen
        if delta.total_seconds() < 300:   return 'live'        # < 5 min
        if delta.total_seconds() < 3600:  return 'today'       # < 1 h
        if delta.total_seconds() < 86400: return 'today'       # same day
        return 'this_week'

    # ── Build result, mutual first ───────────────────────────────────────
    results = []
    for acc in active_accounts:
        ltype, score = network_map[acc.id]
        results.append({
            'account':        acc.to_dict(),
            'headline':       profile_map.get(acc.id) or '',
            'last_seen_at':   acc.last_seen_at.isoformat() if acc.last_seen_at else None,
            'active_label':   _active_label(acc.last_seen_at) if acc.last_seen_at else 'this_week',
            'link_type':      ltype,
            'strength_score': score,
        })

    # Sort: mutual first, then by last_seen_at desc
    results.sort(key=lambda x: (0 if x['link_type'] == 'mutual' else 1, x['last_seen_at'] or ''), reverse=False)
    results.sort(key=lambda x: x['last_seen_at'] or '', reverse=True)
    # Stable re-sort: mutuals always first
    results.sort(key=lambda x: 0 if x['link_type'] == 'mutual' else 1)

    return results[:limit]


# ── Suggestions ───────────────────────────────────────────────────────────────

def get_link_suggestions(account_id: str, limit: int = 10) -> list:
    """
    Suggest people to connect with, ranked by professional Interest Graph overlap.

    Algorithm (3 tiers):
      Tier 1: Shared interest tags (Jaccard similarity via rank_candidates)
      Tier 2: 2nd-degree network — people your connections follow
      Tier 3: Location + profession fallback

    Exclusions: already linked, blocked (both directions), self.

    AI notes:
      - compatibility_score is returned in the response and fed to the
        home-feed "People you may know" card ranking
      - 2nd-degree candidates carry a `mutual_connection_count` signal
        that the feed model uses as social-proof weighting
    """
    from backend.domains.recommend.service import rank_candidates  # unified seam (T-API-029)

    # ── Excluded IDs ──────────────────────────────────────────────────────
    existing = Link.query.filter(
        or_(Link.requester_id == account_id, Link.addressee_id == account_id)
    ).all()
    linked_ids = {l.requester_id for l in existing} | {l.addressee_id for l in existing}

    blocked_ids = (
        {b.blocked_id  for b in Block.query.filter_by(blocker_id=account_id).all()} |
        {b.blocker_id  for b in Block.query.filter_by(blocked_id=account_id).all()}
    )
    excluded = linked_ids | blocked_ids | {account_id}

    pool_size = limit * 5
    my_tags = {ip.tag_id for ip in InterestProfile.query.filter_by(account_id=account_id).all()}

    # ── Tier 1: shared interest tags ─────────────────────────────────────
    candidate_ids: list[str] = []
    if my_tags:
        rows = (
            InterestProfile.query
            .filter(
                InterestProfile.tag_id.in_(my_tags),
                InterestProfile.account_id != account_id,
                ~InterestProfile.account_id.in_(excluded) if excluded else True,
            )
            .with_entities(InterestProfile.account_id)
            .distinct()
            .limit(pool_size)
            .all()
        )
        candidate_ids = [r[0] for r in rows]

    # ── Tier 2: 2nd-degree (people your connections follow) ───────────────
    if len(candidate_ids) < pool_size:
        my_network_ids = list(linked_ids - excluded)[:50]  # cap BFS width
        if my_network_ids:
            second_degree = (
                Link.query
                .filter(
                    or_(
                        Link.requester_id.in_(my_network_ids),
                        Link.addressee_id.in_(my_network_ids),
                    ),
                    Link.status.in_(['requested', 'accepted']),
                )
                .limit(200)
                .all()
            )
            seen = set(candidate_ids)
            for edge in second_degree:
                for oid in (edge.requester_id, edge.addressee_id):
                    if oid not in excluded and oid not in seen:
                        candidate_ids.append(oid)
                        seen.add(oid)
                    if len(candidate_ids) >= pool_size:
                        break

    # ── Tier 3: active-account fallback ──────────────────────────────────
    if len(candidate_ids) < pool_size:
        fallback = Account.query.filter(
            Account.id != account_id,
            Account.account_status == 'active',
            Account.deleted_at.is_(None),
            ~Account.id.in_(excluded | set(candidate_ids)) if (excluded or candidate_ids) else True,
        ).order_by(Account.created_at.desc()).limit(pool_size - len(candidate_ids)).all()
        candidate_ids.extend(a.id for a in fallback)

    if not candidate_ids:
        return []

    # ── Rank ──────────────────────────────────────────────────────────────
    ranked = rank_candidates(account_id, candidate_ids[:pool_size], mode='professional')

    acc_map = {
        a.id: a for a in Account.query.filter(
            Account.id.in_([cid for cid, _ in ranked[:limit]]),
            Account.deleted_at.is_(None),
        ).all()
    }

    from backend.domains.profile.models import ProfessionalProfile
    prof_map = {
        p.account_id: p
        for p in ProfessionalProfile.query.filter(
            ProfessionalProfile.account_id.in_(list(acc_map.keys()))
        ).all()
    }

    # ── Mutual connection counts ──────────────────────────────────────────
    # For each candidate, count how many of my accepted links they also share.
    my_accepted_ids = {
        (l.addressee_id if l.requester_id == account_id else l.requester_id)
        for l in existing if l.status == 'accepted'
    }
    candidate_link_rows = Link.query.filter(
        or_(
            Link.requester_id.in_([cid for cid, _ in ranked[:limit]]),
            Link.addressee_id.in_([cid for cid, _ in ranked[:limit]]),
        ),
        Link.status == 'accepted',
    ).all()
    # Build map: candidate_id → set of their connection ids
    cand_conn_map: dict[str, set] = {}
    for row in candidate_link_rows:
        for node in (row.requester_id, row.addressee_id):
            if node in acc_map:
                other = row.addressee_id if row.requester_id == node else row.requester_id
                cand_conn_map.setdefault(node, set()).add(other)

    # ── Candidate interest tags ───────────────────────────────────────────
    cand_tag_rows = InterestProfile.query.filter(
        InterestProfile.account_id.in_(list(acc_map.keys()))
    ).all()
    cand_tags_map: dict[str, set] = {}
    for row in cand_tag_rows:
        cand_tags_map.setdefault(row.account_id, set()).add(row.tag_id)

    result = []
    for cid, score in ranked[:limit]:
        acc = acc_map.get(cid)
        if not acc:
            continue
        prof = prof_map.get(cid)

        mutual_count = len(my_accepted_ids & cand_conn_map.get(cid, set()))
        shared_interests = len(my_tags & cand_tags_map.get(cid, set()))

        # Human-readable connection reason (most informative first)
        if mutual_count >= 2:
            reason = f'{mutual_count} mutual connections'
        elif mutual_count == 1:
            reason = '1 mutual connection'
        elif shared_interests >= 3:
            reason = f'{shared_interests} shared interests'
        elif shared_interests > 0:
            reason = f'Shares {shared_interests} interest{"s" if shared_interests > 1 else ""}'
        elif prof and prof.current_role:
            reason = prof.current_role
        else:
            reason = 'Suggested for you'

        d = acc.to_dict()
        d['compatibility_score']   = round(score, 3)
        d['compatibility_pct']     = min(99, max(1, round(score * 100)))
        d['headline']              = prof.headline if prof else ''
        d['current_role']          = prof.current_role if prof else ''
        d['mutual_connection_count'] = mutual_count
        d['shared_interest_count'] = shared_interests
        d['connection_reason']     = reason
        result.append(d)
    return result
