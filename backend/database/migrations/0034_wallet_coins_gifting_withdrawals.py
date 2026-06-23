"""
Migration 0034: Coins + gifting + withdrawals (TikTok-style economy).

- lu_wallet_accounts gains `coins` (bought, spend-only) and `redeemable`
  (gift earnings awaiting redeem). `balance` stays the withdrawable cash pot.
- lu_gift_catalog: purchasable gifts (price in coins, cash value in UGX).
- lu_gifts: every gift sent (sender → recipient), with fee + cash value.
- lu_withdrawals: mobile-money payout requests + their Flutterwave status.
"""


def _has_column(cur, table, column):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (table, column)
    )
    return cur.fetchone()[0] > 0


def up(conn):
    with conn.cursor() as cur:
        # ── wallet: coins + redeemable ───────────────────────────────────────
        if not _has_column(cur, 'lu_wallet_accounts', 'coins'):
            cur.execute(
                "ALTER TABLE `lu_wallet_accounts` "
                "ADD COLUMN `coins` INT NOT NULL DEFAULT 0 AFTER `balance`")
        if not _has_column(cur, 'lu_wallet_accounts', 'redeemable'):
            cur.execute(
                "ALTER TABLE `lu_wallet_accounts` "
                "ADD COLUMN `redeemable` DECIMAL(14,2) NOT NULL DEFAULT 0.00 AFTER `coins`")

        # ── lu_gift_catalog ──────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_gift_catalog` (
                `id`             VARCHAR(36)   NOT NULL,
                `code`           VARCHAR(40)   NOT NULL,
                `name`           VARCHAR(80)   NOT NULL,
                `icon`           VARCHAR(20)   DEFAULT NULL,
                `price_coins`    INT           NOT NULL,
                `cash_value_ugx` DECIMAL(14,2) NOT NULL,
                `sort_order`     SMALLINT      NOT NULL DEFAULT 0,
                `active`         TINYINT       NOT NULL DEFAULT 1,
                `created_at`     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_gift_code` (`code`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_gifts (gift events / ledger) ──────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_gifts` (
                `id`               VARCHAR(36)   NOT NULL,
                `sender_id`        VARCHAR(36)   NOT NULL,
                `recipient_id`     VARCHAR(36)   NOT NULL,
                `gift_code`        VARCHAR(40)   NOT NULL,
                `gift_name`        VARCHAR(80)   DEFAULT NULL,
                `coins_spent`      INT           NOT NULL,
                `cash_value_ugx`   DECIMAL(14,2) NOT NULL,
                `platform_fee_ugx` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
                `net_ugx`          DECIMAL(14,2) NOT NULL,
                `context_type`     VARCHAR(20)   DEFAULT NULL,
                `context_id`       VARCHAR(36)   DEFAULT NULL,
                `message`          VARCHAR(300)  DEFAULT NULL,
                `created_at`       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_gift_sender`    (`sender_id`),
                KEY `idx_gift_recipient` (`recipient_id`),
                CONSTRAINT `fk_gift_sender`    FOREIGN KEY (`sender_id`)    REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE,
                CONSTRAINT `fk_gift_recipient` FOREIGN KEY (`recipient_id`) REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── lu_withdrawals ───────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_withdrawals` (
                `id`               VARCHAR(36)   NOT NULL,
                `account_id`       VARCHAR(36)   NOT NULL,
                `amount_ugx`       DECIMAL(14,2) NOT NULL,
                `fee_ugx`          DECIMAL(14,2) NOT NULL DEFAULT 0.00,
                `net_ugx`          DECIMAL(14,2) NOT NULL,
                `phone`            VARCHAR(20)   NOT NULL,
                `network`          VARCHAR(20)   NOT NULL,
                `beneficiary_name` VARCHAR(120)  DEFAULT NULL,
                `status`           ENUM('requested','processing','paid','failed','reversed','review') NOT NULL DEFAULT 'requested',
                `flw_transfer_id`  VARCHAR(100)  DEFAULT NULL,
                `flw_reference`    VARCHAR(100)  DEFAULT NULL,
                `failure_reason`   VARCHAR(300)  DEFAULT NULL,
                `requested_at`     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `settled_at`       DATETIME      DEFAULT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_wd_reference` (`flw_reference`),
                KEY `idx_wd_account` (`account_id`),
                CONSTRAINT `fk_wd_account` FOREIGN KEY (`account_id`) REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── Seed the gift catalog (idempotent). cash_value = price_coins * 50 ─
        gifts = [
            ('rose',    'Rose',         '🌹',    1,    50,   1),
            ('heart',   'Heart',        '❤️',    5,    250,  2),
            ('coffee',  'Coffee',       '☕',    10,   500,  3),
            ('teddy',   'Teddy Bear',   '🧸',    20,   1000, 4),
            ('flowers', 'Bouquet',      '💐',    50,   2500, 5),
            ('crown',   'Crown',        '👑',    100,  5000, 6),
            ('ring',    'Ring',         '💍',    300,  15000, 7),
            ('rocket',  'Rocket',       '🚀',    500,  25000, 8),
            ('diamond', 'Diamond',      '💎',    1000, 50000, 9),
        ]
        for code, name, icon, coins, cash, order in gifts:
            cur.execute(
                "INSERT IGNORE INTO `lu_gift_catalog` "
                "(`id`,`code`,`name`,`icon`,`price_coins`,`cash_value_ugx`,`sort_order`,`active`) "
                "VALUES (UUID(), %s, %s, %s, %s, %s, %s, 1)",
                (code, name, icon, coins, cash, order)
            )

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        for t in ['lu_gifts', 'lu_withdrawals', 'lu_gift_catalog']:
            cur.execute(f"DROP TABLE IF EXISTS `{t}`")
        for col in ['redeemable', 'coins']:
            try:
                cur.execute(
                    f"ALTER TABLE `lu_wallet_accounts` DROP COLUMN IF EXISTS `{col}`")
            except Exception:
                pass
    conn.commit()
