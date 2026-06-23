"""
Migration 0017: Uganda institutions reference database.
  - Adds sort_order + is_popular columns to lu_institutions
  - Clears duplicates and seeds comprehensive list of all Uganda universities,
    institutes, and professional bodies (42 entries)
  - Also seeds education_affiliation interest tags for each institution
    so they appear in the interests taxonomy picker
"""
import uuid


def _uid():
    return str(uuid.uuid4())


# (name, short_name, type, district, website, is_popular, sort_order)
INSTITUTIONS = [
    # ── Public Universities (most popular first) ──────────────────────────
    ('Makerere University',                          'Mak',       'university',         'Kampala',    'mak.ac.ug',              1,  1),
    ('Makerere University Business School',          'MUBS',      'university',         'Kampala',    'mubs.ac.ug',             1,  2),
    ('Kyambogo University',                          'KYU',       'university',         'Kampala',    'kyu.ac.ug',              1,  3),
    ('Mbarara University of Science and Technology', 'MUST',      'university',         'Mbarara',    'must.ac.ug',             1,  4),
    ('Gulu University',                              'GU',        'university',         'Gulu',       'gu.ac.ug',               1,  5),
    ('Busitema University',                          'BU',        'university',         'Busia',      'busitema.ac.ug',         1,  6),
    ('Soroti University',                            'SU',        'university',         'Soroti',     'soroti.ac.ug',           0,  7),
    ('Kabale University',                            'KAB',       'university',         'Kabale',     'kabale.ac.ug',           0,  8),
    ('Lira University',                              'LU',        'university',         'Lira',       'lirauniversity.ac.ug',   0,  9),
    ('Muni University',                              'MU',        'university',         'Arua',       'muni.ac.ug',             0, 10),
    ('Mountains of the Moon University',             'MMU',       'university',         'Fort Portal', 'mmu.ac.ug',            0, 11),

    # ── Private Universities ───────────────────────────────────────────────
    ('Uganda Christian University',                  'UCU',       'university',         'Mukono',     'ucu.ac.ug',              1, 12),
    ('Kampala International University',             'KIU',       'university',         'Kampala',    'kiu.ac.ug',              1, 13),
    ('Islamic University in Uganda',                 'IUIU',      'university',         'Mbale',      'iuiu.ac.ug',             1, 14),
    ('Uganda Martyrs University',                    'UMU',       'university',         'Kampala',    'umu.ac.ug',              1, 15),
    ('Ndejje University',                            'NDJ',       'university',         'Luweero',    'ndejjeuniversity.ac.ug', 0, 16),
    ('Bugema University',                            'BUG',       'university',         'Luweero',    'bugema.ac.ug',           0, 17),
    ('St. Lawrence University Uganda',               'SLAU',      'university',         'Kampala',    'slau.ac.ug',             0, 18),
    ('Bishop Stuart University',                     'BSU',       'university',         'Mbarara',    'bishops.ac.ug',          0, 19),
    ('Nkumba University',                            'NU',        'university',         'Wakiso',     'nkumbauniversity.ac.ug', 0, 20),
    ('Victoria University',                          'VU',        'university',         'Kampala',    'vu.ac.ug',               0, 21),
    ('Cavendish University Uganda',                  'CUU',       'university',         'Kampala',    'cavendish.ac.ug',        0, 22),
    ('Muteesa I Royal University',                   'MRU',       'university',         'Kampala',    'mru.ac.ug',              0, 23),
    ('Uganda Pentecostal University',                'UPU',       'university',         'Fort Portal', 'upu.ac.ug',            0, 24),
    ('Kumi University',                              'KUM',       'university',         'Kumi',       'kumi.ac.ug',             0, 25),
    ('All Saints University',                        'ASU',       'university',         'Lira',       None,                     0, 26),
    ('Clarke International University',              'CIU',       'university',         'Kampala',    'clarke.ac.ug',           0, 27),
    ('Kampala University',                           'KU',        'university',         'Kampala',    None,                     0, 28),
    ('King Ceasor University',                       'KCU',       'university',         'Kampala',    'kingceasor.ac.ug',       0, 29),
    ('Uganda College of Commerce Pakwach',           'UCC-P',     'college',            'Nebbi',      None,                     0, 30),

    # ── Institutes & Professional Schools ─────────────────────────────────
    ('Uganda Management Institute',                  'UMI',       'institute',          'Kampala',    'umi.ac.ug',              1, 31),
    ('Law Development Centre',                       'LDC',       'institute',          'Kampala',    'ldc.ac.ug',              1, 32),
    ('Uganda Institute of ICT',                      'UICT',      'institute',          'Kampala',    'uict.ac.ug',             0, 33),
    ('Nsamizi Institute of Social Development',      'NISD',      'institute',          'Kampala',    'nsamizi.ac.ug',          0, 34),
    ('Makerere School of Public Health',             'MakSPH',    'institute',          'Kampala',    'musph.ac.ug',            0, 35),
    ('Nakawa Vocational Training Institute',         'NVTI',      'college',            'Kampala',    None,                     0, 36),
    ('Uganda Technical College Elgon',               'UTC-E',     'college',            'Mbale',      None,                     0, 37),
    ('Uganda Technical College Lira',                'UTC-L',     'college',            'Lira',       None,                     0, 38),

    # ── Professional Bodies ────────────────────────────────────────────────
    ('Institute of Certified Public Accountants of Uganda', 'ICPAU', 'professional_body', 'Kampala', 'icpau.co.ug',           0, 39),
    ('Uganda Law Society',                           'ULS',       'professional_body',  'Kampala',    'ugls.com',               0, 40),
    ('Uganda Medical Association',                   'UMA',       'professional_body',  'Kampala',    None,                     0, 41),
    ('Uganda Engineers Registration Board',          'ERB',       'professional_body',  'Kampala',    None,                     0, 42),
]


def up(conn):
    with conn.cursor() as cur:

        # ── Add columns if they don't exist ───────────────────────────────
        cur.execute("SHOW COLUMNS FROM `lu_institutions` LIKE 'sort_order'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE `lu_institutions` ADD COLUMN `sort_order` SMALLINT NOT NULL DEFAULT 100")

        cur.execute("SHOW COLUMNS FROM `lu_institutions` LIKE 'is_popular'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE `lu_institutions` ADD COLUMN `is_popular` TINYINT(1) NOT NULL DEFAULT 0")

        # ── Expand type ENUM to include new values ─────────────────────────
        cur.execute("""
            ALTER TABLE `lu_institutions`
            MODIFY COLUMN `type`
            ENUM('university','college','polytechnic','institute',
                 'professional_body','secondary','primary','other')
            DEFAULT 'university'
        """)

        # ── Clear existing institutions (rebuilding from scratch) ─────────
        cur.execute("DELETE FROM `lu_institutions`")

        # ── Insert all institutions ────────────────────────────────────────
        for (name, short_name, itype, district, website, is_popular, sort_order) in INSTITUTIONS:
            uid = _uid()
            cur.execute("""
                INSERT INTO `lu_institutions`
                    (id, name, short_name, type, country, district, website, verified, sort_order, is_popular)
                VALUES (%s, %s, %s, %s, 'Uganda', %s, %s, 1, %s, %s)
            """, (uid, name, short_name, itype, district, website, sort_order, is_popular))

        # ── Ensure lu_interest_tags has sort_order + is_active ────────────
        cur.execute("SHOW COLUMNS FROM `lu_interest_tags` LIKE 'sort_order'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE `lu_interest_tags` ADD COLUMN `sort_order` SMALLINT NOT NULL DEFAULT 100")

        cur.execute("SHOW COLUMNS FROM `lu_interest_tags` LIKE 'is_active'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE `lu_interest_tags` ADD COLUMN `is_active` TINYINT(1) NOT NULL DEFAULT 1")

        # ── Rebuild education_affiliation interest tags ────────────────────
        # Delete old ones, re-insert fresh with proper sort_order
        cur.execute("DELETE FROM `lu_interest_tags` WHERE dimension='education_affiliation'")

        for (name, short_name, itype, district, website, is_popular, sort_order) in INSTITUTIONS:
            if itype not in ('university', 'institute', 'college'):
                continue
            slug = 'edu-' + name.lower()
            slug = __import__('re').sub(r'[^a-z0-9]+', '-', slug).strip('-')[:80]
            uid = _uid()
            cur.execute("""
                INSERT INTO `lu_interest_tags`
                    (id, slug, dimension, display_name_en, display_name_lg,
                     popularity, sort_order, is_sensitive, is_active)
                VALUES (%s, %s, 'education_affiliation', %s, %s,
                        %s, %s, 0, 1)
                ON DUPLICATE KEY UPDATE
                    display_name_en=VALUES(display_name_en),
                    sort_order=VALUES(sort_order),
                    popularity=VALUES(popularity)
            """, (uid, slug, name, short_name or name, 200 - sort_order, sort_order))

        # ── Also add some professional network tags ────────────────────────
        extra_tags = [
            ('edu-ugandan-alumni-network', 'Ugandan Alumni Network', 'UA', 50, 50),
            ('edu-stem-graduates-ug',      'STEM Graduates Uganda',  'STEM-UG', 40, 51),
            ('edu-mba-alumni-ug',          'MBA Alumni Uganda',      'MBA', 30, 52),
            ('edu-diaspora-ugandans',      'Ugandan Diaspora Network','Diaspora', 25, 53),
        ]
        for (slug, name_en, name_lg, pop, sord) in extra_tags:
            uid = _uid()
            cur.execute("""
                INSERT INTO `lu_interest_tags`
                    (id, slug, dimension, display_name_en, display_name_lg,
                     popularity, sort_order, is_sensitive, is_active)
                VALUES (%s, %s, 'education_affiliation', %s, %s, %s, %s, 0, 1)
                ON DUPLICATE KEY UPDATE
                    display_name_en=VALUES(display_name_en)
            """, (uid, slug, name_en, name_lg, pop, sord))

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM `lu_institutions`")
        cur.execute("DELETE FROM `lu_interest_tags` WHERE dimension='education_affiliation'")
    conn.commit()
