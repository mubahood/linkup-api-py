"""
One-time backfill: grant every existing account (across LinkUp, Abanoonya
Pro, and Uganda Dating App) the September 2026 launch promo — top plan for
their app, free, for a month. New signups get this automatically via the
hook in identity/service.py up through the same cutoff
(subscriptions/service.py's LAUNCH_PROMO_CUTOFF); this script is only for
accounts that already existed before that hook went in.

Idempotent — grant_launch_promo() checks for an existing grant per account
(tx_ref 'PROMO-LAUNCH-<account_id>') before creating one, so re-running this
is safe and just skips accounts already granted.

Run:  python backfill_launch_promo.py
"""
def run():
    from backend.domains.identity.models import Account
    from backend.domains.subscriptions.service import grant_launch_promo

    accounts = Account.query.filter(
        Account.deleted_at.is_(None),
        Account.account_status != 'closed',
    ).all()

    granted, skipped, no_plan = 0, 0, 0
    for account in accounts:
        result = grant_launch_promo(account)
        if result is not None:
            granted += 1
        else:
            # Either already granted (idempotent skip) or no plan found for
            # this app_id — tell those apart by checking whether it now has
            # an active subscription (the earlier grant), rather than a
            # second, more fragile query.
            if account.subscription_plan_id and account.subscription_expires_at:
                skipped += 1
            else:
                no_plan += 1

    print(f'Accounts considered: {len(accounts)}')
    print(f'  Granted this run:  {granted}')
    print(f'  Already granted:   {skipped}')
    print(f'  No plan for app:   {no_plan}  (should be 0 — investigate if not)')


if __name__ == '__main__':
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        run()
