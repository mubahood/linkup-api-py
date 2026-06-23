"""
Migration 0012: v1 wallet tables + job referrals table.
"""


def up(conn):
    with conn.cursor() as cur:

        # ── lu_wallet_accounts ────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_wallet_accounts` (
                `id`              VARCHAR(36)    NOT NULL,
                `account_id`      VARCHAR(36)    NOT NULL,
                `balance`         DECIMAL(14,2)  NOT NULL DEFAULT 0.00,
                `currency`        VARCHAR(5)     NOT NULL DEFAULT 'UGX',
                `total_credited`  DECIMAL(14,2)  NOT NULL DEFAULT 0.00,
                `total_debited`   DECIMAL(14,2)  NOT NULL DEFAULT 0.00,
                `flw_customer_id` VARCHAR(100)   DEFAULT NULL,
                `created_at`      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at`      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_wallet_account` (`account_id`),
                CONSTRAINT `fk_wa_account` FOREIGN KEY (`account_id`) REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_wallet_transactions ────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_wallet_transactions` (
                `id`             VARCHAR(36)    NOT NULL,
                `wallet_id`      VARCHAR(36)    NOT NULL,
                `account_id`     VARCHAR(36)    NOT NULL,
                `type`           ENUM('credit','debit') NOT NULL,
                `category`       VARCHAR(50)    NOT NULL DEFAULT 'topup',
                `amount`         DECIMAL(14,2)  NOT NULL,
                `balance_before` DECIMAL(14,2)  NOT NULL DEFAULT 0.00,
                `balance_after`  DECIMAL(14,2)  NOT NULL DEFAULT 0.00,
                `reference`      VARCHAR(100)   DEFAULT NULL,
                `description`    TEXT           DEFAULT NULL,
                `status`         ENUM('pending','completed','failed','reversed') NOT NULL DEFAULT 'completed',
                `flw_tx_id`      VARCHAR(100)   DEFAULT NULL,
                `extra_data`     JSON           DEFAULT NULL,
                `created_at`     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_wt_wallet`  (`wallet_id`),
                KEY `idx_wt_account` (`account_id`),
                CONSTRAINT `fk_wt_wallet`  FOREIGN KEY (`wallet_id`)  REFERENCES `lu_wallet_accounts`(`id`) ON DELETE CASCADE,
                CONSTRAINT `fk_wt_account` FOREIGN KEY (`account_id`) REFERENCES `lu_accounts`(`id`)        ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_job_referrals ──────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_job_referrals` (
                `id`            VARCHAR(36)   NOT NULL,
                `job_id`        VARCHAR(36)   NOT NULL,
                `requester_id`  VARCHAR(36)   NOT NULL,
                `referrer_id`   VARCHAR(36)   NOT NULL,
                `message`       TEXT          DEFAULT NULL,
                `status`        ENUM('pending','accepted','declined','referred') NOT NULL DEFAULT 'pending',
                `responded_at`  DATETIME      DEFAULT NULL,
                `created_at`    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at`    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_referral` (`job_id`, `requester_id`, `referrer_id`),
                KEY `idx_jr_job`       (`job_id`),
                KEY `idx_jr_requester` (`requester_id`),
                KEY `idx_jr_referrer`  (`referrer_id`),
                CONSTRAINT `fk_jr_job`       FOREIGN KEY (`job_id`)       REFERENCES `lu_jobs`(`id`)     ON DELETE CASCADE,
                CONSTRAINT `fk_jr_requester` FOREIGN KEY (`requester_id`) REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE,
                CONSTRAINT `fk_jr_referrer`  FOREIGN KEY (`referrer_id`)  REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_password_resets ────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_password_resets` (
                `id`         VARCHAR(36)  NOT NULL,
                `phone`      VARCHAR(30)  NOT NULL,
                `code_hash`  VARCHAR(500) NOT NULL,
                `expires_at` DATETIME     NOT NULL,
                `used_at`    DATETIME     DEFAULT NULL,
                `created_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_pr_phone` (`phone`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_endorsements ───────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_endorsements` (
                `id`          VARCHAR(36)  NOT NULL,
                `endorser_id` VARCHAR(36)  NOT NULL,
                `endorsee_id` VARCHAR(36)  NOT NULL,
                `tag_id`      VARCHAR(36)  NOT NULL,
                `body`        TEXT         DEFAULT NULL,
                `weight`      DECIMAL(3,2) NOT NULL DEFAULT 0.50,
                `created_at`  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_endorsement` (`endorser_id`, `endorsee_id`, `tag_id`),
                KEY `idx_end_endorsee` (`endorsee_id`),
                CONSTRAINT `fk_end_endorser` FOREIGN KEY (`endorser_id`) REFERENCES `lu_accounts`(`id`)       ON DELETE CASCADE,
                CONSTRAINT `fk_end_endorsee` FOREIGN KEY (`endorsee_id`) REFERENCES `lu_accounts`(`id`)       ON DELETE CASCADE,
                CONSTRAINT `fk_end_tag`      FOREIGN KEY (`tag_id`)      REFERENCES `lu_interest_tags`(`id`)  ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        for t in ['lu_job_referrals', 'lu_endorsements', 'lu_password_resets',
                  'lu_wallet_transactions', 'lu_wallet_accounts']:
            cur.execute(f"DROP TABLE IF EXISTS `{t}`")
    conn.commit()
