"""
Migration 0014: Dating safety toolkit tables.
  lu_safety_contacts — trusted contacts (phone or lu_account)
  lu_date_checkins   — scheduled date check-ins with auto-ping
"""


def up(conn):
    with conn.cursor() as cur:

        # ── lu_safety_contacts ────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_safety_contacts` (
                `id`           VARCHAR(36)   NOT NULL,
                `account_id`   VARCHAR(36)   NOT NULL,
                `name`         VARCHAR(200)  NOT NULL,
                `phone`        VARCHAR(30)   DEFAULT NULL,
                `linked_account_id` VARCHAR(36) DEFAULT NULL,
                `created_at`   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_sc_account` (`account_id`),
                CONSTRAINT `fk_sc_account` FOREIGN KEY (`account_id`)
                    REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_date_checkins ──────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_date_checkins` (
                `id`            VARCHAR(36)   NOT NULL,
                `account_id`    VARCHAR(36)   NOT NULL,
                `match_id`      VARCHAR(36)   DEFAULT NULL,
                `location_text` VARCHAR(500)  DEFAULT NULL,
                `check_time`    DATETIME      NOT NULL,
                `status`        ENUM('active','checked_in','missed','cancelled')
                                NOT NULL DEFAULT 'active',
                `panic_sent`    TINYINT(1)    NOT NULL DEFAULT 0,
                `note`          TEXT          DEFAULT NULL,
                `created_at`    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_dc_account` (`account_id`),
                CONSTRAINT `fk_dc_account` FOREIGN KEY (`account_id`)
                    REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        for t in ['lu_date_checkins', 'lu_safety_contacts']:
            cur.execute(f"DROP TABLE IF EXISTS `{t}`")
    conn.commit()
