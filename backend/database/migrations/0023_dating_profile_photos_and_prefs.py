"""
Migration 0023: Add photos (JSON) + max_distance_km (INT) to lu_dating_profiles.

photos: ordered list of photo URLs for the dating profile card gallery.
max_distance_km: discovery preference radius in km (saved alongside age prefs).
"""


def up(conn):
    c = conn.cursor()
    try:
        c.execute(
            "ALTER TABLE lu_dating_profiles "
            "ADD COLUMN photos JSON NULL AFTER prompts"
        )
    except Exception:
        pass
    try:
        c.execute(
            "ALTER TABLE lu_dating_profiles "
            "ADD COLUMN max_distance_km SMALLINT UNSIGNED NULL DEFAULT NULL AFTER photos"
        )
    except Exception:
        pass
    conn.commit()


def down(conn):
    c = conn.cursor()
    for col in ('photos', 'max_distance_km'):
        try:
            c.execute(f"ALTER TABLE lu_dating_profiles DROP COLUMN {col}")
        except Exception:
            pass
    conn.commit()
