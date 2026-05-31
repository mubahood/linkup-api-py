"""
Migration 0010: Add hub_post_likes and message_reactions tables.
Also adds discoverability + birth_year columns to lu_dating_profiles.
"""


def up(conn):
    with conn.cursor() as cur:

        # ── lu_hub_post_likes ────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_hub_post_likes` (
                `id`         VARCHAR(36) NOT NULL,
                `post_id`    VARCHAR(36) NOT NULL,
                `account_id` VARCHAR(36) NOT NULL,
                `created_at` TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_post_like` (`post_id`, `account_id`),
                KEY `idx_post_likes_post`    (`post_id`),
                KEY `idx_post_likes_account` (`account_id`),
                CONSTRAINT `fk_pl_post`    FOREIGN KEY (`post_id`)    REFERENCES `lu_hub_posts`(`id`) ON DELETE CASCADE,
                CONSTRAINT `fk_pl_account` FOREIGN KEY (`account_id`) REFERENCES `lu_accounts`(`id`)  ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_hub_post_likes — ensure collation on likes table ─────────────
        # (already created above — this section is a no-op but kept for clarity)

        # ── lu_message_reactions ─────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_message_reactions` (
                `id`         VARCHAR(36)  NOT NULL,
                `message_id` VARCHAR(36)  NOT NULL,
                `account_id` VARCHAR(36)  NOT NULL,
                `emoji`      VARCHAR(10)  NOT NULL DEFAULT '👍',
                `created_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_reaction` (`message_id`, `account_id`, `emoji`),
                KEY `idx_reactions_message` (`message_id`),
                KEY `idx_reactions_account` (`account_id`),
                CONSTRAINT `fk_mr_message` FOREIGN KEY (`message_id`) REFERENCES `lu_messages`(`id`)  ON DELETE CASCADE,
                CONSTRAINT `fk_mr_account` FOREIGN KEY (`account_id`) REFERENCES `lu_accounts`(`id`)  ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_dating_profiles: add discoverability + birth_year ─────────────
        for sql in [
            """ALTER TABLE lu_dating_profiles
               ADD COLUMN `birth_year` SMALLINT DEFAULT NULL
               AFTER `age_max`""",
            """ALTER TABLE lu_dating_profiles
               ADD COLUMN `discoverability` ENUM('discoverable','paused','incognito') NOT NULL DEFAULT 'discoverable'
               AFTER `birth_year`""",
            """ALTER TABLE lu_dating_profiles
               ADD COLUMN `gender` VARCHAR(30) DEFAULT NULL
               AFTER `discoverability`""",
            """ALTER TABLE lu_dating_profiles
               ADD COLUMN `looking_for_gender` VARCHAR(30) DEFAULT NULL
               AFTER `gender`""",
        ]:
            try:
                cur.execute(sql)
            except Exception as e:
                if '1060' not in str(e) and 'Duplicate column' not in str(e):
                    raise

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `lu_hub_post_likes`")
        cur.execute("DROP TABLE IF EXISTS `lu_message_reactions`")
    conn.commit()
