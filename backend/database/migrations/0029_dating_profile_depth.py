"""
Migration 0029: 360° dating profile depth (T-API-101).

Adds lifestyle / values / preference columns to lu_dating_profiles.
(`prompts`, `lifestyle`, `photos`, `age_min/max`, `intent`, `gender`,
`looking_for_gender`, `max_distance_km` already existed — not re-added.)

Sensitive fields (`religion`, `religiosity`, `tribe_ethnicity`) are stored but
treated as match-only / opt-in display via `sensitive_optin`; they must never
appear on professional surfaces (mode separation, ARCHITECTURE.md §7.6).
"""

_COLUMNS = [
    ("height_cm",         "INT NULL"),
    ("relationship_goal", "VARCHAR(30) NULL"),
    ("has_children",      "VARCHAR(20) NULL"),
    ("wants_children",    "VARCHAR(20) NULL"),
    ("smoking",           "VARCHAR(20) NULL"),
    ("drinking",          "VARCHAR(20) NULL"),
    ("religion",          "VARCHAR(60) NULL"),       # sensitive
    ("religiosity",       "VARCHAR(30) NULL"),       # sensitive
    ("tribe_ethnicity",   "VARCHAR(60) NULL"),       # sensitive
    ("education_level",   "VARCHAR(40) NULL"),
    ("love_languages",    "JSON NULL"),
    ("personality_type",  "VARCHAR(8) NULL"),
    ("diet",              "VARCHAR(40) NULL"),
    ("exercise",          "VARCHAR(30) NULL"),
    ("pets",              "JSON NULL"),
    ("voice_prompt_url",  "VARCHAR(500) NULL"),
    ("deal_breakers",     "JSON NULL"),
    ("sensitive_optin",   "JSON NULL"),              # {"religion": true, ...}
]


def _existing(cur):
    cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'lu_dating_profiles'
    """)
    return {r[0] for r in cur.fetchall()}


def up(conn):
    with conn.cursor() as cur:
        have = _existing(cur)
        for name, ddl in _COLUMNS:
            if name not in have:
                cur.execute(f"ALTER TABLE `lu_dating_profiles` ADD COLUMN `{name}` {ddl}")
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        have = _existing(cur)
        for name, _ in _COLUMNS:
            if name in have:
                cur.execute(f"ALTER TABLE `lu_dating_profiles` DROP COLUMN `{name}`")
    conn.commit()
