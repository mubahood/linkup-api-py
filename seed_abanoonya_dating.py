#!/usr/bin/env python3
"""
Seed N complete, diverse, photo-rich Ugandan dating profiles.

Downloads real African portraits from Pexels, compresses them (Pillow), stores
them under the app's local upload folder, links >=3 photos per user, and builds
a 100%-complete dating profile for each. Idempotent via the @abanoonya.seed
email domain (re-run safe; pass --reset to wipe previous seed users first).

Run on the server (inside the venv):
    PEXELS_KEY=xxxx ./venv/bin/python seed_abanoonya_dating.py --women 35 --men 15 --photos 3
"""
import argparse
import io
import os
import random
import sys
import uuid
from datetime import datetime, timedelta

import requests
from PIL import Image

from backend.seed_demo import (
    MALE_FIRST, FEMALE_FIRST, SURNAMES,
    DATING_PROMPTS_MALE, DATING_PROMPTS_FEMALE,
)

# ── Uganda-flavoured content pools ───────────────────────────────────────────
TRIBES = ['Muganda', 'Munyankole', 'Musoga', 'Mukiga', 'Iteso', 'Langi',
          'Acholi', 'Lugbara', 'Munyoro', 'Mutooro', 'Mugisu', 'Karamojong',
          'Alur', 'Mufumbira', 'Samia', 'Japadhola']
RELIGION = (['catholic'] * 4 + ['anglican'] * 4 + ['pentecostal'] * 4
            + ['muslim'] * 3 + ['sda'] * 2 + ['orthodox', 'traditional'])
RELIGIOSITY = ['very'] * 3 + ['somewhat'] * 4 + ['not_really'] * 2
SMOKING = ['no'] * 7 + ['social'] * 2 + ['quitting']
DRINKING = ['no'] * 4 + ['social'] * 4 + ['yes'] * 2
MARIJUANA = ['never'] * 8 + ['sometimes', 'prefer_not']
DIET = ['omnivore'] * 6 + ['no_pork'] * 2 + ['halal'] * 2 + ['vegetarian']
EXERCISE = ['daily', 'often', 'often', 'sometimes', 'sometimes', 'rarely']
PETS = ['none'] * 3 + ['dog'] * 2 + ['cat', 'both', 'want']
EDU = ['certificate', 'diploma', 'diploma', 'bachelors', 'bachelors',
       'bachelors', 'masters', 'vocational']
INDUSTRY = ['technology', 'finance', 'healthcare', 'education', 'agriculture',
            'engineering', 'legal', 'media', 'business', 'ngo',
            'sales_marketing', 'hospitality', 'arts', 'student']
BODY_F = ['slim', 'athletic', 'average', 'average', 'curvy', 'curvy', 'plus_size']
BODY_M = ['slim', 'athletic', 'athletic', 'average', 'average', 'muscular']
ZODIAC = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra',
          'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces']
COMM = ['big_texter', 'phone_caller', 'video_chat', 'in_person', 'slow_texter']
REL_GOAL = (['long_term'] * 4 + ['marriage'] * 3 + ['short_term', 'friendship',
            'figuring_out'])
HAS_KIDS = ['no'] * 7 + ['yes_not_with_me', 'yes_with_me', 'prefer_not']
WANTS_KIDS = ['want'] * 4 + ['open'] * 3 + ['not_sure', 'dont_want']
LOVE = ['words', 'quality_time', 'acts', 'gifts', 'touch']
LANGS = ['en', 'en', 'lg', 'lg', 'sw', 'nyn', 'ach', 'xog', 'lgg', 'cgg', 'nyo']
INTENT = ['serious', 'serious', 'serious', 'marriage', 'open']
POLITICS = ['none', 'none', 'prefer_not', 'independent']
JOBS = ['Nurse', 'Teacher', 'Accountant', 'Software developer', 'Banker',
        'Entrepreneur', 'Marketing officer', 'Lawyer', 'Doctor', 'Journalist',
        'Fashion designer', 'Chef', 'Architect', 'Civil engineer', 'Pharmacist',
        'HR officer', 'Data analyst', 'Sales executive', 'Graphic designer',
        'Hotel manager', 'University student', 'Social worker', 'Pilot',
        'Real estate agent', 'Photographer']
FEMALE_BIOS = [
    "Kampala girl who loves rolex, road trips and good conversation. Looking for someone genuine.",
    "Faith, family and a good laugh matter most to me. Tell me your favourite local food spot.",
    "Ambitious but soft-hearted. I love sunsets at the lake, church on Sundays and honest people.",
    "Foodie, traveller and a sucker for good music. Catch me dancing at every wedding.",
    "Simple, God-fearing and hardworking. Looking for a partner, not a project.",
    "Nurse by day, Netflix critic by night. I value kindness over everything.",
    "Born in Mbarara, living in Kampala. I love nature walks, matooke and deep talks.",
    "Independent and fun. If you can make me laugh and survive Kampala traffic, we'll get along.",
    "Creative soul who loves art, fashion and chapati. Looking for something real.",
    "Quietly confident. I enjoy reading, gardening and weekend getaways to Jinja.",
]
MALE_BIOS = [
    "Hardworking Kampala guy who loves football, family and a good plate of luwombo.",
    "Ambitious and loyal. I value honesty, ambition and a partner who prays.",
    "Engineer who loves road trips to the west and lazy Sundays. Looking for my person.",
    "Easy-going, God-fearing and driven. Let's grab nyama choma and talk about life.",
    "Entrepreneur building something real. I love gym, travel and honest conversation.",
    "Down-to-earth gentleman. Family man in the making, looking for a serious connection.",
    "Lover of music, motorbikes and Lake Victoria sunsets. Tell me your story.",
    "Calm, focused and ambitious. I believe in loyalty, faith and growing together.",
    "Kampala-born, globally minded. I enjoy good food, deep talks and weekend hikes.",
    "Simple guy with big dreams. Looking for a queen to build a future with.",
]

# Pexels search queries (collect diverse, distinct portraits)
WOMEN_QUERIES = [
    'beautiful african woman portrait', 'ugandan woman', 'black woman smiling portrait',
    'african woman fashion', 'african girl portrait', 'nigerian woman portrait',
    'african woman headshot', 'black woman beauty',
]
MEN_QUERIES = [
    'african man portrait', 'ugandan man', 'black man smiling portrait',
    'african man fashion', 'handsome african man', 'nigerian man portrait',
]

KAMPALA = (0.3476, 32.5825)


def _slugify(name, i):
    base = ''.join(c.lower() if c.isalnum() else '' for c in name)
    return f'{base}{i:02d}'


def fetch_pexels_pool(key, queries, need):
    """Return a de-duplicated list of portrait image URLs from Pexels."""
    urls, seen = [], set()
    headers = {'Authorization': key}
    for q in queries:
        if len(urls) >= need * 2:
            break
        for page in (1, 2):
            try:
                r = requests.get('https://api.pexels.com/v1/search',
                                 headers=headers, timeout=20,
                                 params={'query': q, 'per_page': 80, 'page': page,
                                         'orientation': 'portrait'})
                if r.status_code != 200:
                    print(f'  [pexels] {q} p{page} -> HTTP {r.status_code}')
                    break
                for ph in r.json().get('photos', []):
                    pid = ph.get('id')
                    if pid in seen:
                        continue
                    seen.add(pid)
                    src = ph.get('src', {})
                    urls.append(src.get('portrait') or src.get('large') or src.get('original'))
            except Exception as e:
                print(f'  [pexels] error {q}: {e}')
                break
    random.shuffle(urls)
    print(f'  collected {len(urls)} distinct photos (needed ~{need})')
    return urls


def download_compress_save(url, upload_root):
    """Download an image, compress to <=1080 long-edge JPEG, save under
    uploads/gallery/. Returns the relative URL or None."""
    try:
        resp = requests.get(url, timeout=25)
        if resp.status_code != 200:
            return None
        img = Image.open(io.BytesIO(resp.content)).convert('RGB')
        w, h = img.size
        scale = min(1.0, 1080 / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        gallery = os.path.join(upload_root, 'gallery')
        os.makedirs(gallery, exist_ok=True)
        name = f'{uuid.uuid4().hex}.jpg'
        img.save(os.path.join(gallery, name), 'JPEG', quality=82, optimize=True)
        return f'/uploads/gallery/{name}'
    except Exception as e:
        print(f'    [img] failed {url[:60]}: {e}')
        return None


def run(args):
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        from backend.models import db
        from backend.domains.identity.models import Account
        from backend.domains.profile.models import DatingProfile
        from backend.domains.photos.models import UserPhoto
        try:
            from backend.domains.reference.models import Location
            districts = Location.query.filter(Location.level == 'district').all()
        except Exception:
            districts = []

        upload_root = app.config['UPLOAD_FOLDER']
        SEED_DOMAIN = '@abanoonya.seed'

        if args.reset:
            old = Account.query.filter(Account.email.like(f'%{SEED_DOMAIN}')).all()
            ids = [a.id for a in old]
            if ids:
                UserPhoto.query.filter(UserPhoto.account_id.in_(ids)).delete(synchronize_session=False)
                DatingProfile.query.filter(DatingProfile.account_id.in_(ids)).delete(synchronize_session=False)
                Account.query.filter(Account.id.in_(ids)).delete(synchronize_session=False)
                db.session.commit()
            print(f'reset: removed {len(ids)} previous seed users')

        key = args.pexels_key or os.getenv('PEXELS_KEY', '')
        if not key:
            print('ERROR: provide --pexels-key or PEXELS_KEY env var'); sys.exit(1)

        print('Fetching woman photo pool …')
        women_pool = fetch_pexels_pool(key, WOMEN_QUERIES, args.women * args.photos)
        print('Fetching man photo pool …')
        men_pool = fetch_pexels_pool(key, MEN_QUERIES, args.men * args.photos)

        specs = [('female', args.women), ('male', args.men)]
        created = 0
        idx = 0
        for gender, count in specs:
            pool = women_pool if gender == 'female' else men_pool
            firsts = FEMALE_FIRST if gender == 'female' else MALE_FIRST
            bios = FEMALE_BIOS if gender == 'female' else MALE_BIOS
            prompts_pool = DATING_PROMPTS_FEMALE if gender == 'female' else DATING_PROMPTS_MALE
            for _ in range(count):
                idx += 1
                first = random.choice(firsts)
                last = random.choice(SURNAMES)
                name = f'{first} {last}'
                handle = _slugify(first + last, idx)
                email = f'{handle}{SEED_DOMAIN}'
                if Account.query.filter_by(email=email).first():
                    continue

                # photos: pop `photos` distinct urls (reuse pool if short)
                pics = []
                for _ in range(args.photos):
                    if pool:
                        src = pool.pop()
                    else:
                        src = random.choice(women_pool or men_pool)
                    rel = download_compress_save(src, upload_root)
                    if rel:
                        pics.append(rel)
                if len(pics) < 1:
                    print(f'  skip {name}: no photos'); continue

                acc = Account(
                    id=str(uuid.uuid4()), handle=handle, display_name=name,
                    email=email, email_verified=1, phone_verified=0,
                    account_status='active', kyc_level=1,
                    modes_enabled={'professional': False, 'sparks': True},
                    avatar=pics[0],
                    last_lat=round(KAMPALA[0] + random.uniform(-0.12, 0.12), 6),
                    last_lng=round(KAMPALA[1] + random.uniform(-0.12, 0.12), 6),
                    location_updated_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 4000)),
                )
                acc.set_password('Passw0rd!')
                db.session.add(acc)
                db.session.flush()

                for i, rel in enumerate(pics):
                    db.session.add(UserPhoto(
                        id=str(uuid.uuid4()), account_id=acc.id, url=rel,
                        is_profile_photo=(i == 0), is_public=True,
                        photo_type='profile' if i == 0 else 'gallery',
                        sort_order=i, caption=None,
                    ))

                age = random.randint(21, 33) if gender == 'female' else random.randint(24, 40)
                dp = DatingProfile(
                    id=str(uuid.uuid4()), account_id=acc.id, display_name=name,
                    bio=random.choice(bios), gender=gender,
                    looking_for_gender=('male' if gender == 'female' else 'female'),
                    birth_year=datetime.utcnow().year - age,
                    age_min=max(18, age - 6), age_max=age + 8,
                    discoverability='discoverable',
                    intent=random.choice(INTENT),
                    relationship_goal=random.choice(REL_GOAL),
                    max_distance_km=120,
                    height_cm=(random.randint(150, 178) if gender == 'female'
                               else random.randint(168, 192)),
                    has_children=random.choice(HAS_KIDS),
                    wants_children=random.choice(WANTS_KIDS),
                    smoking=random.choice(SMOKING), drinking=random.choice(DRINKING),
                    religion=random.choice(RELIGION), religiosity=random.choice(RELIGIOSITY),
                    tribe_ethnicity=random.choice(TRIBES),
                    education_level=random.choice(EDU),
                    love_languages=random.sample(LOVE, k=2),
                    personality_type=random.choice(
                        ['INFJ', 'ENFP', 'ISTJ', 'ESFJ', 'INTP', 'ENTJ', 'ISFP', 'ESTP']),
                    diet=random.choice(DIET), exercise=random.choice(EXERCISE),
                    pets=random.choice(PETS),
                    prompts=random.sample(prompts_pool, k=min(3, len(prompts_pool))),
                    lifestyle={'job': random.choice(JOBS),
                               'industry': random.choice(INDUSTRY),
                               'languages': list(dict.fromkeys(random.sample(LANGS, k=3)))},
                    photos=[{'type': 'photo', 'url': u} for u in pics],
                    languages_spoken=list(dict.fromkeys(random.sample(LANGS, k=3))),
                )
                # extra columns used by backfill (set if present on model)
                for attr, val in [
                    ('marijuana', random.choice(MARIJUANA)),
                    ('body_type', random.choice(BODY_F if gender == 'female' else BODY_M)),
                    ('zodiac', random.choice(ZODIAC)),
                    ('communication_style', random.choice(COMM)),
                    ('sexual_orientation', 'straight'),
                    ('politics', random.choice(POLITICS)),
                    ('country_code', 'UG'),
                ]:
                    setattr(dp, attr, val)
                if districts:
                    d = random.choice(districts)
                    setattr(dp, 'district_id', d.id)
                    setattr(dp, 'region_id', d.parent_id)
                db.session.add(dp)
                created += 1
                if created % 10 == 0:
                    db.session.commit()
                    print(f'  … {created} users created')

        db.session.commit()
        total_f = Account.query.filter(Account.email.like(f'%{SEED_DOMAIN}')).count()
        print(f'DONE — created {created} seed users this run. Total seed users: {total_f}.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--women', type=int, default=35)
    ap.add_argument('--men', type=int, default=15)
    ap.add_argument('--photos', type=int, default=3)
    ap.add_argument('--pexels-key', default='')
    ap.add_argument('--reset', action='store_true')
    run(ap.parse_args())
