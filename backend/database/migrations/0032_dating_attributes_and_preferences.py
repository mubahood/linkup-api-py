"""
Migration 0032: deep dating attributes + structured preferences (P-API-03 / P-API-04).

Adds the remaining "who I am" attribute columns and a single `preferences` JSON
column holding the full "who I'm looking for" object (each field carries an
optional is_dealbreaker flag). Idempotent (INFORMATION_SCHEMA-guarded).
"""

_COLUMNS = [
    # ── Attributes (who I am) ──────────────────────────────────────────────
    ("sexual_orientation", "VARCHAR(30) NULL"),
    ("marijuana",          "VARCHAR(20) NULL"),
    ("politics",           "VARCHAR(30) NULL"),       # sensitive
    ("body_type",          "VARCHAR(30) NULL"),
    ("zodiac",             "VARCHAR(20) NULL"),
    ("communication_style","VARCHAR(30) NULL"),
    ("languages_spoken",   "JSON NULL"),
    ("industry",           "VARCHAR(40) NULL"),
    ("region_id",          "VARCHAR(36) NULL"),
    ("district_id",        "VARCHAR(36) NULL"),
    ("country_code",       "VARCHAR(10) NULL DEFAULT 'UG'"),
    # ── Preferences (who I'm looking for) ──────────────────────────────────
    ("preferences",        "JSON NULL"),
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
