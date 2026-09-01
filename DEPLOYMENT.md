# Deployment — LinkUp / Abanoonya Pro Backend

This backend (`linkup-api-py`) is one Flask app serving **two branded mobile
apps** — LinkUp and Abanoonya Pro — from a single codebase, database, and
production process. There is no separate "Abanoonya backend": it's the same
deployment described below, with requests scoped per-app via a header.

## Read this first (for an agent working on this repo)

- **Real secrets live in `.server-credentials` at repo root — gitignored,
  never commit it.** This doc explains *what* exists and *how* deployment
  works; it deliberately does not repeat passwords/tokens/keys so there's one
  source of truth.
- **Don't trust a credentials/deployment doc at face value — verify against
  the live system first** (`dig`, `curl .../v1/health`, an actual SSH
  connection). This exact file was wrong before because nobody did that.
- **This VPS is shared with 4+ other unrelated production apps** (Truckfully,
  Jangu, NegoRide, an "etag" project — all root-owned gunicorn processes on
  one box). Any server-level change (nginx.conf itself, PHP, MySQL server
  settings) can affect all of them — scope changes to this app's own
  vhost/service/database only.
- **There is no git repository on the production server.** Deployment is by
  copying files directly (rsync/scp), not `git pull`. Don't assume a
  git-based redeploy flow works here without checking first.
- **Never blind-run `migrate.py migrate` against production** without
  `migrate.py status` first.
- **The built admin frontend (`frontend/build/`) is gitignored and deployed
  by manual upload**, same as the backend — copied in, not built on the box.
- **`.env.production` in this repo is a stale template from an earlier
  project (NegoRide rideshare, `negoride` DB, `mruodel.com` domain)** — not
  representative of real production config. The real `.env` exists only on
  the server, at `/var/www/abanoonya.u-lits.com/app/.env`, chmod 600.

## Architecture

```
Browser / Mobile App
        │  HTTPS (443)
        ▼
   Nginx  (conf.d/abanoonyapro.online.conf, Let's Encrypt SSL, WS upgrade)
        │  reverse proxy → 127.0.0.1:5006
        ▼
   Gunicorn + eventlet worker  (systemd: abanoonya.service)
        │  wsgi.py → backend.app:application
        ▼
   Flask app (backend/app.py)  ──►  MySQL  (db: linkup, on this same box)
```

One Flask process serves both brands. A request's `X-App` header is resolved
to `app_id` ('linkup' | 'abanoonya') by
[`backend/shared/app_brand.py`](backend/shared/app_brand.py) — unrecognized or
missing header defaults to `'linkup'`. That `app_id` is stamped on
`lu_accounts.app_id` at signup and on `lu_app_versions.app_id` for
per-app force-update config; the admin console filters by it via `?app_id=`.
There's no branch/deploy/database split between the two apps — it's one
running system, segmented by data, not by infrastructure.

## Server

A shared Linux VPS referred to internally as the "U-LITS box" — AlmaLinux
9.7, hostname `server1.u-lits.com`. SSH access, DB credentials, and full
detail are in `.server-credentials`; the short version:

```bash
ssh jangu-vps   # alias already in ~/.ssh/config on the dev Mac
```

This one server hosts **five separate production apps** as sibling
directories under `/var/www/`, each its own systemd-managed gunicorn process
on its own port:

| App | Path | Port |
|---|---|---|
| **This app (LinkUp/Abanoonya)** | `/var/www/abanoonya.u-lits.com/app` | 5006 |
| Jangu | `/var/www/jangu.u-lits.com/app` | 5005 |
| Truckfully | `/var/www/truckfully.com/app` | 5002 |
| NegoRide | `/var/www/negoride.ugnews24.info/app` | 5004 |
| etag-web | `/var/www/etag-web-py` | 5001 |

## Domain & TLS

- `abanoonyapro.online` + `www.abanoonyapro.online` → `162.0.236.86`.
- Nginx vhost: `/etc/nginx/conf.d/abanoonyapro.online.conf` (AlmaLinux's
  `conf.d` layout — not Debian/Ubuntu's `sites-available`). Proxies `/` and
  `/socket.io/` separately to `127.0.0.1:5006`, the latter with WS upgrade
  headers and a long read timeout for chat/call signaling.
- TLS via Let's Encrypt, `/etc/letsencrypt/live/abanoonyapro.online/`.

## Application

| What | Where |
|---|---|
| App root | `/var/www/abanoonya.u-lits.com/app` — **not a git repo**, files copied in directly |
| Python venv | `/var/www/abanoonya.u-lits.com/app/.venv` (Python **3.9.25** — older than local dev; check compatibility before relying on newer-Python-only syntax) |
| Env config | `/var/www/abanoonya.u-lits.com/app/.env` (chmod 600) |
| App server | `gunicorn --worker-class eventlet -w 1 -b 127.0.0.1:5006 wsgi:application` |
| Process manager | systemd unit `abanoonya.service` (active) — a stale, unrelated `linkup.service` unit also exists on this box (inactive/not-found) and should be ignored |
| App logs | `/var/log/abanoonya-access.log`, `/var/log/abanoonya-error.log` |
| Database | MySQL, db `linkup`, on the same box |

Service control:
```bash
sudo systemctl status abanoonya
sudo systemctl restart abanoonya
sudo systemctl stop abanoonya
```

## Redeploy (backend)

There's no `git pull` on the server — sync files directly, then migrate and
restart:

```bash
rsync -avz --exclude='.git' --exclude='.venv' --exclude='node_modules' \
      --exclude='uploads' --exclude='__pycache__' --exclude='.env' \
      ./ jangu-vps:/var/www/abanoonya.u-lits.com/app/

ssh jangu-vps
cd /var/www/abanoonya.u-lits.com/app
./.venv/bin/pip install -r requirements.txt   # if deps changed
./.venv/bin/python migrate.py status           # check before migrating
./.venv/bin/python migrate.py migrate          # only if new migrations pending
sudo systemctl restart abanoonya
```

As of 2026-08-27, production is at migration `0037` (37/37 ran, 0 pending) —
in sync with local up through `0037_panic_alerts`. Migration `0038` (a new
listings/claim-import feature — see below) exists locally but has not been
copied to the server.

Sanity-check after restart: `GET https://abanoonyapro.online/v1/health`
should return `{"data": {"database": "ok", ...}}`.

## Redeploy (admin console frontend)

Also not part of the sync above — build locally, upload separately:

```bash
cd frontend && npm run build
# then upload build/ to /var/www/abanoonya.u-lits.com/app/frontend/build
```

Flask serves it directly as static files from that path.

## Credentials — what exists and where

Category pointers only — actual values are in `.server-credentials` (repo
root, gitignored):

- SSH: root key for the shared VPS (`jangu-vps` alias).
- MySQL: app DB user/password used in the production `.env`.
- App secrets: `SECRET_KEY` / `JWT_SECRET_KEY` in the production `.env`.
- Admin console logins: two seeded admin accounts (`lu_accounts.is_admin=1`)
  — one uses a weak placeholder password (`111111`), flagged for rotation
  before a real public launch.

## Known gaps

- Payment keys (`FLW_SECRET_KEY` / `FLW_PUBLIC_KEY` / `FLW_ENCRYPTION_KEY` /
  `FLW_SECRET_HASH`), mail credentials, and `ONESIGNAL_REST_API_KEY` — check
  `.server-credentials` for current fill status; historically unfilled.
- Admin 2's password (`111111`) should be rotated before real users see the
  console.
- **The listings/claim-import feature (migration `0038`, `backend/domains/listings/`,
  branch `feature/listings-discovery-phase1-2`) is intentionally not deployed.**
  Its own plan doc (`PROFILE_CLAIM_IMPORTER_PLAN.md`) lists legal and
  app-store-policy review as explicit, unchecked preconditions before any
  source adapter goes live — this isn't an oversight, don't rsync it over
  without confirming those gates have been cleared.
