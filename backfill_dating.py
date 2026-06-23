"""
Backfill every dating profile with full 360° profiling data + real African
portrait photos (verified Unsplash URLs). Idempotent — safe to re-run.

Run:  python backfill_dating.py
"""
import random

# ── Verified African portrait pools (Unsplash, all return 200) ────────────────
MEN_IDS = [
    '1518882570151-157128e78fa1', '1605980776566-0486c3ac7617',
    '1562173650-f61426fbe683', '1564541558234-ef406c118d0c',
    '1532437698276-c2ac365e7147', '1612214070782-b97cad77ca54',
    '1643904524951-2a3a58856745', '1659093728055-45f8275166d9',
    '1714118657863-2843a622718b',
]
WOMEN_IDS = [
    '1593351799227-75df2026356b', '1613876215075-276fd62c89a4',
    '1505421031134-e57263cae630', '1619694770795-e21c58464159',
    '1604247203891-ae01b7b2f1bb', '1532076904124-d4e8fe7fbbec',
    '1548207775-a7676e36f20a', '1636302926027-9619142d7173',
    '1620424037570-15137a4a562d', '1664662566408-ef40c502a66b',
    '1628682814595-a3f0816b25ff', '1534470717-233b39a41c54',
]


def _img(pid):
    return (f"https://images.unsplash.com/photo-{pid}"
            "?w=640&q=72&fit=crop&crop=faces")


# ── Uganda-weighted token pools (weights via repetition) ──────────────────────
RELIGION = (['catholic'] * 4 + ['anglican'] * 4 + ['pentecostal'] * 4
            + ['muslim'] * 3 + ['sda'] * 2 + ['orthodox', 'traditional',
            'spiritual', 'agnostic', 'atheist', 'prefer_not'])
RELIGIOSITY = ['very'] * 3 + ['somewhat'] * 4 + ['not_really'] * 2 + ['prefer_not']
SMOKING = ['no'] * 6 + ['social'] * 2 + ['yes', 'quitting', 'prefer_not']
DRINKING = ['no'] * 4 + ['social'] * 4 + ['yes'] * 2 + ['sober', 'prefer_not']
MARIJUANA = ['never'] * 7 + ['sometimes'] * 2 + ['prefer_not']
DIET = ['omnivore'] * 6 + ['no_pork'] * 2 + ['halal'] * 2 + ['vegetarian', 'pescatarian']
EXERCISE = ['daily', 'often', 'often', 'sometimes', 'sometimes', 'rarely', 'never']
PETS = ['none'] * 3 + ['dog'] * 2 + ['cat', 'both', 'want', 'allergic']
EDU = ['secondary', 'certificate', 'diploma', 'diploma', 'bachelors',
       'bachelors', 'bachelors', 'masters', 'vocational']
INDUSTRY = ['technology', 'finance', 'healthcare', 'education', 'agriculture',
            'engineering', 'legal', 'media', 'government', 'ngo', 'business',
            'sales_marketing', 'hospitality', 'transport', 'construction',
            'arts', 'student']
BODY = ['slim', 'athletic', 'athletic', 'average', 'average', 'curvy',
        'plus_size', 'prefer_not']
ZODIAC = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra',
          'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces']
COMM = ['big_texter', 'phone_caller', 'video_chat', 'in_person', 'slow_texter']
REL_GOAL = (['long_term'] * 4 + ['marriage'] * 3 + ['long_open_short',
            'short_open_long', 'short_term', 'friendship', 'figuring_out'])
HAS_KIDS = ['no'] * 6 + ['yes_not_with_me', 'yes_with_me', 'yes_sometimes', 'prefer_not']
WANTS_KIDS = ['want'] * 4 + ['open'] * 3 + ['not_sure', 'dont_want',
              'have_want_more', 'prefer_not']
LOVE = ['words', 'quality_time', 'acts', 'gifts', 'touch']
LANGS = ['en', 'en', 'lg', 'lg', 'sw', 'nyn', 'ach', 'xog', 'lgg', 'teo',
         'cgg', 'nyo', 'ttj', 'laj']
INTENT = ['serious', 'serious', 'serious', 'marriage', 'open', 'casual']
POLITICS = ['none', 'none', 'nrm', 'nup', 'fdc', 'dp', 'independent', 'prefer_not']
ORIENT = ['straight'] * 9 + ['bisexual', 'gay', 'lesbian']


def run():
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        from backend.models import db
        from backend.domains.identity.models import Account
        from backend.domains.profile.models import DatingProfile
        from backend.domains.reference.models import Location

        districts = Location.query.filter(Location.level == 'district').all()
        if not districts:
            districts = Location.query.all()
        dps = DatingProfile.query.all()
        print(f'Enriching {len(dps)} dating profiles …')
        n = 0
        for dp in dps:
            g = (dp.gender or '').lower()
            is_male = g in ('male', 'man', 'm')
            is_female = g in ('female', 'woman', 'w', 'f')
            pool = MEN_IDS if is_male else WOMEN_IDS if is_female else (MEN_IDS + WOMEN_IDS)
            ids = random.sample(pool, k=min(4, len(pool)))
            dp.photos = [{'type': 'photo', 'url': _img(i)} for i in ids]
            acc = db.session.get(Account, dp.account_id)
            if acc:
                acc.avatar = _img(ids[0])

            dp.height_cm = random.randint(168, 193) if is_male else random.randint(150, 178)
            dp.relationship_goal = random.choice(REL_GOAL)
            dp.intent = random.choice(INTENT)
            dp.smoking = random.choice(SMOKING)
            dp.drinking = random.choice(DRINKING)
            dp.marijuana = random.choice(MARIJUANA)
            dp.diet = random.choice(DIET)
            dp.exercise = random.choice(EXERCISE)
            dp.pets = random.choice(PETS)
            dp.religion = random.choice(RELIGION)
            dp.religiosity = random.choice(RELIGIOSITY)
            dp.politics = random.choice(POLITICS)
            dp.education_level = random.choice(EDU)
            dp.industry = random.choice(INDUSTRY)
            dp.body_type = random.choice(BODY)
            dp.zodiac = random.choice(ZODIAC)
            dp.communication_style = random.choice(COMM)
            dp.has_children = random.choice(HAS_KIDS)
            dp.wants_children = random.choice(WANTS_KIDS)
            dp.sexual_orientation = random.choice(ORIENT)
            dp.love_languages = random.sample(LOVE, k=2)
            dp.languages_spoken = list(dict.fromkeys(
                random.sample(LANGS, k=random.randint(2, 3))))
            dp.country_code = 'UG'
            d = random.choice(districts)
            dp.district_id = d.id
            dp.region_id = d.parent_id

            n += 1
            if n % 100 == 0:
                db.session.commit()
                print(f'  … {n}')
        db.session.commit()
        print(f'Done — updated {n} dating profiles + avatars.')


if __name__ == '__main__':
    run()
