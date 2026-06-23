"""
Migration 0015: Mentorship system.
  lu_mentor_profiles  — professionals advertising mentorship availability
  lu_mentorship_requests — mentee → mentor pairing requests
"""


def up(conn):
    with conn.cursor() as cur:

        # ── lu_mentor_profiles ────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_mentor_profiles` (
                `id`               VARCHAR(36)   NOT NULL,
                `account_id`       VARCHAR(36)   NOT NULL,
                `headline`         VARCHAR(300)  DEFAULT NULL,
                `bio`              TEXT          DEFAULT NULL,
                `skills`           JSON          DEFAULT NULL,
                `industries`       JSON          DEFAULT NULL,
                `mentorship_mode`  ENUM('online','in_person','both') NOT NULL DEFAULT 'both',
                `session_duration` SMALLINT      NOT NULL DEFAULT 60,
                `capacity`         TINYINT       NOT NULL DEFAULT 3,
                `is_open`          TINYINT(1)    NOT NULL DEFAULT 1,
                `session_count`    SMALLINT      NOT NULL DEFAULT 0,
                `created_at`       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at`       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_mp_account` (`account_id`),
                CONSTRAINT `fk_mp_account` FOREIGN KEY (`account_id`)
                    REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_mentorship_requests ────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_mentorship_requests` (
                `id`            VARCHAR(36)   NOT NULL,
                `mentee_id`     VARCHAR(36)   NOT NULL,
                `mentor_id`     VARCHAR(36)   NOT NULL,
                `message`       TEXT          DEFAULT NULL,
                `goals`         TEXT          DEFAULT NULL,
                `status`        ENUM('pending','accepted','declined','completed','withdrawn')
                                NOT NULL DEFAULT 'pending',
                `responded_at`  DATETIME      DEFAULT NULL,
                `completed_at`  DATETIME      DEFAULT NULL,
                `created_at`    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at`    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_mr_pair` (`mentee_id`, `mentor_id`),
                KEY `idx_mr_mentor`  (`mentor_id`),
                KEY `idx_mr_mentee`  (`mentee_id`),
                CONSTRAINT `fk_mr_mentee` FOREIGN KEY (`mentee_id`)
                    REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE,
                CONSTRAINT `fk_mr_mentor` FOREIGN KEY (`mentor_id`)
                    REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        for t in ['lu_mentorship_requests', 'lu_mentor_profiles']:
            cur.execute(f"DROP TABLE IF EXISTS `{t}`")
    conn.commit()
