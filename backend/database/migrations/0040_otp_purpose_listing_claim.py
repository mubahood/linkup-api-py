"""
Migration 0040: widen lu_otp_requests.purpose to include 'listing_claim'.

lu_otp_requests.purpose is a MySQL ENUM('register','login','reset','verify')
at the schema level, even though the SQLAlchemy model declares it as a plain
String(20) — the model doesn't enforce the constraint, MySQL does. The
listings claim flow (Phase 5) needs its own purpose value so OTPs sent for a
listing claim are distinguishable in lu_otp_requests from login/register/reset
OTPs. Adding a value to an ENUM is backward compatible — existing rows and
values are untouched.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE `lu_otp_requests`
            MODIFY COLUMN `purpose` ENUM('register','login','reset','verify','listing_claim')
            DEFAULT 'login'
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        # Only safe to narrow back if nothing actually used the new value.
        cur.execute("SELECT COUNT(*) FROM `lu_otp_requests` WHERE `purpose` = 'listing_claim'")
        (count,) = cur.fetchone()
        if count:
            raise RuntimeError(
                f"Cannot roll back 0040: {count} lu_otp_requests row(s) use "
                f"purpose='listing_claim'. Remove or reassign them first."
            )
        cur.execute("""
            ALTER TABLE `lu_otp_requests`
            MODIFY COLUMN `purpose` ENUM('register','login','reset','verify')
            DEFAULT 'login'
        """)
    conn.commit()
