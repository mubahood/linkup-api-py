"""
Migration 0016: Email-primary authentication.
  - lu_accounts.phone → nullable (email becomes the primary identifier)
  - lu_otp_requests.phone → VARCHAR(300) to accommodate email addresses
"""


def up(conn):
    with conn.cursor() as cur:
        # Make phone nullable — new accounts registered via email have no phone yet
        cur.execute("""
            ALTER TABLE `lu_accounts`
            MODIFY COLUMN `phone` VARCHAR(30) NULL
        """)

        # Expand the OTP identifier column to hold email addresses (up to 254 chars)
        cur.execute("""
            ALTER TABLE `lu_otp_requests`
            MODIFY COLUMN `phone` VARCHAR(300) NOT NULL
        """)

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE `lu_otp_requests`
            MODIFY COLUMN `phone` VARCHAR(30) NOT NULL
        """)
        # Note: reverting phone to NOT NULL would fail if any accounts have phone=NULL
    conn.commit()
