---
description: Brief on where LinkUp/Abanoonya Pro actually runs in production
---

Tell the user, in your own words, where this app actually runs in
production — using the facts below, which were verified directly against
the live system on 2026-08-27 (DNS resolution, live `/v1/health`, direct
SSH, `migrate.py status` on the real database). Do not just restate this
file verbatim — summarize it naturally, and offer to go deeper (read
`DEPLOYMENT.md` or `.server-credentials`) if the user wants more.

## The facts

- **Production domain:** `abanoonyapro.online` resolves to `162.0.236.86` —
  a Namecheap-registered IP, on a shared VPS referred to internally as the
  "U-LITS box" (hostname `server1.u-lits.com`, AlmaLinux 9.7).
- **SSH access:** `ssh jangu-vps` (alias already configured in `~/.ssh/config`
  on this Mac) — root, key-based.
- **This app is one of five** unrelated production apps sharing that one VPS
  under a single root user (LinkUp/Abanoonya, Jangu, Truckfully, NegoRide,
  etag-web) — each its own directory, its own systemd unit, its own port.
  Server-level changes (nginx.conf itself, PHP, MySQL server config) can
  affect all of them; scope changes to this app's own vhost/service/db only.
- **App root:** `/var/www/abanoonya.u-lits.com/app` — **not a git
  repository**. Deployment is by copying files directly (rsync/scp), never
  `git pull`. There is no on-server git remote.
- **Runtime:** gunicorn + eventlet, 1 worker, bound to `127.0.0.1:5006`,
  managed by systemd unit `abanoonya.service`. Python 3.9.25 in
  `/var/www/abanoonya.u-lits.com/app/.venv` — older than local dev.
- **Nginx:** `/etc/nginx/conf.d/abanoonyapro.online.conf` (AlmaLinux's
  `conf.d` layout, not Debian's `sites-available`), TLS via Let's Encrypt.
- **Full deployment procedure, architecture diagram, and known gaps:**
  [`DEPLOYMENT.md`](../../DEPLOYMENT.md) at the repo root.
- **Actual secrets** (SSH key path, DB password, admin console logins, app
  secrets): [`.server-credentials`](../../.server-credentials) at the repo
  root — gitignored, local-only, never commit it or paste its contents
  anywhere outside this machine.

## Why this command exists

An earlier version of `DEPLOYMENT.md`/`.server-credentials` confidently
described a completely different server (a Hetzner Cloud VPS) that turned
out to have nothing to do with this domain — that was written by trusting a
stale credentials file without checking DNS first. Don't repeat that: if
anything here ever looks inconsistent with what you observe live (a health
check, an SSH session, a `migrate.py status`), the live system is the
source of truth, not this file. Update `DEPLOYMENT.md` and
`.server-credentials` if you find a discrepancy, the same way this file was
corrected.
