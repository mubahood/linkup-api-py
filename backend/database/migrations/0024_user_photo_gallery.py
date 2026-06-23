"""
Migration 0024: User photo gallery.

lu_user_photos stores every photo a user uploads. Each entry can be:
  - a regular gallery photo (is_profile_photo=0, is_cover_photo=0)
  - the active profile photo (is_profile_photo=1)
  - the active cover photo  (is_cover_photo=1)

is_public controls whether the photo appears in the public-facing gallery.
"""


def up(conn):
    c = conn.cursor()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS lu_user_photos (
                id          VARCHAR(36)  NOT NULL PRIMARY KEY,
                account_id  VARCHAR(36)  NOT NULL,
                url         VARCHAR(500) NOT NULL,
                is_profile_photo TINYINT(1) NOT NULL DEFAULT 0,
                is_cover_photo   TINYINT(1) NOT NULL DEFAULT 0,
                is_public        TINYINT(1) NOT NULL DEFAULT 1,
                caption     VARCHAR(300) NULL,
                photo_type  VARCHAR(50)  NOT NULL DEFAULT 'gallery',
                sort_order  SMALLINT     NOT NULL DEFAULT 0,
                created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                         ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_uphotos_account
                    FOREIGN KEY (account_id)
                    REFERENCES lu_accounts(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    except Exception:
        pass
    # Indexes
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_uphotos_account   ON lu_user_photos (account_id)",
        "CREATE INDEX IF NOT EXISTS idx_uphotos_profile   ON lu_user_photos (account_id, is_profile_photo)",
        "CREATE INDEX IF NOT EXISTS idx_uphotos_cover     ON lu_user_photos (account_id, is_cover_photo)",
        "CREATE INDEX IF NOT EXISTS idx_uphotos_public    ON lu_user_photos (account_id, is_public)",
    ]:
        try:
            c.execute(idx_sql)
        except Exception:
            pass
    conn.commit()


def down(conn):
    c = conn.cursor()
    try:
        c.execute("DROP TABLE IF EXISTS lu_user_photos")
    except Exception:
        pass
    conn.commit()
