"""
Migration 0022: Expand lu_dating_profiles.intent ENUM to match Flutter UI values.

Original ENUM: ('casual', 'serious', 'friendship', 'open')
New ENUM: ('open', 'casual', 'serious', 'relationship', 'marriage', 'friendship', 'friends')

The Flutter onboarding sends 'relationship', 'marriage', 'casual', 'open' — the old ENUM
was missing 'relationship' and 'marriage', causing DataError on save.
"""


def up(conn):
    c = conn.cursor()
    try:
        c.execute(
            "ALTER TABLE lu_dating_profiles "
            "MODIFY COLUMN intent "
            "ENUM('open','casual','serious','relationship','marriage','friendship','friends') "
            "DEFAULT 'open'"
        )
        conn.commit()
    except Exception:
        pass


def down(conn):
    c = conn.cursor()
    try:
        c.execute(
            "ALTER TABLE lu_dating_profiles "
            "MODIFY COLUMN intent "
            "ENUM('casual','serious','friendship','open') "
            "DEFAULT 'open'"
        )
        conn.commit()
    except Exception:
        pass
