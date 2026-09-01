"""
Migration 0048: Uganda Dating App — third brand on the shared backend.

Seeds the per-app rows that `lu_app_versions` (0035) and
`lu_subscription_plans` (0041) already require for any app_id to function:
a force-update row per platform, and the same 5-tier pricing/limits catalog
used by Abanoonya Pro (same market, same currency — UGX). No schema changes;
both tables already carry `app_id` as a free-form VARCHAR(20)/VARCHAR(20)
column, so a new app_id just needs new rows, not a new column.
"""
import uuid
import json


APP_ID = 'uganda_dating'

# ios_url left NULL — not on the App Store yet (matches the 0035 pattern for
# both existing apps). android_url is a placeholder Play Store link — update
# once the app has a real listing.
APP_VERSION_ROWS = [
    ('android', 1, '1.0.0', 1, 'Initial release.',
     'https://play.google.com/store/apps/details?id=app.ugandadating.app', None),
    ('ios', 1, '1.0.0', 1, 'Initial release.', None, None),
]

# Same limits/pricing as Abanoonya Pro (migration 0041) — same market and
# currency, no reason to diverge at launch.
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


def up(conn):
    with conn.cursor() as cur:
        for platform, latest_build, latest_version_name, min_build, notes, android_url, ios_url in APP_VERSION_ROWS:
            cur.execute(
                "INSERT IGNORE INTO `lu_app_versions` "
                "(`id`, `app_id`, `platform`, `latest_build`, `latest_version_name`, "
                "`min_supported_build`, `update_notes`, `android_url`, `ios_url`) "
                "VALUES (UUID(), %s, %s, %s, %s, %s, %s, %s, %s)",
                (APP_ID, platform, latest_build, latest_version_name, min_build, notes, android_url, ios_url)
            )

        for code, name, tagline, price, duration, sort_order, badge, limits in PLAN_ROWS:
            cur.execute(
                "INSERT IGNORE INTO `lu_subscription_plans` "
                "(`id`, `app_id`, `code`, `name`, `tagline`, `price_ugx`, `duration_days`, "
                "`sort_order`, `badge_color`, `limits`) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), APP_ID, code, name, tagline, price, duration,
                 sort_order, badge, json.dumps(limits))
            )
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM `lu_subscription_plans` WHERE `app_id` = %s", (APP_ID,))
        cur.execute("DELETE FROM `lu_app_versions` WHERE `app_id` = %s", (APP_ID,))
    conn.commit()
