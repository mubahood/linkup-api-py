"""
Migration 0021: Add requirements (JSON) and work_mode (VARCHAR) to lu_jobs
"""


def up(conn):
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE lu_jobs ADD COLUMN requirements JSON NULL")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE lu_jobs ADD COLUMN work_mode VARCHAR(20) DEFAULT 'onsite'")
    except Exception:
        pass
    conn.commit()


def down(conn):
    c = conn.cursor()
    for col in ('requirements', 'work_mode'):
        try:
            c.execute(f"ALTER TABLE lu_jobs DROP COLUMN {col}")
        except Exception:
            pass
    conn.commit()
