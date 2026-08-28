"""
Migration 0043: widen lu_accounts.account_status to include 'inactive'.

lu_accounts.account_status is a MySQL ENUM('active','suspended','closed') at
the schema level, even though the SQLAlchemy model declares it as a plain
String(20) — the model doesn't enforce the constraint, MySQL does. 'inactive'
is a new soft, reversible dormancy status (distinct from 'suspended', a
policy action, and 'closed', permanent/soft-deleted) used for e.g. seed/demo
accounts. Adding a value to an ENUM is backward compatible — existing rows
and values are untouched.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE `lu_accounts`
            MODIFY COLUMN `account_status` ENUM('active','inactive','suspended','closed')
            DEFAULT 'active'
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM `lu_accounts` WHERE `account_status` = 'inactive'")
        (count,) = cur.fetchone()
        if count:
            raise RuntimeError(
                f"Cannot roll back 0043: {count} lu_accounts row(s) use "
                f"account_status='inactive'. Remove or reassign them first."
            )
        cur.execute("""
            ALTER TABLE `lu_accounts`
            MODIFY COLUMN `account_status` ENUM('active','suspended','closed')
            DEFAULT 'active'
        """)
    conn.commit()
