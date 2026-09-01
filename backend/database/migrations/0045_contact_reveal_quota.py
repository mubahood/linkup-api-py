"""
Migration 0045: add contacts_per_day to every existing subscription plan's
limits JSON.

can_reveal_contact (migration 0041) was always a pure boolean — once true,
reveal was unlimited for the life of the subscription, with no per-day cap
and no audit trail (match_contact didn't emit an event). This adds the
numeric ceiling on top of that boolean gate: can_reveal_contact still
decides whether the tier gets this feature at all, contacts_per_day decides
how many different matches' contacts can be revealed per day. -1 = unlimited
(five_month only, matching how every other -1 limit in this table is used).

Values below are starting defaults, not fixed — like every other number in
`limits`, they're editable from the admin console (AccountFormModal /
SubscriptionsPage) with no deploy required.
"""
import json

CONTACT_LIMITS = {
    'free': 0,
    'weekly': 0,        # can_reveal_contact is already false for this tier
    'biweekly': 3,
    'monthly': 10,
    'five_month': -1,
}


def up(conn):
    with conn.cursor() as cur:
        for code, limit in CONTACT_LIMITS.items():
            cur.execute(
                "UPDATE `lu_subscription_plans` "
                "SET `limits` = JSON_SET(`limits`, '$.contacts_per_day', %s) "
                "WHERE `code` = %s",
                (limit, code)
            )
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE `lu_subscription_plans` "
            "SET `limits` = JSON_REMOVE(`limits`, '$.contacts_per_day')"
        )
    conn.commit()
