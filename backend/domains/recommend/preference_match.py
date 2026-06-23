"""
Bidirectional preference-compatibility engine (P-API-06).

Answers the question every dater actually has: *"Do they want someone like me,
and do I want someone like them?"* — by scoring each side's **preferences**
against the other's **attributes**, with hard **dealbreakers**.

Returns, for viewer V looking at candidate C:
  they_match_me : % of C's preferences that MY (V's) profile satisfies
  i_match_them  : % of MY (V's) preferences that C's profile satisfies
  mutual_pct    : harmonic mean of the two (a relationship needs both)
  breakdown     : per-criterion {field, label, mine, theirs, status}
  dealbreaker   : True if either side has a violated dealbreaker (→ hard-exclude)

Only preference fields that are actually SET are evaluated, so an empty
preference never penalises anyone.
"""
from __future__ import annotations

from datetime import date

# Ordered education ladder for ">= minimum" checks.
_EDU_ORDER = ['secondary', 'certificate', 'vocational', 'diploma',
              'bachelors', 'masters', 'phd']

# Human labels for the breakdown.
_LABELS = {
    'interested_in': 'Gender', 'age': 'Age', 'height_cm': 'Height',
    'relationship_goal': 'Relationship goal', 'wants_children': 'Wants children',
    'open_to_children': 'Open to kids', 'religion': 'Religion',
    'education_min': 'Education', 'smoking': 'Smoking', 'drinking': 'Drinking',
    'diet': 'Diet', 'languages': 'Languages', 'tribe': 'Tribe', 'politics': 'Politics',
}


# Gender is stored in two vocabularies across the schema — profiles use
# male/female (DatingProfile.gender), while the preference catalog uses
# man/woman (interested_in). Treat them as equivalent so the gender criterion
# matches regardless of which vocabulary each side was saved with.
_GENDER_ALIASES = {
    'female': {'female', 'woman'}, 'woman': {'female', 'woman'},
    'male': {'male', 'man'}, 'man': {'male', 'man'},
}


def _gender_satisfies(gender, pref_list) -> bool:
    g = (gender or '').lower().strip()
    aliases = _GENDER_ALIASES.get(g, {g})
    return any((p or '').lower().strip() in aliases for p in pref_list)


def _age(dp):
    return (date.today().year - dp.birth_year) if dp and dp.birth_year else None


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _tolerance_ok(pref, value):
    """Smoking/drinking tolerance: 'any' = ok; 'no' = value must be no/never;
    'social_ok' = no/social ok; 'prefer_not' = soft (treated as ok)."""
    if pref in (None, 'any', 'prefer_not'):
        return True
    if pref == 'no':
        return value in (None, 'no', 'never', 'sober')
    if pref == 'social_ok':
        return value in (None, 'no', 'never', 'social', 'sober')
    return True


def _eval_criterion(field, pref_val, attrs) -> bool | None:
    """Return True/False if the candidate's attrs satisfy this preference, or
    None if the preference isn't set (skip)."""
    if pref_val in (None, '', [], {}):
        return None

    if field == 'interested_in':
        g = attrs.get('gender')
        return _gender_satisfies(g, pref_val) if g else None
    if field == 'age':
        a = attrs.get('age')
        if a is None:
            return None
        lo, hi = pref_val.get('min'), pref_val.get('max')
        return (lo is None or a >= lo) and (hi is None or a <= hi)
    if field == 'height_cm':
        h = attrs.get('height_cm')
        if not h:
            return None
        lo, hi = pref_val.get('min'), pref_val.get('max')
        return (lo is None or h >= lo) and (hi is None or h <= hi)
    if field == 'relationship_goal':
        g = attrs.get('relationship_goal') or attrs.get('intent')
        return (g in pref_val) if g else None
    if field == 'wants_children':
        w = attrs.get('wants_children')
        return (w == pref_val) if w else None
    if field == 'open_to_children':
        # pref True means "I'm fine if they have kids" — always satisfiable.
        return True
    if field == 'religion':
        r = attrs.get('religion')
        return (r in pref_val) if r else None
    if field == 'education_min':
        e = attrs.get('education_level')
        if not e or e not in _EDU_ORDER or pref_val not in _EDU_ORDER:
            return None
        return _EDU_ORDER.index(e) >= _EDU_ORDER.index(pref_val)
    if field == 'smoking':
        return _tolerance_ok(pref_val, attrs.get('smoking'))
    if field == 'drinking':
        return _tolerance_ok(pref_val, attrs.get('drinking'))
    if field == 'diet':
        d = attrs.get('diet')
        return (d == pref_val) if d else None
    if field == 'languages':
        spoken = attrs.get('languages_spoken') or []
        codes = [s.get('code') if isinstance(s, dict) else s for s in spoken]
        return bool(set(pref_val) & set(codes)) if codes else None
    if field == 'tribe':
        t = attrs.get('tribe_ethnicity')
        return (t in pref_val) if t else None
    if field == 'politics':
        p = attrs.get('politics')
        return (p == pref_val) if p else None
    return None


def _attrs(dp) -> dict:
    """Flatten a DatingProfile into the attribute dict the matcher reads."""
    if not dp:
        return {}
    return {
        'gender': dp.gender, 'age': _age(dp), 'height_cm': dp.height_cm,
        'relationship_goal': dp.relationship_goal, 'intent': dp.intent,
        'wants_children': dp.wants_children, 'religion': dp.religion,
        'education_level': dp.education_level, 'smoking': dp.smoking,
        'drinking': dp.drinking, 'diet': dp.diet,
        'languages_spoken': dp.languages_spoken or [],
        'tribe_ethnicity': dp.tribe_ethnicity, 'politics': dp.politics,
    }


def _eval_side(prefs: dict, attrs: dict) -> dict:
    """Score one side: how well `attrs` satisfy `prefs`."""
    prefs = prefs or {}
    dealbreakers = set(prefs.get('dealbreakers') or [])
    criteria, satisfied, total = [], 0, 0
    dealbreaker_hit = False
    for field, label in _LABELS.items():
        ok = _eval_criterion(field, prefs.get(field), attrs)
        if ok is None:
            continue
        total += 1
        is_db = field in dealbreakers
        if ok:
            satisfied += 1
            status = 'match'
        else:
            status = 'dealbreaker' if is_db else 'miss'
            if is_db:
                dealbreaker_hit = True
        criteria.append({'field': field, 'label': label, 'status': status,
                         'dealbreaker': is_db})
    pct = round(100 * satisfied / total) if total else 100
    return {'pct': pct, 'satisfied': satisfied, 'total': total,
            'criteria': criteria, 'dealbreaker_hit': dealbreaker_hit}


def compatibility(viewer_dp, viewer_prefs, candidate_dp, candidate_prefs) -> dict:
    """Full bidirectional compatibility between viewer and candidate."""
    i_match_them = _eval_side(viewer_prefs, _attrs(candidate_dp))
    they_match_me = _eval_side(candidate_prefs, _attrs(viewer_dp))

    a, b = i_match_them['pct'], they_match_me['pct']
    mutual = round(2 * a * b / (a + b)) if (a + b) else 0  # harmonic mean

    return {
        'i_match_them': i_match_them,
        'they_match_me': they_match_me,
        'mutual_pct': mutual,
        'dealbreaker': i_match_them['dealbreaker_hit'] or they_match_me['dealbreaker_hit'],
    }
