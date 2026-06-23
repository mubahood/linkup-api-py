"""
Migration 0013: Add is_premium flag to lu_accounts + lat/lng for Sparks distance filtering.
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
        if not _has_column(cur, 'lu_accounts', 'is_premium'):
            cur.execute(
                "ALTER TABLE `lu_accounts` "
                "ADD COLUMN `is_premium` TINYINT(1) NOT NULL DEFAULT 0"
            )

        if not _has_column(cur, 'lu_accounts', 'last_lat'):
            cur.execute(
                "ALTER TABLE `lu_accounts` "
                "ADD COLUMN `last_lat` DECIMAL(10,7) DEFAULT NULL, "
                "ADD COLUMN `last_lng` DECIMAL(10,7) DEFAULT NULL, "
                "ADD COLUMN `last_seen_at` DATETIME DEFAULT NULL"
            )

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        for col in ['is_premium', 'last_lat', 'last_lng', 'last_seen_at']:
            try:
                cur.execute(f"ALTER TABLE `lu_accounts` DROP COLUMN IF EXISTS `{col}`")
            except Exception:
                pass
    conn.commit()
