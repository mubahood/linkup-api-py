"""
Migration 0031: add 'withdrawn' to lu_applications.status enum.

The jobs domain uses status='withdrawn' (apply re-application + the withdraw
endpoint), but the DB enum never included it → withdraw raised a SQL
"Data truncated" 500. This aligns the column with the code's VALID_STATUSES.
"""

_ENUM = ("enum('applied','reviewed','shortlisted','interview',"
         "'rejected','hired','withdrawn')")


def up(conn):
    with conn.cursor() as cur:
        cur.execute(
            f"ALTER TABLE `lu_applications` "
            f"MODIFY COLUMN `status` {_ENUM} NOT NULL DEFAULT 'applied'"
        )
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute(
            "ALTER TABLE `lu_applications` "
            "MODIFY COLUMN `status` "
            "enum('applied','reviewed','shortlisted','interview','rejected','hired') "
            "NOT NULL DEFAULT 'applied'"
        )
    conn.commit()
