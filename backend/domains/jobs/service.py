"""
Jobs service — personalised recommendation engine.

FOR-YOU RANKING ALGORITHM
═══════════════════════════════════════════════════════════════════════════════

Score for each open job = weighted sum of five signals (0–100 scale):

  35 %  Skill overlap
         Jaccard( user_skill_tokens, job_skill_tokens )
         Tokens: interest tag slugs + keywords extracted from profile headline
                 compared against job.skills[] + first 60 words of description

  25 %  Seniority match
         1.0  exact match (user seniority == job seniority)
         0.6  one level off (entry↔mid, mid↔senior)
         0.2  two levels off

  20 %  Location proximity
         1.0  same location_id
         0.4  same country (both Uganda, both Kampala, etc.)
         0.0  no location info

  10 %  Recency
         1.0  posted today
         0.7  this week
         0.4  this month
         0.1  older

  10 %  Referral bonus
         0.5  job is referral_open AND user has accepted connections (proxy for
              likelihood of knowing a referrer)

Final match_pct = round(score * 100), capped at 99.

The function is called by GET /v1/jobs/for-you.
"""
from datetime import datetime, timedelta
from backend.domains.jobs.models import Job, Application, SavedJob

# Map seniority levels to numeric ranks for proximity scoring
_SENIORITY_RANK = {'entry': 0, 'mid': 1, 'senior': 2, 'lead': 3, 'director': 4}


def _seniority_score(user_level: str, job_level: str) -> float:
    ur = _SENIORITY_RANK.get(user_level, 1)
    jr = _SENIORITY_RANK.get(job_level, 1)
    diff = abs(ur - jr)
    return 1.0 if diff == 0 else (0.6 if diff == 1 else 0.2)


def _recency_score(created_at: datetime) -> float:
    if not created_at:
        return 0.1
    age = (datetime.utcnow() - created_at).days
    if age == 0:    return 1.0
    if age <= 7:    return 0.7
    if age <= 30:   return 0.4
    return 0.1


def _tokenise(text: str) -> set:
    """Lower-case words, strip punctuation, remove short stop-words."""
    STOP = {'the','a','an','and','or','of','in','to','for','with','on',
            'at','by','from','is','are','was','were','be','been','this',
            'that','your','our','we','us','you','it','its','as','can',
            'will','has','have','had','not','but','all','any','more',
            'than','their','they','also','which','who','what','how'}
    import re
    tokens = re.findall(r"[a-zA-Z0-9+#./]+", text.lower())
    return {t for t in tokens if len(t) > 2 and t not in STOP}


def get_jobs_for_you(
    account_id: str,
    limit: int = 8,
    exclude_applied: bool = True,
    exclude_own: bool = True,
) -> list:
    """
    Return the top `limit` open jobs ranked by relevance to `account_id`.
    Each dict in the result extends Job.to_dict() with:
        match_pct     int   0–99
        match_reason  str   human-readable reason ("4 matching skills", etc.)
        is_saved      bool
        my_application dict | None
    """
    from backend.domains.interest.models import InterestProfile, InterestTag
    from backend.domains.profile.models import ProfessionalProfile
    from backend.domains.links.models import Link
    from sqlalchemy import or_

    # ── Build user profile tokens ──────────────────────────────────────────
    # 1. Interest tag slugs
    user_tag_rows = InterestProfile.query.filter_by(account_id=account_id).all()
    user_tag_ids  = {r.tag_id for r in user_tag_rows}
    tag_slug_map  = {
        t.id: t.slug
        for t in InterestTag.query.filter(InterestTag.id.in_(user_tag_ids)).all()
    }
    user_skill_tokens: set = set()
    for slug in tag_slug_map.values():
        user_skill_tokens.update(_tokenise(slug.replace('-', ' ')))

    # 2. Professional headline keywords
    prof = ProfessionalProfile.query.filter_by(account_id=account_id).first()
    user_seniority = 'mid'
    user_location_id = None
    if prof:
        user_skill_tokens.update(_tokenise(prof.headline or ''))
        user_skill_tokens.update(_tokenise(prof.current_role or ''))
        user_seniority   = prof.seniority or 'mid'
        user_location_id = prof.location_id

    # 3. Has connections (for referral bonus)
    has_connections = Link.query.filter(
        or_(Link.requester_id == account_id, Link.addressee_id == account_id),
        Link.status == 'accepted',
    ).first() is not None

    # ── Exclusion sets ─────────────────────────────────────────────────────
    excluded_job_ids: set = set()
    if exclude_applied:
        for app in Application.query.filter_by(applicant_id=account_id).all():
            excluded_job_ids.add(app.job_id)
    if exclude_own:
        for j in Job.query.filter_by(posted_by=account_id).all():
            excluded_job_ids.add(j.id)

    # ── Candidate pool ─────────────────────────────────────────────────────
    query = Job.query.filter_by(is_open=1)
    if excluded_job_ids:
        query = query.filter(~Job.id.in_(excluded_job_ids))
    candidates: list[Job] = query.order_by(Job.created_at.desc()).limit(200).all()

    if not candidates:
        return []

    # ── Score each candidate ───────────────────────────────────────────────
    saved_ids = {
        s.job_id
        for s in SavedJob.query.filter_by(account_id=account_id).all()
    }

    scored = []
    for job in candidates:
        # Skill overlap (35 %)
        job_tokens: set = set()
        for skill in (job.skills or []):
            job_tokens.update(_tokenise(skill))
        desc_words = ' '.join((job.description or '').split()[:60])
        job_tokens.update(_tokenise(desc_words))

        overlap = job_tokens & user_skill_tokens
        union   = job_tokens | user_skill_tokens
        jaccard = len(overlap) / len(union) if union else 0.0
        skill_s = min(jaccard * 3.0, 1.0)          # amplify: 33 % overlap → 1.0

        # Seniority match (25 %)
        sen_s = _seniority_score(user_seniority, job.seniority or 'mid')

        # Location (20 %)
        if user_location_id and job.location_id:
            loc_s = 1.0 if job.location_id == user_location_id else 0.4
        else:
            loc_s = 0.4   # Uganda-wide fallback

        # Recency (10 %)
        rec_s = _recency_score(job.created_at)

        # Referral bonus (10 %)
        ref_s = 0.5 if (job.referral_open and has_connections) else 0.0

        score = (
            0.35 * skill_s +
            0.25 * sen_s   +
            0.20 * loc_s   +
            0.10 * rec_s   +
            0.10 * ref_s
        )

        # Human-readable reason
        n_skills = len(overlap)
        if n_skills >= 3:
            reason = f'{n_skills} matching skills'
        elif n_skills >= 1:
            reason = f'{n_skills} matching skill{"s" if n_skills > 1 else ""}'
        elif sen_s == 1.0:
            reason = 'Matches your seniority level'
        elif loc_s == 1.0:
            reason = 'Based in your location'
        else:
            reason = 'Relevant to your profile'

        scored.append((score, n_skills, job, reason))

    # Sort: highest score first; break ties by skill overlap count, then recency
    scored.sort(key=lambda x: (x[0], x[1], x[2].created_at or datetime.min), reverse=True)

    # ── Build response ─────────────────────────────────────────────────────
    result = []
    for score, _, job, reason in scored[:limit]:
        d = job.to_dict(
            is_saved=job.id in saved_ids,
            include_application_count=False,
        )
        d['match_pct']    = min(99, max(1, round(score * 100)))
        d['match_reason'] = reason
        result.append(d)

    return result
