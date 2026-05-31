"""
Profile service: profile CRUD, completion score.
"""
from backend.domains.profile.models import ProfessionalProfile, DatingProfile, Education, Experience


def calculate_completion(account, prof_profile, edu_list, exp_list) -> dict:
    """Calculate profile completion score (0-100)."""
    score = 0
    checks = {}

    # Account basics: 20 pts
    if account.avatar:
        score += 10
        checks['avatar'] = True
    else:
        checks['avatar'] = False

    if account.phone_verified:
        score += 10
        checks['phone_verified'] = True
    else:
        checks['phone_verified'] = False

    # Professional profile: 50 pts
    if prof_profile:
        if prof_profile.headline:
            score += 10
            checks['headline'] = True
        else:
            checks['headline'] = False

        if prof_profile.bio and len(prof_profile.bio) > 20:
            score += 15
            checks['bio'] = True
        else:
            checks['bio'] = False

        if prof_profile.current_role:
            score += 10
            checks['current_role'] = True
        else:
            checks['current_role'] = False

        if prof_profile.location_id:
            score += 5
            checks['location'] = True
        else:
            checks['location'] = False

        if prof_profile.seniority:
            score += 10
            checks['seniority'] = True
        else:
            checks['seniority'] = False
    else:
        checks.update({k: False for k in ['headline', 'bio', 'current_role', 'location', 'seniority']})

    # Education: 15 pts
    if edu_list:
        score += 15
        checks['education'] = True
    else:
        checks['education'] = False

    # Experience: 15 pts
    if exp_list:
        score += 15
        checks['experience'] = True
    else:
        checks['experience'] = False

    missing_fields = [k for k, v in checks.items() if not v]
    return {
        'score': min(score, 100),
        'checks': checks,
        'missing_fields': missing_fields,
        'label': 'Expert' if score >= 80 else 'Intermediate' if score >= 50 else 'Beginner',
    }
