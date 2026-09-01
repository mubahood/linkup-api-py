"""
Migration 0041: subscription plans + subscription ledger.

lu_subscription_plans is the admin-editable pricing/limits catalog (mirrors the
lu_gift_catalog pattern) — a free plan plus 4 paid tiers per app, each carrying
a `limits` JSON blob (swipes/day, chats/day, who-liked-me visibility, contact
reveal, etc.) so numbers can be retuned from the admin console with no deploy.

lu_subscriptions is the purchase ledger (mirrors lu_wallet_transactions) — one
row per purchase/renewal, tracked through pending -> active -> expired.

lu_accounts gets two denormalized columns (subscription_plan_id,
subscription_expires_at) so a per-request entitlement check never has to join
the ledger table — the active plan is always resolvable from the account row
alone. is_premium is kept in sync by application code, not by this migration.
"""
import uuid
import json


FREE_LIMITS = {
    "swipes_per_day": 15, "standouts_per_day": 1, "chats_per_day": 10,
    "can_view_likers": False, "can_view_profile_viewers": False,
    "can_reveal_contact": False, "rewinds_per_day": 0,
    "boosts_per_month": 0, "priority_deck": False,
    "read_receipts": False, "advanced_filters": False,
    "streak_freeze_per_month": 0,
}
WEEKLY_LIMITS = {
    "swipes_per_day": 50, "standouts_per_day": 5, "chats_per_day": -1,
    "can_view_likers": True, "can_view_profile_viewers": False,
    "can_reveal_contact": False, "rewinds_per_day": 5,
    "boosts_per_month": 1, "priority_deck": False,
    "read_receipts": True, "advanced_filters": True,
    "streak_freeze_per_month": 0,
}
BIWEEKLY_LIMITS = {
    "swipes_per_day": 100, "standouts_per_day": 8, "chats_per_day": -1,
    "can_view_likers": True, "can_view_profile_viewers": True,
    "can_reveal_contact": True, "rewinds_per_day": 10,
    "boosts_per_month": 2, "priority_deck": False,
    "read_receipts": True, "advanced_filters": True,
    "streak_freeze_per_month": 1,
}
MONTHLY_LIMITS = {
    "swipes_per_day": -1, "standouts_per_day": 12, "chats_per_day": -1,
    "can_view_likers": True, "can_view_profile_viewers": True,
    "can_reveal_contact": True, "rewinds_per_day": -1,
    "boosts_per_month": 4, "priority_deck": True,
    "read_receipts": True, "advanced_filters": True,
    "streak_freeze_per_month": 2,
}
FIVE_MONTH_LIMITS = {
    "swipes_per_day": -1, "standouts_per_day": 20, "chats_per_day": -1,
    "can_view_likers": True, "can_view_profile_viewers": True,
    "can_reveal_contact": True, "rewinds_per_day": -1,
    "boosts_per_month": 8, "priority_deck": True,
    "read_receipts": True, "advanced_filters": True,
    "streak_freeze_per_month": 5,
}

# (code, name, tagline, price_ugx, duration_days, sort_order, badge_color, limits)
PLAN_ROWS = [
    ('free', 'Free', 'Get started with the basics', 0, 0, 0, None, FREE_LIMITS),
    ('weekly', 'Weekly', 'A week of unlocked swiping', 5000, 7, 1, '#8B5CF6', WEEKLY_LIMITS),
    ('biweekly', 'Biweekly', 'See who likes you, reveal contacts', 15000, 14, 2, '#EC4899', BIWEEKLY_LIMITS),
    ('monthly', 'Monthly', 'Unlimited swipes, priority in the deck', 30000, 30, 3, '#F59E0B', MONTHLY_LIMITS),
    ('five_month', 'Five Months', 'Best value — go all in', 50000, 150, 4, '#10B981', FIVE_MONTH_LIMITS),
]

APP_IDS = ['linkup', 'abanoonya']


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_subscription_plans` (
                `id`            VARCHAR(36)   NOT NULL,
                `app_id`        VARCHAR(20)   NOT NULL,
                `code`          VARCHAR(40)   NOT NULL,
                `name`          VARCHAR(80)   NOT NULL,
                `tagline`       VARCHAR(160)  DEFAULT NULL,
                `price_ugx`     DECIMAL(14,2) NOT NULL,
                `duration_days` INT           NOT NULL DEFAULT 0,
                `sort_order`    SMALLINT      NOT NULL DEFAULT 0,
                `active`        TINYINT(1)    NOT NULL DEFAULT 1,
                `badge_color`   VARCHAR(20)   DEFAULT NULL,
                `limits`        JSON          NOT NULL,
                `created_at`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                              ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_plan_app_code` (`app_id`, `code`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_subscriptions` (
                `id`              VARCHAR(36)   NOT NULL,
                `account_id`      VARCHAR(36)   NOT NULL,
                `plan_id`         VARCHAR(36)   NOT NULL,
                `status`          VARCHAR(20)   NOT NULL DEFAULT 'pending',
                `starts_at`       DATETIME      DEFAULT NULL,
                `expires_at`      DATETIME      DEFAULT NULL,
                `amount_paid_ugx` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
                `tx_ref`          VARCHAR(100)  NOT NULL,
                `flw_tx_id`       VARCHAR(100)  DEFAULT NULL,
                `extra_data`      JSON          DEFAULT NULL,
                `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_sub_tx_ref` (`tx_ref`),
                KEY `idx_sub_account` (`account_id`),
                KEY `idx_sub_status` (`status`),
                CONSTRAINT `fk_sub_account` FOREIGN KEY (`account_id`)
                    REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE,
                CONSTRAINT `fk_sub_plan` FOREIGN KEY (`plan_id`)
                    REFERENCES `lu_subscription_plans`(`id`) ON DELETE RESTRICT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cur.execute("""
            ALTER TABLE `lu_accounts`
                ADD COLUMN `subscription_plan_id` VARCHAR(36) DEFAULT NULL AFTER `is_premium`,
                ADD COLUMN `subscription_expires_at` DATETIME DEFAULT NULL AFTER `subscription_plan_id`
        """)

        for app_id in APP_IDS:
            for code, name, tagline, price, duration, sort_order, badge, limits in PLAN_ROWS:
                cur.execute(
                    "INSERT IGNORE INTO `lu_subscription_plans` "
                    "(`id`, `app_id`, `code`, `name`, `tagline`, `price_ugx`, `duration_days`, "
                    "`sort_order`, `badge_color`, `limits`) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (str(uuid.uuid4()), app_id, code, name, tagline, price, duration,
                     sort_order, badge, json.dumps(limits))
                )
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE `lu_accounts` DROP COLUMN `subscription_expires_at`")
        cur.execute("ALTER TABLE `lu_accounts` DROP COLUMN `subscription_plan_id`")
        cur.execute("DROP TABLE IF EXISTS `lu_subscriptions`")
        cur.execute("DROP TABLE IF EXISTS `lu_subscription_plans`")
    conn.commit()
