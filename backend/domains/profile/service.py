"""
Profile service: profile CRUD, completion score, onboarding steps.
"""
from backend.domains.profile.models import ProfessionalProfile, DatingProfile, Education, Experience

# ── Ordered onboarding step definitions ──────────────────────────────────────
# Each step maps to a `checks` key and carries UX copy + point value.
_STEPS = [
    {
        'id': 'photo',
        'check_key': 'avatar',
        'title': 'Add a profile photo',
        'description': 'Put a face to your name — members with photos get 3× more views',
        'icon': 'camera_alt',
        'points': 10,
        'priority': 1,
    },
    {
        'id': 'interests',
        'check_key': 'interests_added',
        'title': 'Choose your interests',
        'description': 'Pick 5+ interests across 3 areas to power your recommendations',
        'icon': 'interests',
        'points': 15,
        'priority': 2,
    },
    {
        'id': 'headline',
        'check_key': 'headline',
        'title': 'Add a headline',
        'description': 'Tell people what you do — "Software Engineer @ MTN · Makerere \'19"',
        'icon': 'title',
        'points': 10,
        'priority': 3,
    },
    {
        'id': 'experience',
        'check_key': 'experience',
        'title': 'Add work experience',
        'description': 'Showcase your career journey and attract better opportunities',
        'icon': 'work_outline',
        'points': 15,
        'priority': 4,
    },
    {
        'id': 'education',
        'check_key': 'education',
        'title': 'Add your education',
        'description': 'Connect with alumni from your university or college',
        'icon': 'school_outlined',
        'points': 15,
        'priority': 5,
    },
    {
        'id': 'bio',
        'check_key': 'bio',
        'title': 'Write a bio',
        'description': 'Share your story, mission, and what you\'re looking for',
        'icon': 'edit_note',
        'points': 15,
        'priority': 6,
    },
    {
        'id': 'current_role',
        'check_key': 'current_role',
        'title': 'Set your current role',
        'description': 'Help people understand where you work and what you do',
        'icon': 'badge_outlined',
        'points': 10,
        'priority': 7,
    },
]


def _build_sections(account, prof, edu_list, exp_list, interests_count, dating_profile):
    """Per-section completeness breakdown for the 'completeness ring' (T-API-102).

    Each section reports the fraction of its items that are filled, so the UI can
    show one ring per section and nudge the next-best action (feeds T-API-081).
    """
    def pct(items):
        done = sum(1 for v in items.values() if v)
        return {
            'items': items,
            'filled': done,
            'total': len(items),
            'pct': round(100 * done / len(items)) if items else 0,
            'complete': done == len(items),
        }

    sections = {
        'basics': pct({
            'avatar': bool(account.avatar),
            'headline': bool(prof and prof.headline),
            'tagline': bool(prof and getattr(prof, 'tagline', None)),
            'bio': bool(prof and prof.bio and len(prof.bio.strip()) >= 10),
        }),
        'professional': pct({
            'current_role': bool(prof and prof.current_role),
            'seniority': bool(prof and prof.seniority),
            'industry': bool(prof and getattr(prof, 'industry', None)),
            'years_experience': prof is not None and getattr(prof, 'years_experience', None) is not None,
            'location': bool(prof and prof.location_id),
        }),
        'professional_depth': pct({
            'social_links': bool(prof and getattr(prof, 'social_links', None)),
            'languages_spoken': bool(prof and getattr(prof, 'languages_spoken', None)),
            'achievements': bool(prof and getattr(prof, 'achievements', None)),
            'open_to': bool(prof and prof.open_to),
            'availability_status': bool(prof and getattr(prof, 'availability_status', None)),
        }),
        'education': pct({'has_education': bool(edu_list)}),
        'experience': pct({'has_experience': bool(exp_list)}),
        'interests': pct({'five_plus_interests': interests_count >= 5}),
    }

    # Dating section only when the member runs the Sparks lens.
    if dating_profile is not None:
        dp = dating_profile
        sections['dating'] = pct({
            'photos': bool(dp.photos) and len(dp.photos) >= 1,
            'prompts': bool(dp.prompts) and len(dp.prompts) >= 3,
            'intent': bool(dp.intent),
            'relationship_goal': bool(getattr(dp, 'relationship_goal', None)),
            'lifestyle_basics': bool(getattr(dp, 'smoking', None) or getattr(dp, 'drinking', None)
                                     or getattr(dp, 'education_level', None)),
        })

    overall = round(sum(s['pct'] for s in sections.values()) / len(sections)) if sections else 0
    return sections, overall


def calculate_completion(
    account,
    prof_profile,
    edu_list,
    exp_list,
    interests_count: int = 0,
    dating_profile=None,
) -> dict:
    """
    Calculate profile completion score (0–100) and return ordered onboarding steps.

    Parameters
    ----------
    account          : Account model instance
    prof_profile     : ProfessionalProfile | None
    edu_list         : list of Education records
    exp_list         : list of Experience records
    interests_count  : number of interest tags the user has selected
    """
    score = 0
    checks = {}

    # ── Account basics ────────────────────────────────────────────────────
    checks['avatar'] = bool(account.avatar)
    if checks['avatar']:
        score += 10

    checks['email_verified'] = bool(getattr(account, 'email_verified', False))
    if not checks['email_verified']:
        # Fallback: phone_verified counts too
        checks['email_verified'] = bool(getattr(account, 'phone_verified', False))
    # Email verified is a prerequisite (no points; user can't be here without it)

    _modes = account.modes  # safe accessor — tolerates legacy/double-encoded JSON strings
    checks['modes_enabled'] = bool(
        _modes and (_modes.get('professional') or _modes.get('sparks'))
    )
    # Mode enabled = prereq, no points

    # ── Interests ─────────────────────────────────────────────────────────
    checks['interests_added'] = interests_count >= 5
    if checks['interests_added']:
        score += 15

    # ── Professional profile ──────────────────────────────────────────────
    if prof_profile:
        checks['headline'] = bool(prof_profile.headline)
        checks['bio'] = bool(prof_profile.bio and len(prof_profile.bio.strip()) >= 10)
        checks['current_role'] = bool(prof_profile.current_role)
        checks['location'] = bool(prof_profile.location_id)
        checks['seniority'] = bool(prof_profile.seniority)
    else:
        for k in ('headline', 'bio', 'current_role', 'location', 'seniority'):
            checks[k] = False

    if checks['headline']:    score += 10
    if checks['bio']:         score += 15
    if checks['current_role']: score += 10
    if checks['seniority']:   score += 5  # bonus, not in step list

    # ── Education & Experience ────────────────────────────────────────────
    checks['education']   = bool(edu_list)
    checks['experience']  = bool(exp_list)
    if checks['education']:   score += 15
    if checks['experience']:  score += 15

    # ── Build ordered onboarding steps ───────────────────────────────────
    onboarding_steps = [
        {
            **step,
            'done': checks.get(step['check_key'], False),
        }
        for step in _STEPS
    ]

    missing_fields = [k for k, v in checks.items() if not v]
    completed_steps = sum(1 for s in onboarding_steps if s['done'])
    total_steps = len(onboarding_steps)

    sections, sections_overall = _build_sections(
        account, prof_profile, edu_list, exp_list, interests_count, dating_profile
    )

    return {
        'score':            min(score, 100),
        'checks':           checks,
        'missing_fields':   missing_fields,
        'label':            _label(score),
        'onboarding_steps': onboarding_steps,
        'completed_steps':  completed_steps,
        'total_steps':      total_steps,
        'is_complete':      score >= 80,
        # Per-section breakdown for the completeness ring (T-API-102)
        'sections':         sections,
        'sections_overall': sections_overall,
    }


def _label(score: int) -> str:
    if score >= 80:  return 'Expert'
    if score >= 50:  return 'Intermediate'
    if score >= 25:  return 'Getting started'
    return 'Just joined'
