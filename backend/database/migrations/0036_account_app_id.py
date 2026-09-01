"""
Migration 0036: lu_accounts.app_id — which app (linkup | abanoonya) an
account signed up through. Existing rows backfill to 'linkup' (the original,
single-brand history before Abanoonya Pro existed as a separate signup path).
New signups are tagged from the X-App header going forward (see
backend/domains/identity/service.py). Used to keep professional-mode
notifications (jobs, mentorship, links, endorsements) from ever reaching an
Abanoonya Pro account.
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
        if not _has_column(cur, 'lu_accounts', 'app_id'):
            cur.execute(
                "ALTER TABLE `lu_accounts` "
                "ADD COLUMN `app_id` VARCHAR(20) NOT NULL DEFAULT 'linkup' AFTER `kyc_level`")
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        try:
            cur.execute("ALTER TABLE `lu_accounts` DROP COLUMN IF EXISTS `app_id`")
        except Exception:
            pass
    conn.commit()
