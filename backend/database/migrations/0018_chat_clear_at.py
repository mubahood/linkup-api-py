"""
Migration 0018: Add cleared_at to lu_thread_participants.
  - Allows per-participant "clear chat" without affecting the other side.
    Messages created before cleared_at are hidden for that participant.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE `lu_thread_participants`
            ADD COLUMN `cleared_at` DATETIME NULL DEFAULT NULL
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE `lu_thread_participants`
            DROP COLUMN `cleared_at`
        """)
    conn.commit()
