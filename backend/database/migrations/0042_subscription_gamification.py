"""
Migration 0042: gamification support for the subscription system.

lu_accounts gets:
  - streak_days / streak_updated_at — real consecutive-day activity tracking
    (touched on genuine engagement, not just app-open), backing the swipe
    bonus at 3-day/7-day streaks.
  - first_match_bonus_available — a one-shot flag set true the moment an
    account's first-ever match happens, consumed as a bonus standout on next
    use. Simple boolean rather than a grants table since it's a single,
    non-repeating milestone.

lu_subscription_plans gets optional discount fields so admin can run a
time-boxed promo on a plan's price without a code change or new table.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE `lu_accounts`
                ADD COLUMN `streak_days` INT NOT NULL DEFAULT 0 AFTER `subscription_expires_at`,
                ADD COLUMN `streak_updated_at` DATETIME DEFAULT NULL AFTER `streak_days`,
                ADD COLUMN `first_match_bonus_available` TINYINT(1) NOT NULL DEFAULT 0
                    AFTER `streak_updated_at`
        """)
        cur.execute("""
            ALTER TABLE `lu_subscription_plans`
                ADD COLUMN `discount_price_ugx` DECIMAL(14,2) DEFAULT NULL AFTER `price_ugx`,
                ADD COLUMN `discount_ends_at` DATETIME DEFAULT NULL AFTER `discount_price_ugx`
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE `lu_subscription_plans`
                DROP COLUMN `discount_ends_at`,
                DROP COLUMN `discount_price_ugx`
        """)
        cur.execute("""
            ALTER TABLE `lu_accounts`
                DROP COLUMN `first_match_bonus_available`,
                DROP COLUMN `streak_updated_at`,
                DROP COLUMN `streak_days`
        """)
    conn.commit()
