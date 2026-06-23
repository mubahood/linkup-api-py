"""
Migration 0033: Add location_updated_at to lu_accounts.

Tracks when a member's GPS was last recorded (distinct from last_seen_at, which
presence bumps every ~90s). Powers the "refresh your location weekly" prompt and
keeps Sparks distance matching honest.
"""


def _has_column(cur, table, column):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (table, column)
    )
    return cur.fetchone()[0] > 0


def up(conn):
    with conn.cursor() as cur:
        if not _has_column(cur, 'lu_accounts', 'location_updated_at'):
            cur.execute(
                "ALTER TABLE `lu_accounts` "
                "ADD COLUMN `location_updated_at` DATETIME DEFAULT NULL AFTER `last_lng`"
            )
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        try:
            cur.execute(
                "ALTER TABLE `lu_accounts` DROP COLUMN IF EXISTS `location_updated_at`")
        except Exception:
            pass
    conn.commit()
