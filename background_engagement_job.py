"""
Scheduled entry point for the server-side re-engagement push job — see
backend/domains/notifications/engagement.py for the actual selection/content
logic. Intended to run once a day via a systemd timer (see
deploy/engagement-job.service + .timer at the repo root); safe to run more
often too, since run_engagement_job()'s per-account cooldown means an extra
run just finds nothing new to send.

Run:  python background_engagement_job.py [--limit N]
"""
import argparse


def run(limit=None):
    from backend.domains.notifications.engagement import run_engagement_job
    result = run_engagement_job(limit=limit)
    print(f"Eligible: {result['eligible']}")
    print(f"Sent:     {result['sent']}")
    print(f"Skipped (cooldown): {result['skipped_cooldown']}")
    print(f"Failed:   {result['failed']}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None,
                         help='Cap how many eligible accounts to process this run (testing).')
    args = parser.parse_args()

    from backend.app import create_app
    app = create_app()
    with app.app_context():
        run(limit=args.limit)
