"""
Migration 0020: Add view_count to lu_jobs
"""


def up(conn):
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE lu_jobs ADD COLUMN view_count INT DEFAULT 0")
    except Exception:
        pass  # column already exists
    conn.commit()


def down(conn):
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE lu_jobs DROP COLUMN view_count")
    except Exception:
        pass
    conn.commit()
