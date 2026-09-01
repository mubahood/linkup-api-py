#!/usr/bin/env python3
"""
Seed N complete, diverse, dormant Ugandan dating profiles for Abanoonya.

Every profile hits the exact 100%-completion formula in
backend/domains/profile/service.py::calculate_completion (avatar via dating
photos, phone/email verified, >=5 interest tags, >=2 photos, birth_year +
gender + orientation, bio >=10 chars, district set, preferences set, >=1
prompt) and uses ONLY the canonical dropdown tokens from
backend/domains/reference/dating_options.py — never a display label, never
an invented value — so every field renders correctly selected in the admin
console and mobile app.

Profiles are dormant by design: discoverability='paused' (a first-class,
existing state — see sparks/routes.py) keeps them 100% complete but invisible
to real users' discovery/matching feeds, and account_status='inactive' (a
reversible dormancy marker, distinct from suspended/closed) keeps the admin
console's Status column honest about these being demo accounts rather than
real active members — both are one dropdown away from flipping to live.

GPS: real district reference rows already exist in lu_locations but without
coordinates, so each district here is hand-mapped to its actual town's
real-world lat/lng, then jittered a few km. Weighted so Kampala and Wakiso
dominate, with the remaining accounts spread across ~35 other districts
covering all 4 regions.

Photos: no photo API key is configured for this project, so each profile
gets a deterministic placeholder avatar (DiceBear "personas", CC0, not a
photo of a real person) rendered at multiple background-color variants —
same "face" across 3-4 slots, so a profile doesn't look like it swaps
identity between photos. Swap in real (licensed) photos later by editing
photo_urls_for() below; nothing else in this script needs to change.

Idempotent via the @abanoonya.seed email domain (re-run safe; --reset wipes
previous seed users first).

Run on the server (inside the venv):
    ./venv/bin/python seed_abanoonya_dating.py --women 100 --men 20
"""
import argparse
import random
import secrets
import string
import uuid
from datetime import datetime, timedelta

from backend.seed_demo import (
    MALE_FIRST, FEMALE_FIRST, SURNAMES,
    DATING_PROMPTS_MALE, DATING_PROMPTS_FEMALE,
)

# ── Nilotic given-name pools (subset of MALE_FIRST/FEMALE_FIRST already in
# seed_demo.py) used as the "surname" slot for Nilotic tribes, since Acholi/
# Langi/Alur/Iteso naming pairs an English/Christian given name with a
# traditional name in the surname position — not a Baganda-style clan name.
NILOTIC_MALE = ['Oryem', 'Okello', 'Odongo', 'Ochola', 'Ojok', 'Otim', 'Owor', 'Opio', 'Odoi']
NILOTIC_FEMALE = ['Achieng', 'Apio', 'Adong', 'Abalo', 'Achen', 'Lamunu', 'Akello', 'Anena', 'Achola', 'Asio', 'Aber', 'Ajok']
ENGLISH_FIRST_MALE = ['Ronald', 'Brian', 'Joel', 'Emmanuel', 'Robert', 'Daniel', 'Moses', 'Joshua',
                       'Aaron', 'Patrick', 'Francis', 'Samuel', 'Lawrence', 'Richard', 'George', 'Vincent', 'Dennis', 'Allan']
ENGLISH_FIRST_FEMALE = ['Sandra', 'Sharon', 'Gloria', 'Doreen', 'Patricia', 'Christine', 'Caroline',
                         'Harriet', 'Agnes', 'Grace', 'Stella', 'Diana', 'Judith', 'Rachael', 'Faith',
                         'Hope', 'Joy', 'Mercy', 'Ruth', 'Esther', 'Deborah', 'Lydia', 'Priscilla',
                         'Miriam', 'Florence', 'Juliet', 'Irene', 'Vivian', 'Susan', 'Beatrice']
NILOTIC_TRIBES = {'acholi', 'langi', 'alur', 'iteso', 'karamojong', 'japadhola'}
_NILOTIC_NAMES = set(NILOTIC_MALE) | set(NILOTIC_FEMALE)
# seed_demo.py's shared pools blend a few Nilotic names in with the Bantu
# ones — excluded here so a Bantu-tribe profile doesn't draw a Luo-style
# surname (kept for the Nilotic branch instead, see pick_name()).
BANTU_FEMALE_FIRST = [n for n in FEMALE_FIRST if n not in _NILOTIC_NAMES]
BANTU_MALE_FIRST = [n for n in MALE_FIRST if n not in _NILOTIC_NAMES]
BANTU_SURNAMES = [n for n in SURNAMES if n not in _NILOTIC_NAMES]

# ── Canonical dropdown values only (backend/domains/reference/dating_options.py) ──
RELIGION = (['catholic'] * 4 + ['anglican'] * 4 + ['pentecostal'] * 4
            + ['muslim'] * 3 + ['sda'] * 2 + ['orthodox', 'traditional'])
RELIGIOSITY = ['very'] * 3 + ['somewhat'] * 4 + ['not_really'] * 2
SMOKING = ['no'] * 8 + ['social'] * 2 + ['quitting']
MARIJUANA = ['never'] * 9 + ['sometimes', 'prefer_not']
DIET = ['omnivore'] * 6 + ['no_pork'] * 2 + ['halal'] * 2 + ['vegetarian']
EXERCISE = ['daily', 'often', 'often', 'sometimes', 'sometimes', 'rarely']
PETS = ['none'] * 3 + ['dog'] * 2 + ['cat', 'both', 'want']
EDU = ['certificate', 'diploma', 'diploma', 'bachelors', 'bachelors',
       'bachelors', 'masters', 'vocational']
INDUSTRY = ['technology', 'finance', 'healthcare', 'education', 'agriculture',
            'engineering', 'legal', 'media', 'business', 'ngo',
            'sales_marketing', 'hospitality', 'arts', 'student']
BODY_F = ['slim', 'athletic', 'average', 'average', 'curvy', 'curvy', 'plus_size']
BODY_M = ['slim', 'athletic', 'athletic', 'average', 'average', 'plus_size']
ZODIAC = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra',
          'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces']
COMM = ['big_texter', 'phone_caller', 'video_chat', 'in_person', 'slow_texter']
REL_GOAL = (['long_term'] * 4 + ['marriage'] * 3 + ['short_term', 'friendship',
            'figuring_out', 'long_open_short'])
HAS_KIDS = ['no'] * 7 + ['yes_not_with_me', 'yes_with_me', 'yes_sometimes', 'prefer_not']
WANTS_KIDS = ['want'] * 4 + ['open'] * 3 + ['not_sure', 'dont_want']
LOVE = ['words', 'quality_time', 'acts', 'gifts', 'touch']
LANGS = ['en', 'en', 'lg', 'lg', 'sw', 'nyn', 'ach', 'xog', 'lgg', 'cgg', 'nyo', 'teo']
INTENT = ['relationship'] * 4 + ['marriage'] * 2 + ['open', 'casual', 'friends']
POLITICS = ['none'] * 3 + ['prefer_not'] * 2 + ['independent', 'nrm']
PERSONALITY_TYPE = ['infj', 'enfp', 'istj', 'esfj', 'intp', 'entj', 'isfp', 'estp',
                     'infp', 'enfj', 'istp', 'esfp']
ORIENTATION = 'straight'  # see script docstring rationale in the report to the user
JOBS = ['Nurse', 'Teacher', 'Accountant', 'Software developer', 'Bank teller',
        'Entrepreneur', 'Marketing officer', 'Lawyer', 'Medical doctor', 'Journalist',
        'Fashion designer', 'Chef', 'Architect', 'Civil engineer', 'Pharmacist',
        'HR officer', 'Data analyst', 'Sales executive', 'Graphic designer',
        'Hotel manager', 'University student', 'Social worker', 'Flight attendant',
        'Real estate agent', 'Photographer', 'Agronomist', 'Loans officer', 'Content creator']

# ── Districts: real town coordinates + weight (Kampala/Wakiso dominate) ─────
# (lat, lng, weight, region_key, dominant_tribe_or_None)
DISTRICTS = {
    # Central
    'Kampala':    (0.3476, 32.5825, 36, 'central', None),   # melting pot -> national pool
    'Wakiso':     (0.4044, 32.4593, 26, 'central', None),   # melting pot -> national pool
    'Mukono':     (0.3533, 32.7553, 4, 'central', 'muganda'),
    'Masaka':     (0.3350, 31.7344, 3, 'central', 'muganda'),
    'Mpigi':      (0.2280, 32.3306, 2, 'central', 'muganda'),
    'Luwero':     (0.8500, 32.4736, 2, 'central', 'muganda'),
    'Mityana':    (0.4167, 32.0333, 2, 'central', 'muganda'),
    'Mubende':    (0.5891, 31.3894, 2, 'central', 'muganda'),
    'Buikwe':     (0.3372, 32.8828, 2, 'central', 'muganda'),
    'Kayunga':    (0.6931, 32.8908, 1, 'central', 'muganda'),
    'Nakasongola': (1.3122, 32.4636, 1, 'central', 'muganda'),
    'Kalangala':  (-0.3181, 32.2306, 1, 'central', 'muganda'),
    'Rakai':      (0.7056, 31.5272, 1, 'central', 'muganda'),
    'Sembabule':  (0.0667, 31.4500, 1, 'central', 'muganda'),
    # Eastern
    'Jinja':      (0.4478, 33.2026, 5, 'eastern', 'musoga'),
    'Mbale':      (1.0827, 34.1751, 4, 'eastern', 'mugisu'),
    'Iganga':     (0.6081, 33.4689, 2, 'eastern', 'musoga'),
    'Tororo':     (0.6928, 34.1808, 2, 'eastern', 'japadhola'),
    'Busia':      (0.4608, 34.0919, 2, 'eastern', 'japadhola'),
    'Soroti':     (1.7147, 33.6111, 2, 'eastern', 'iteso'),
    'Kumi':       (1.4664, 33.9358, 1, 'eastern', 'iteso'),
    'Pallisa':    (1.1447, 33.7093, 1, 'eastern', 'iteso'),
    'Bugiri':     (0.5794, 33.7614, 1, 'eastern', 'musoga'),
    'Kamuli':     (0.9472, 33.1200, 1, 'eastern', 'musoga'),
    'Sironko':    (1.2306, 34.2456, 1, 'eastern', 'mugisu'),
    'Kapchorwa':  (1.3986, 34.4444, 1, 'eastern', 'other'),
    # Western
    'Mbarara':    (-0.6072, 30.6545, 5, 'western', 'munyankole'),
    'Kabarole':   (0.6710, 30.2748, 2, 'western', 'mutooro'),
    'Kasese':     (0.1833, 30.0833, 2, 'western', 'other'),
    'Hoima':      (1.4356, 31.3528, 2, 'western', 'munyoro'),
    'Kabale':     (-1.2486, 29.9861, 2, 'western', 'mukiga'),
    'Bushenyi':   (-0.5833, 30.2000, 2, 'western', 'munyankole'),
    'Masindi':    (1.6744, 31.7150, 1, 'western', 'munyoro'),
    'Ntungamo':   (-0.8667, 30.2667, 1, 'western', 'munyankole'),
    'Kisoro':     (-1.2833, 29.6833, 1, 'western', 'other'),
    # Northern
    'Gulu':       (2.7724, 32.2881, 4, 'northern', 'acholi'),
    'Lira':       (2.2350, 32.9100, 3, 'northern', 'langi'),
    'Arua':       (3.0197, 30.9111, 2, 'northern', 'lugbara'),
    'Kitgum':     (3.2783, 32.8867, 1, 'northern', 'acholi'),
    'Nebbi':      (2.4772, 31.0894, 1, 'northern', 'alur'),
    'Moroto':     (2.5333, 34.6667, 1, 'northern', 'karamojong'),
}
NATIONAL_TRIBE_WEIGHTS = (
    ['muganda'] * 18 + ['munyankole'] * 11 + ['musoga'] * 9 + ['mukiga'] * 8
    + ['iteso'] * 7 + ['langi'] * 6 + ['mugisu'] * 6 + ['acholi'] * 5
    + ['lugbara'] * 4 + ['munyoro'] * 4 + ['mutooro'] * 3 + ['karamojong'] * 2
    + ['alur'] * 2 + ['japadhola'] * 2 + ['other'] * 3
)
REGION_TRIBE_FALLBACK = {
    'central': ['muganda'] * 6 + NATIONAL_TRIBE_WEIGHTS,
    'eastern': ['musoga', 'mugisu', 'iteso', 'japadhola'] * 3 + NATIONAL_TRIBE_WEIGHTS,
    'western': ['munyankole', 'mukiga', 'mutooro', 'munyoro'] * 3 + NATIONAL_TRIBE_WEIGHTS,
    'northern': ['acholi', 'langi', 'alur', 'lugbara', 'karamojong'] * 3 + NATIONAL_TRIBE_WEIGHTS,
}

# ── Bio building blocks — combined per-profile for effectively unique bios,
# lightly personalised with the profile's own job/hometown for coherence.
BIO_OPENERS_F = [
    "{district} girl at heart, {job_lc} by day.", "Raised between village holidays and {district} weekdays.",
    "Simple, God-fearing and ambitious — that's me in five words.", "{job} who still believes in old-fashioned romance.",
    "Kampala-based but my roots trace back to {district}.", "Independent, a little stubborn, mostly kind.",
    "Faith, family and good food — my whole personality, honestly.", "{job_lc} with a soft spot for real conversation.",
    "Grew up in {district}, building my life in the city now.", "Quietly confident and endlessly curious about people.",
    "I laugh loud and love harder — no in-between.", "Career-focused {job_lc} who still makes time for the people who matter.",
    "Church on Sunday, hustle every other day.", "Warm, a bit sarcastic, and very serious about good food.",
]
BIO_OPENERS_M = [
    "{district}-born, {job_lc} by trade, romantic by nature.", "Hardworking {job_lc} who still opens doors and means it.",
    "Ambitious and loyal — I don't do half-measures.", "Grew up in {district}, now building something real in the city.",
    "{job} with big dreams and bigger patience.", "Down-to-earth guy who values honesty over everything.",
    "Family man in the making. Faith comes first for me.", "Calm, focused, and quietly determined.",
    "{job_lc} who still believes chivalry isn't dead.", "Kampala hustle, {district} heart.",
    "I show up, I follow through, I keep my word.", "Easy-going until it's time to be serious about life.",
    "Gym in the morning, good conversation at night.", "Straightforward guy — what you see is what you get.",
]
BIO_MIDDLES = [
    "I love road trips, good music and long conversations that go nowhere in particular.",
    "You'll usually find me trying a new local restaurant or planning the next one.",
    "Big on family time, small talk not so much — let's skip to the real stuff.",
    "Football on weekends, church on Sundays, hustle every day in between.",
    "I collect playlists more than anything else. Ask me for a recommendation.",
    "Weekend getaways to Jinja or the west are my reset button.",
    "I take my coffee seriously and my Sundays slow.",
    "Big fan of live music, local food spots, and people who ask good questions.",
    "Nature walks, lake sunsets and honest conversation — my favourite combination.",
    "I'm the friend who always knows the best rolex or nyama choma spot nearby.",
    "Books, documentaries and the occasional dance floor — a bit of everything.",
    "I take faith seriously but I don't take myself too seriously.",
    "Traveling within Uganda is my favourite kind of adventure right now.",
    "Loud laugh, quiet mornings, and a genuine love for good storytelling.",
]
BIO_CLOSERS = [
    "Looking for someone genuine — not a project, a partner.",
    "If you can hold a real conversation and survive Kampala traffic, we'll get along.",
    "Tell me your favourite local food spot and we'll take it from there.",
    "Looking for depth over speed, substance over performance.",
    "Kindness is non-negotiable for me. Everything else we can figure out.",
    "Here for something real — friendship first, then we'll see.",
    "If you know a good playlist and a good matooke spot, message me.",
    "Let's swap travel stories over good food sometime.",
    "Looking for my person — patient, ambitious, and a little bit funny.",
    "Serious about building something real, not in a rush either.",
]


def _slugify(name, i):
    base = ''.join(c.lower() if c.isalnum() else '' for c in name)
    return f'{base}{i:03d}'


def _gen_password(length=14):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def pick_name(gender, tribe, used):
    """Bantu tribes: given name (Bantu or generic) + Bantu clan surname.
    Nilotic tribes: English/Christian given name + a distinct Nilotic name
    in the surname slot — matches real Acholi/Langi/Alur/Iteso naming."""
    for _ in range(200):
        if tribe in NILOTIC_TRIBES:
            pool_first = ENGLISH_FIRST_FEMALE if gender == 'female' else ENGLISH_FIRST_MALE
            pool_last = NILOTIC_FEMALE if gender == 'female' else NILOTIC_MALE
            first = random.choice(pool_first)
            last = random.choice(pool_last)
        else:
            firsts = BANTU_FEMALE_FIRST if gender == 'female' else BANTU_MALE_FIRST
            first = random.choice(firsts)
            last = random.choice(BANTU_SURNAMES)
        key = (first, last)
        if key not in used:
            used.add(key)
            return first, last
    # combo space exhausted (shouldn't happen at this scale) — allow a repeat
    return first, last


def pick_tribe(district_key):
    lat, lng, weight, region, dominant = DISTRICTS[district_key]
    if dominant is None:
        return random.choice(NATIONAL_TRIBE_WEIGHTS)
    if random.random() < 0.70:
        return dominant
    return random.choice(REGION_TRIBE_FALLBACK[region])


def photo_urls_for(seed, n=4):
    """Deterministic placeholder avatars — same generated 'face' (same seed),
    different background colour per slot, so a profile's photos look like a
    consistent set rather than random unrelated people. Not real photos."""
    palette = ['b6e3f4', 'c0aede', 'd1d4f9', 'ffd5dc', 'ffdfbf', 'c9f5d9']
    return [
        f'https://api.dicebear.com/9.x/personas/png?seed={seed}&backgroundColor={palette[i % len(palette)]}'
        for i in range(n)
    ]


def _lc_first(job):
    """Lowercase a job title's leading word for mid-sentence use, unless
    that word is an acronym (e.g. 'HR officer' must stay 'HR', not 'hR')."""
    first_word = job.split(' ', 1)[0]
    if first_word.isupper() and len(first_word) > 1:
        return job
    return job[0].lower() + job[1:]


def build_bio(gender, first, job, district):
    openers = BIO_OPENERS_F if gender == 'female' else BIO_OPENERS_M
    opener = random.choice(openers).format(district=district, job=job, job_lc=_lc_first(job))
    middle = random.choice(BIO_MIDDLES)
    closer = random.choice(BIO_CLOSERS)
    return f'{opener} {middle} {closer}'


def weighted_district_choice():
    names = list(DISTRICTS.keys())
    weights = [DISTRICTS[n][2] for n in names]
    return random.choices(names, weights=weights, k=1)[0]


def build_preferences(gender, age):
    interested_in = 'male' if gender == 'female' else 'female'
    if gender == 'female':
        age_min, age_max = max(18, age - 2), age + random.randint(6, 12)
    else:
        age_min, age_max = max(18, age - 8), age + random.randint(2, 5)
    return {
        'interested_in': [interested_in],
        'age': {'min': age_min, 'max': age_max},
        'distance_km': random.choice([30, 50, 75, 100, 150]),
        'height_cm': {'min': None, 'max': None},
        'relationship_goal': random.sample(REL_GOAL, k=1),
        'wants_children': random.choice(WANTS_KIDS),
        'open_to_children': random.choice([True, False, None]),
        'religion': [],
        'education_min': None,
        'smoking': random.choice(['any', 'no', 'social_ok']),
        'drinking': random.choice(['any', 'no', 'social_ok']),
        'diet': None,
        'languages': [],
        'tribe': [],
        'politics': None,
        'dealbreakers': random.sample(['smoking', 'dishonesty', 'no_ambition', 'rudeness'], k=random.randint(1, 2)),
    }


def run(args):
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        from backend.models import db
        from backend.domains.identity.models import Account
        from backend.domains.profile.models import DatingProfile
        from backend.domains.interest.models import InterestTag, InterestProfile
        from backend.domains.reference.models import Location

        districts_db = {d.name: d for d in Location.query.filter_by(level='district').all()}
        missing = [n for n in DISTRICTS if n not in districts_db]
        if missing:
            print(f'WARNING: districts not found in lu_locations, skipping: {missing}')
            for n in missing:
                DISTRICTS.pop(n, None)

        tags_by_dim = {}
        for t in InterestTag.query.all():
            tags_by_dim.setdefault(t.dimension, []).append(t.id)
        rich_dims = [d for d in ('hobbies_passions', 'lifestyle', 'personality_working_style',
                                  'relationship_intent', 'causes_values') if tags_by_dim.get(d)]

        SEED_DOMAIN = '@abanoonya.seed'
        if args.reset:
            old = Account.query.filter(Account.email.like(f'%{SEED_DOMAIN}')).all()
            ids = [a.id for a in old]
            if ids:
                InterestProfile.query.filter(InterestProfile.account_id.in_(ids)).delete(synchronize_session=False)
                DatingProfile.query.filter(DatingProfile.account_id.in_(ids)).delete(synchronize_session=False)
                Account.query.filter(Account.id.in_(ids)).delete(synchronize_session=False)
                db.session.commit()
            print(f'reset: removed {len(ids)} previous seed users')

        used_names = set()
        created = 0
        idx = Account.query.filter(Account.email.like(f'%{SEED_DOMAIN}')).count()
        district_tally = {}
        specs = [('female', args.women), ('male', args.men)]

        for gender, count in specs:
            prompts_pool = DATING_PROMPTS_FEMALE if gender == 'female' else DATING_PROMPTS_MALE
            for _ in range(count):
                idx += 1
                district_key = weighted_district_choice()
                lat, lng, _w, region, _dom = DISTRICTS[district_key]
                tribe = pick_tribe(district_key)
                first, last = pick_name(gender, tribe, used_names)
                name = f'{first} {last}'
                handle = _slugify(name, idx)
                email = f'{handle}{SEED_DOMAIN}'
                if Account.query.filter_by(email=email).first():
                    continue

                age = random.randint(19, 25) if gender == 'female' else random.randint(20, 35)
                job = random.choice(JOBS)
                seed_str = f'{handle}-{uuid.uuid4().hex[:6]}'
                pics = photo_urls_for(seed_str, n=random.choice([3, 4]))

                acc = Account(
                    id=str(uuid.uuid4()), handle=handle, display_name=name,
                    email=email, email_verified=1, phone_verified=0,
                    app_id='abanoonya', account_status='inactive', kyc_level=0,
                    modes_enabled={'professional': False, 'sparks': True},
                    last_lat=round(lat + random.uniform(-0.045, 0.045), 6),
                    last_lng=round(lng + random.uniform(-0.045, 0.045), 6),
                    location_updated_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 4000)),
                )
                acc.set_password(_gen_password())
                db.session.add(acc)
                db.session.flush()

                religion = random.choice(RELIGION)
                religiosity = random.choice(RELIGIOSITY)
                if religion == 'muslim' or religiosity == 'very':
                    drinking = random.choices(['no', 'sober', 'social'], weights=[50, 30, 20], k=1)[0]
                else:
                    drinking = random.choices(['no', 'social', 'yes', 'sober'], weights=[35, 40, 15, 10], k=1)[0]

                dp = DatingProfile(
                    id=str(uuid.uuid4()), account_id=acc.id, display_name=name,
                    bio=build_bio(gender, first, job, district_key), gender=gender,
                    looking_for_gender=('male' if gender == 'female' else 'female'),
                    sexual_orientation=ORIENTATION,
                    birth_year=datetime.utcnow().year - age,
                    age_min=max(18, age - 6), age_max=age + 8,
                    discoverability='paused',
                    intent=random.choice(INTENT),
                    relationship_goal=random.choice(REL_GOAL),
                    max_distance_km=random.choice([30, 50, 75, 100, 150]),
                    height_cm=(random.randint(150, 178) if gender == 'female'
                               else random.randint(168, 192)),
                    has_children=random.choice(HAS_KIDS),
                    wants_children=random.choice(WANTS_KIDS),
                    smoking=random.choice(SMOKING), drinking=drinking,
                    marijuana=random.choice(MARIJUANA),
                    religion=religion, religiosity=religiosity,
                    tribe_ethnicity=tribe,
                    education_level=random.choice(EDU),
                    love_languages=random.sample(LOVE, k=2),
                    personality_type=random.choice(PERSONALITY_TYPE),
                    diet=random.choice(DIET), exercise=random.choice(EXERCISE),
                    pets=list(dict.fromkeys(
                        [random.choice(PETS)] if random.random() < 0.7
                        else random.sample(sorted(set(PETS)), k=2)
                    )),
                    body_type=random.choice(BODY_F if gender == 'female' else BODY_M),
                    zodiac=random.choice(ZODIAC),
                    communication_style=random.choice(COMM),
                    politics=random.choice(POLITICS),
                    industry=random.choice(INDUSTRY),
                    country_code='UG',
                    region_id=districts_db[district_key].parent_id,
                    district_id=districts_db[district_key].id,
                    languages_spoken=list(dict.fromkeys(random.sample(LANGS, k=3))),
                    prompts=random.sample(prompts_pool, k=min(3, len(prompts_pool))),
                    photos=[{'url': u, 'caption': None} for u in pics],
                    lifestyle={'job': job, 'industry': random.choice(INDUSTRY),
                               'languages': list(dict.fromkeys(random.sample(LANGS, k=3)))},
                    deal_breakers=random.sample(
                        ['smoking', 'dishonesty', 'no_ambition', 'disrespect'], k=random.randint(1, 2)),
                    sensitive_optin={'religion': True, 'tribe_ethnicity': random.random() < 0.5,
                                      'politics': random.random() < 0.3},
                )
                dp.preferences = build_preferences(gender, age)
                db.session.add(dp)

                # >=5 interest tags -> the 15pt 'interests_added' completion check
                if rich_dims:
                    pool = []
                    for d in rich_dims:
                        pool.extend(tags_by_dim[d])
                    if random.random() < 0.35 and tags_by_dim.get('education_affiliation'):
                        pool_edu = tags_by_dim['education_affiliation']
                        chosen = random.sample(pool, k=min(5, len(pool))) + random.sample(pool_edu, k=1)
                    else:
                        chosen = random.sample(pool, k=min(6, len(pool)))
                    for tag_id in set(chosen):
                        db.session.add(InterestProfile(
                            id=str(uuid.uuid4()), account_id=acc.id, tag_id=tag_id,
                            weight=round(random.uniform(0.55, 0.95), 4), mode='dating', source='explicit',
                        ))

                district_tally[district_key] = district_tally.get(district_key, 0) + 1
                created += 1
                if created % 20 == 0:
                    db.session.commit()
                    print(f'  … {created} profiles created')

        db.session.commit()
        total = Account.query.filter(Account.email.like(f'%{SEED_DOMAIN}')).count()
        print(f'\nDONE — created {created} profiles this run. Total seed profiles: {total}.\n')
        print('District distribution this run:')
        for d, n in sorted(district_tally.items(), key=lambda kv: -kv[1]):
            print(f'  {d:<14} {n}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--women', type=int, default=100)
    ap.add_argument('--men', type=int, default=20)
    ap.add_argument('--reset', action='store_true')
    run(ap.parse_args())
