"""
Migration 0019: Widen lu_messages.type from ENUM to VARCHAR(20).
  - ENUM('text','image','voice_note','file','system') was too narrow;
    new media types (audio, video, etc.) caused DataError on insert.
  - VARCHAR(20) matches the SQLAlchemy model definition (String(20)).
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE `lu_messages`
            MODIFY COLUMN `type` VARCHAR(20) NOT NULL DEFAULT 'text'
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE `lu_messages`
            MODIFY COLUMN `type`
            ENUM('text','image','voice_note','file','system')
            NOT NULL DEFAULT 'text'
        """)
    conn.commit()
