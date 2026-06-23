"""
Migration 0028: 360° professional profile depth (T-API-100).

Adds attribute columns to lu_professional_profiles for fuller professional
coverage. (`seniority` and `open_to` already existed and are not re-added.)
Interests live in the Interest Graph (lu_interest_profiles) — not duplicated here.
"""

_COLUMNS = [
    ("pronouns",            "VARCHAR(30) NULL"),
    ("tagline",             "VARCHAR(160) NULL"),
    ("industry",            "VARCHAR(120) NULL"),
    ("years_experience",    "INT NULL"),
    ("availability_status", "VARCHAR(30) NULL DEFAULT 'open'"),
    ("social_links",        "JSON NULL"),
    ("portfolio_urls",      "JSON NULL"),
    ("achievements",        "JSON NULL"),
    ("languages_spoken",    "JSON NULL"),
    ("location_origin_id",  "VARCHAR(36) NULL"),
    ("hourly_rate",         "INT NULL"),
    ("hourly_rate_currency","VARCHAR(8) NULL DEFAULT 'UGX'"),
    ("response_rate",       "FLOAT NULL"),
    ("profile_video_url",   "VARCHAR(500) NULL"),
]


def _existing(cur):
    cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'lu_professional_profiles'
    """)
    return {r[0] for r in cur.fetchall()}


def up(conn):
    with conn.cursor() as cur:
        have = _existing(cur)
        for name, ddl in _COLUMNS:
            if name not in have:
                cur.execute(f"ALTER TABLE `lu_professional_profiles` ADD COLUMN `{name}` {ddl}")
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        have = _existing(cur)
        for name, _ in _COLUMNS:
            if name in have:
                cur.execute(f"ALTER TABLE `lu_professional_profiles` DROP COLUMN `{name}`")
    conn.commit()
