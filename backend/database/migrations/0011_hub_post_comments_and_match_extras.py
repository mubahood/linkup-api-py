"""
Migration 0011: Hub post comments + match state fields.
"""


def up(conn):
    with conn.cursor() as cur:

        # ── lu_hub_post_comments ─────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_hub_post_comments` (
                `id`          VARCHAR(36)  NOT NULL,
                `post_id`     VARCHAR(36)  NOT NULL,
                `account_id`  VARCHAR(36)  NOT NULL,
                `parent_id`   VARCHAR(36)  DEFAULT NULL,
                `content`     TEXT         NOT NULL,
                `like_count`  INT          NOT NULL DEFAULT 0,
                `created_at`  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at`  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `deleted_at`  DATETIME     DEFAULT NULL,
                PRIMARY KEY (`id`),
                KEY `idx_pc_post`       (`post_id`),
                KEY `idx_pc_account`    (`account_id`),
                KEY `idx_pc_parent`     (`parent_id`),
                KEY `idx_pc_created_at` (`created_at`),
                CONSTRAINT `fk_pc_post`    FOREIGN KEY (`post_id`)    REFERENCES `lu_hub_posts`(`id`) ON DELETE CASCADE,
                CONSTRAINT `fk_pc_account` FOREIGN KEY (`account_id`) REFERENCES `lu_accounts`(`id`)  ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_matches: add state + met_at columns ───────────────────────────
        for sql in [
            """ALTER TABLE lu_matches
               ADD COLUMN `state` ENUM('active','unmatched','expired') NOT NULL DEFAULT 'active'
               AFTER `thread_id`""",
            """ALTER TABLE lu_matches
               ADD COLUMN `met_at` DATETIME DEFAULT NULL
               AFTER `state`""",
            """ALTER TABLE lu_matches
               ADD COLUMN `unmatched_by` VARCHAR(36) DEFAULT NULL
               AFTER `met_at`""",
            """ALTER TABLE lu_matches
               ADD COLUMN `unmatched_at` DATETIME DEFAULT NULL
               AFTER `unmatched_by`""",
        ]:
            try:
                cur.execute(sql)
            except Exception as e:
                if '1060' not in str(e) and 'Duplicate column' not in str(e):
                    raise

        # ── lu_messages: add reply_to_id column ──────────────────────────────
        for sql in [
            """ALTER TABLE lu_messages
               ADD COLUMN `reply_to_id` VARCHAR(36) DEFAULT NULL
               AFTER `type`""",
        ]:
            try:
                cur.execute(sql)
            except Exception as e:
                if '1060' not in str(e) and 'Duplicate column' not in str(e):
                    raise

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `lu_hub_post_comments`")
    conn.commit()
