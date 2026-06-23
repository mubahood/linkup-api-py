"""
LinkUp dummy-data factory (T-API-110).

The engine behind the **≥50-records rule**: every feature task uses these
composable builders to spin up ≥50 realistic, valid records for exactly what
it is testing — reproducibly, from a clean run.

Design:
  • Reuses the hand-curated Ugandan pools in `backend.seed_demo` (names,
    professions, cities) for authenticity — richer than Faker's generic locale.
  • Uses Faker only for incidental filler where a curated pool would add no value.
  • Operates on the *existing* seeded accounts where a feature just needs actors
    (chat, sparks, links), and creates fresh entities where the feature owns them.
  • Deterministic when seeded (`--seed`), so runs are reproducible.

CLI:
    python -m backend.factories --feature=chat --count=50
    python -m backend.factories --feature=chat --count=50 --seed=42

Run `--list` to see available features.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
import uuid
from datetime import datetime, timedelta

from faker import Faker

fake = Faker()


def gen_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ── Realistic message corpora (believable LinkUp chatter) ──────────────────
_PRO_OPENERS = [
    "Hi! Saw we both studied at Makerere — would love to connect.",
    "Hello, I came across your profile through the alumni hub. Impressive work!",
    "Hi there, are you still mentoring junior developers this quarter?",
    "Good morning! I saw your post on the fintech hub — really insightful.",
    "Hey, thanks for accepting my link request. What are you working on these days?",
]
_PRO_REPLIES = [
    "Thanks for reaching out! Happy to connect.",
    "Likewise! What part of the industry are you in?",
    "Yes, I have a couple of mentorship slots open. Let's set something up.",
    "Appreciate it 🙏 I'm building something in the payments space.",
    "Glad it resonated! Are you attending the Kampala tech meetup next week?",
    "Let me check my schedule and get back to you.",
    "Sounds great — send me the details and I'll take a look.",
]
_SPARK_OPENERS = [
    "Hey, your hiking photos are amazing — where was that one taken? 😄",
    "Hi! We matched 🎉 What's keeping you busy this week?",
    "Your prompt about jollof made me laugh. Team Uganda all the way though!",
    "Hello! Coffee or tea person? Important first question 😅",
    "Hi 👋 your profile says you love live music — been to any good shows lately?",
]
_SPARK_REPLIES = [
    "Haha that was up in the Rwenzoris! You hike?",
    "Hey! 🎉 Just wrapped a big week at work, finally relaxing. You?",
    "Bold take 😂 I'll allow it. What's your go-to spot in town?",
    "Tea, always — but I won't judge 😉",
    "Yes! Caught a jazz night at the Square last weekend. It was unreal.",
    "Aww thank you! That's so sweet of you to say 🙂",
]


def _active_accounts(limit: int = 400) -> list:
    """Sample existing active accounts to act as record participants."""
    from backend.domains.identity.models import Account
    return (
        Account.query.filter(
            Account.account_status == 'active',
            Account.deleted_at.is_(None),
        )
        .limit(limit)
        .all()
    )


# ── Builders ───────────────────────────────────────────────────────────────

def make_thread_with_messages(a_id: str, b_id: str, n_messages: int = 6,
                              mode: str = 'professional') -> tuple:
    """Create one direct thread between two accounts with n believable messages.

    Returns (thread, [messages]). Timestamps are staggered backwards from now so
    the chat list is chronologically sane. Caller commits.
    """
    from backend.domains.chat.models import Thread, ThreadParticipant, Message

    is_spark = (mode == 'dating')
    openers = _SPARK_OPENERS if is_spark else _PRO_OPENERS
    replies = _SPARK_REPLIES if is_spark else _PRO_REPLIES

    start = _now() - timedelta(hours=random.randint(2, 240))
    thread = Thread(
        id=gen_id(),
        type='spark' if is_spark else 'direct',
        mode='dating' if is_spark else 'professional',
        created_by=a_id,
        created_at=start,
    )
    from backend.models import db
    db.session.add(thread)
    db.session.flush()
    for pid in (a_id, b_id):
        db.session.add(ThreadParticipant(
            id=gen_id(), thread_id=thread.id, account_id=pid, joined_at=start,
        ))

    messages = []
    t = start
    for i in range(n_messages):
        sender = a_id if i % 2 == 0 else b_id
        if i == 0:
            body = random.choice(openers)
        else:
            body = random.choice(replies)
        t = t + timedelta(minutes=random.randint(2, 600))
        msg = Message(
            id=gen_id(), thread_id=thread.id, sender_id=sender,
            body=body, type='text', status='read', created_at=t,
        )
        db.session.add(msg)
        messages.append(msg)
    thread.last_message_at = t
    return thread, messages


# ── Feature seeders (dispatch table) ───────────────────────────────────────

def seed_chat(count: int) -> dict:
    """Create ≥`count` messages spread across ≥max(10, count//6) threads."""
    from backend.models import db
    accounts = _active_accounts()
    if len(accounts) < 4:
        raise RuntimeError('Need at least 4 active accounts to seed chat.')
    ids = [a.id for a in accounts]

    n_threads = max(10, math.ceil(count / 6))
    total_messages = 0
    threads = []
    used_pairs = set()
    attempts = 0
    while total_messages < count or len(threads) < n_threads:
        attempts += 1
        if attempts > n_threads * 20:
            break
        a, b = random.sample(ids, 2)
        key = frozenset((a, b))
        if key in used_pairs:
            continue
        used_pairs.add(key)
        mode = 'dating' if random.random() < 0.35 else 'professional'
        n_msgs = random.randint(4, 9)
        _, msgs = make_thread_with_messages(a, b, n_msgs, mode=mode)
        threads.append(_)
        total_messages += len(msgs)
    db.session.commit()
    return {'threads': len(threads), 'messages': total_messages}


# ── Professional 360° depth backfill (T-API-100) ───────────────────────────
_INDUSTRIES = [
    'Software & Technology', 'Banking & Finance', 'Healthcare', 'Education',
    'Agriculture & Agribusiness', 'Telecommunications', 'Energy & Utilities',
    'Manufacturing', 'Tourism & Hospitality', 'Media & Creative', 'Legal Services',
    'Engineering & Construction', 'NGO & Development', 'Government & Public Sector',
    'Retail & FMCG', 'Logistics & Transport', 'Real Estate',
]
_LANGS = [
    {'code': 'en', 'proficiency': 'fluent'},
    {'code': 'lg', 'proficiency': 'native'},
    {'code': 'sw', 'proficiency': 'conversational'},
    {'code': 'nyn', 'proficiency': 'conversational'},
    {'code': 'ach', 'proficiency': 'native'},
]
_TAGLINES = [
    'Building for the next billion users in East Africa.',
    'Turning ideas into products that ship.',
    'Helping Ugandan businesses grow with data.',
    'Designer who codes. Builder at heart.',
    'Connecting talent with opportunity across the region.',
    'Engineer focused on reliable, low-bandwidth systems.',
    'Mentor, builder, lifelong learner.',
    'Making finance work for everyone, everywhere.',
]
_ACHIEVEMENTS = [
    {'title': 'Speaker, DevFest Kampala', 'year': 2024},
    {'title': 'Top 10, National Innovation Challenge', 'year': 2023},
    {'title': 'Published in the East African Journal of Technology', 'year': 2024},
    {'title': 'Led migration serving 500k+ users', 'year': 2025},
    {'title': 'Mandela Washington Fellow', 'year': 2022},
    {'title': 'Founded a campus tech community', 'year': 2021},
]
_AVAIL = ['open', 'casually_looking', 'not_looking']


def seed_professional_depth(count: int) -> dict:
    """Backfill ≥`count` professional profiles with rich 360° depth fields."""
    from backend.models import db
    from backend.domains.profile.models import ProfessionalProfile

    profiles = (
        ProfessionalProfile.query
        .filter((ProfessionalProfile.industry.is_(None)) | (ProfessionalProfile.tagline.is_(None)))
        .limit(max(count, 50))
        .all()
    )
    if len(profiles) < count:
        profiles = ProfessionalProfile.query.limit(max(count, 50)).all()

    filled = 0
    for p in profiles:
        handle_seed = (p.account_id or '')[:6]
        p.pronouns = random.choice(['she/her', 'he/him', 'they/them', None])
        p.tagline = random.choice(_TAGLINES)
        p.industry = random.choice(_INDUSTRIES)
        p.years_experience = random.randint(0, 18)
        p.availability_status = random.choice(_AVAIL)
        p.social_links = {
            'linkedin': f'https://linkedin.com/in/{handle_seed}',
            'github': f'https://github.com/{handle_seed}' if random.random() < 0.5 else None,
            'website': f'https://{handle_seed}.me' if random.random() < 0.3 else None,
        }
        p.portfolio_urls = [f'https://portfolio.example/{handle_seed}/{i}' for i in range(random.randint(0, 3))]
        p.achievements = random.sample(_ACHIEVEMENTS, k=random.randint(1, 3))
        p.languages_spoken = random.sample(_LANGS, k=random.randint(1, 3))
        p.hourly_rate = random.choice([None, 50000, 80000, 120000, 200000])
        p.hourly_rate_currency = 'UGX'
        p.response_rate = round(random.uniform(0.6, 1.0), 2)
        filled += 1
    db.session.commit()
    return {'profiles_filled': filled}


# ── Dating 360° depth backfill (T-API-101) ─────────────────────────────────
_REL_GOALS = ['long_term', 'short_term', 'friendship', 'marriage', 'figuring_out']
_CHILD = ['yes', 'no', 'someday', 'prefer_not']
_FREQ = ['no', 'sometimes', 'yes', 'prefer_not']
_RELIGIONS = ['Catholic', 'Anglican', 'Pentecostal', 'Muslim', 'SDA', 'Orthodox', 'Spiritual']
_RELIGIOSITY = ['very', 'somewhat', 'not_really', 'prefer_not']
_TRIBES = ['Muganda', 'Munyankole', 'Musoga', 'Mukiga', 'Itesot', 'Acholi', 'Lugbara', 'Mugisu', 'Munyoro']
_EDU = ['secondary', 'diploma', 'bachelors', 'masters', 'phd']
_LOVE = ['words', 'quality_time', 'acts', 'gifts', 'touch']
_MBTI = ['INTJ', 'ENFP', 'ISTJ', 'ESFJ', 'INFP', 'ENTP', 'ISFP', 'ESTJ']
_DIET = ['omnivore', 'vegetarian', 'pescatarian', 'halal']
_EXERCISE = ['often', 'sometimes', 'rarely']
_PETS = [['dog'], ['cat'], ['dog', 'cat'], [], ['none']]
_DEALBREAKERS = ['smoking', 'dishonesty', 'no ambition', 'poor communication', 'rudeness']
_DATING_PROMPTS = [
    {'prompt': 'A perfect weekend looks like', 'answer': 'A hike near Sipi Falls, then street food in town.'},
    {'prompt': 'The way to my heart is', 'answer': 'Good conversation and a shared playlist.'},
    {'prompt': "I'm looking for someone who", 'answer': 'is kind, curious, and ambitious.'},
    {'prompt': 'My simple pleasures', 'answer': 'Rolex by the roadside and live band Fridays.'},
    {'prompt': "We'll get along if", 'answer': "you can debate jollof vs. luwombo and still smile."},
]


def seed_dating_depth(count: int) -> dict:
    """Backfill ≥`count` dating profiles with rich 360° lifestyle/values fields."""
    from backend.models import db
    from backend.domains.profile.models import DatingProfile

    profiles = (
        DatingProfile.query
        .filter(DatingProfile.height_cm.is_(None))
        .limit(max(count, 50))
        .all()
    )
    if len(profiles) < count:
        profiles = DatingProfile.query.limit(max(count, 50)).all()

    filled = 0
    for p in profiles:
        p.height_cm = random.randint(150, 192)
        p.relationship_goal = random.choice(_REL_GOALS)
        p.has_children = random.choice(_CHILD)
        p.wants_children = random.choice(_CHILD)
        p.smoking = random.choice(_FREQ)
        p.drinking = random.choice(_FREQ)
        p.religion = random.choice(_RELIGIONS)
        p.religiosity = random.choice(_RELIGIOSITY)
        p.tribe_ethnicity = random.choice(_TRIBES)
        p.education_level = random.choice(_EDU)
        p.love_languages = random.sample(_LOVE, k=random.randint(1, 2))
        p.personality_type = random.choice(_MBTI)
        p.diet = random.choice(_DIET)
        p.exercise = random.choice(_EXERCISE)
        p.pets = random.choice(_PETS)
        p.deal_breakers = random.sample(_DEALBREAKERS, k=random.randint(1, 3))
        if not p.prompts:
            p.prompts = random.sample(_DATING_PROMPTS, k=3)
        # Sensitivity: most share religion, few share tribe (opt-in, match-only).
        p.sensitive_optin = {
            'religion': random.random() < 0.7,
            'religiosity': random.random() < 0.5,
            'tribe_ethnicity': random.random() < 0.2,
        }
        filled += 1
    db.session.commit()
    return {'profiles_filled': filled}


# ── Active-Now realism (T-API-049) ─────────────────────────────────────────

def seed_active_now(count: int) -> dict:
    """Stagger `last_seen_at` across live/today/this_week so the Active-Now strip
    is always populated, and ensure follow-graph density for demo accounts."""
    from backend.models import db
    from backend.domains.identity.models import Account
    from backend.domains.links.models import Link
    from sqlalchemy import or_

    accts = (Account.query
             .filter(Account.account_status == 'active', Account.deleted_at.is_(None))
             .limit(max(count, 120)).all())
    now = _now()
    buckets = {'live': 0, 'today': 0, 'this_week': 0}
    for a in accts:
        r = random.random()
        if r < 0.18:
            a.last_seen_at = now - timedelta(minutes=random.randint(1, 4)); buckets['live'] += 1
        elif r < 0.55:
            a.last_seen_at = now - timedelta(hours=random.randint(1, 20)); buckets['today'] += 1
        else:
            a.last_seen_at = now - timedelta(days=random.randint(1, 6)); buckets['this_week'] += 1

    # Ensure a spread of demo accounts each follow ≥20 currently-active members.
    followers = accts[:20]
    pool = [a.id for a in accts]
    follows_made = 0
    for f in followers:
        targets = random.sample(pool, min(25, len(pool)))
        existing = {
            (l.requester_id, l.addressee_id)
            for l in Link.query.filter(or_(Link.requester_id == f.id, Link.addressee_id == f.id)).all()
        }
        for tid in targets:
            if tid == f.id:
                continue
            if (f.id, tid) in existing or (tid, f.id) in existing:
                continue
            db.session.add(Link(id=gen_id(), requester_id=f.id, addressee_id=tid,
                                status='accepted', strength_score=round(random.uniform(0.3, 0.9), 4)))
            follows_made += 1
    db.session.commit()
    return {'staggered': len(accts), 'buckets': buckets, 'links_created': follows_made}


# ── Content liveliness (T-API-051) ─────────────────────────────────────────

def seed_liveliness(count: int) -> dict:
    """Fill the gaps that make the app feel empty: dating photos + notifications.
    (Chat content is produced by the `chat` feature; Active-Now by `active_now`.)"""
    from backend.models import db
    from backend.domains.profile.models import DatingProfile
    from backend.domains.identity.models import Account
    from backend.domains.notifications.service import create_notification

    # 1) Backfill dating photos where missing (real placeholder URLs).
    dps = (DatingProfile.query
           .filter((DatingProfile.photos.is_(None)) | (DatingProfile.photos == db.text("JSON_ARRAY()")))
           .all())
    photos_filled = 0
    for dp in dps:
        if dp.photos and len(dp.photos) >= 1:
            continue
        seed = (dp.account_id or 'x')[:8]
        n = random.randint(2, 5)
        dp.photos = [{'url': f'https://picsum.photos/seed/{seed}{i}/600/800', 'caption': None}
                     for i in range(n)]
        photos_filled += 1
    db.session.commit()

    # 2) Ensure a handful of demo accounts have fresh in-app notifications.
    accts = Account.query.filter_by(account_status='active').limit(max(count, 60)).all()
    notifs = 0
    samples = [a for a in accts][:max(count, 50)]
    for a in samples:
        create_notification(a.id, 'link.request', 'Someone wants to connect',
                            'You have a new Link request waiting.', data={}, action_url='/links/requests')
        notifs += 1
    return {'dating_photos_filled': photos_filled, 'notifications_created': notifs}


# ── Deep dating attributes + preferences (P-API-08) ────────────────────────

def seed_dating_prefs(count: int) -> dict:
    """Fill ≥`count` dating profiles with the deep attributes + a realistic
    'looking for' preferences object (with dealbreakers) and a UG region/district."""
    from backend.models import db
    from backend.domains.profile.models import DatingProfile
    from backend.domains.reference.models import Location

    regions = Location.query.filter_by(level='region', country_code='UG').all()
    districts_by_region = {
        r.id: [d.id for d in Location.query.filter_by(level='district', parent_id=r.id).all()]
        for r in regions
    }

    _ORIENT = ['straight', 'straight', 'straight', 'bisexual', 'gay', 'lesbian']
    _MJ = ['never', 'never', 'sometimes', 'prefer_not']
    _POL = ['apolitical', 'moderate', 'liberal', 'conservative', 'prefer_not']
    _BODY = ['slim', 'athletic', 'average', 'curvy', 'plus_size']
    _ZODIAC = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra',
               'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces']
    _COMM = ['big_texter', 'phone_caller', 'video_chat', 'in_person', 'slow_texter']
    _IND = ['technology', 'finance', 'healthcare', 'education', 'business',
            'media', 'ngo', 'engineering', 'hospitality', 'arts']
    _LANGS = ['en', 'lg', 'sw', 'nyn', 'ach', 'xog', 'teo']
    _REL = ['long_term', 'marriage', 'long_open_short', 'short_open_long', 'figuring_out']
    _RELIG = ['catholic', 'anglican', 'pentecostal', 'sda', 'muslim', 'orthodox']
    _EDU = ['diploma', 'bachelors', 'masters', 'phd']

    profiles = DatingProfile.query.limit(max(count, 60)).all()
    filled = 0
    for p in profiles:
        p.sexual_orientation = random.choice(_ORIENT)
        p.marijuana = random.choice(_MJ)
        p.politics = random.choice(_POL)
        p.body_type = random.choice(_BODY)
        p.zodiac = random.choice(_ZODIAC)
        p.communication_style = random.choice(_COMM)
        p.industry = random.choice(_IND)
        p.languages_spoken = random.sample(_LANGS, k=random.randint(1, 3))
        if regions:
            r = random.choice(regions)
            p.region_id = r.id
            ds = districts_by_region.get(r.id) or []
            p.district_id = random.choice(ds) if ds else None
        p.country_code = 'UG'

        # A believable "looking for" with 2–4 dealbreakers.
        candidate_db = ['age', 'relationship_goal', 'religion', 'smoking', 'wants_children']
        p.preferences = {
            'interested_in': [random.choice(['woman', 'man'])],
            'age': {'min': random.randint(20, 28), 'max': random.randint(30, 42)},
            'distance_km': random.choice([25, 50, 100, 200]),
            'height_cm': {'min': random.choice([None, 150, 160]), 'max': None},
            'relationship_goal': random.sample(_REL, k=random.randint(1, 2)),
            'wants_children': random.choice(['want', 'open', 'not_sure', None]),
            'open_to_children': random.choice([True, False, None]),
            'religion': random.sample(_RELIG, k=random.randint(0, 3)),
            'education_min': random.choice([None, *_EDU]),
            'smoking': random.choice(['any', 'no', 'social_ok']),
            'drinking': random.choice(['any', 'no', 'social_ok']),
            'diet': None,
            'languages': random.sample(_LANGS, k=random.randint(0, 2)),
            'tribe': [],
            'politics': None,
            'dealbreakers': random.sample(candidate_db, k=random.randint(2, 4)),
        }
        filled += 1
    db.session.commit()
    return {'profiles_filled': filled, 'regions': len(regions)}


FEATURES = {
    'chat': seed_chat,
    'professional_depth': seed_professional_depth,
    'dating_depth': seed_dating_depth,
    'active_now': seed_active_now,
    'liveliness': seed_liveliness,
    'dating_prefs': seed_dating_prefs,
}


def run(feature: str, count: int, seed: int | None = None) -> dict:
    from backend.app import create_app
    if seed is not None:
        random.seed(seed)
        Faker.seed(seed)
    app = create_app()
    with app.app_context():
        if feature not in FEATURES:
            raise SystemExit(
                f"Unknown feature '{feature}'. Available: {', '.join(sorted(FEATURES))}"
            )
        result = FEATURES[feature](count)
        print(f"[factory] feature={feature} count>={count} -> {result}")
        return result


def main(argv=None):
    p = argparse.ArgumentParser(description='LinkUp dummy-data factory (T-API-110)')
    p.add_argument('--feature', help='feature to seed (e.g. chat)')
    p.add_argument('--count', type=int, default=50, help='minimum records to create')
    p.add_argument('--seed', type=int, default=None, help='deterministic seed')
    p.add_argument('--list', action='store_true', help='list available features')
    args = p.parse_args(argv)

    if args.list or not args.feature:
        print('Available features:', ', '.join(sorted(FEATURES)))
        if not args.feature:
            return
    run(args.feature, args.count, args.seed)


if __name__ == '__main__':
    main()
