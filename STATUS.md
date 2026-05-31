# LinkUp API — Phase 0 Status

**Last updated**: 2026-05-31
**Branch**: `T-API-004-delete-ride-backend`
**Audit result**: 106/106 PASS — idempotent (verified on 2 consecutive runs)

---

## What Has Been Done

### Architecture

- Backend restructured to `backend/domains/<domain>/` architecture (T-API-001 ✅)
- All ride/trip/negotiation/payout backend code deleted (T-API-004..008 ✅)
- NegoRide → LinkUp rebrand complete (T-ID-001 ✅)
- Flask 3.0, SQLAlchemy, Flask-JWT-Extended, Flask-SocketIO (eventlet), Flutterwave, OneSignal

### v1 Domain APIs (`/v1/*`) — all tested in audit

| Domain | Endpoints | Notes |
| --- | --- | --- |
| **Identity** | register, otp/request, otp/verify, login, me, logout, refresh, device | `device` = OneSignal push registration |
| **Profile** | me GET/PUT/DELETE, @handle, photo, education CRUD, experience CRUD, certifications CRUD, dating GET/PUT, completion | Soft-delete reactivates on re-registration |
| **Interests** | taxonomy, search, me GET/POST, remove/:id, suggestions | 8-dimension taxonomy, 43 seed tags |
| **Links** | list, request, requests list, :id/accept, :id/decline, :id/remove, suggestions | Notifications on request + accept |
| **Hubs** | list, create, :id GET/PUT, join, leave, members, posts GET/POST, posts/:id DELETE | Join/leave/rejoin/double-join all tested |
| **Jobs** | list, mine, post, :id GET, apply, save | Referral flag, seniority, currency |
| **Events** | list, create, :id GET, :id/rsvp (going/maybe/not_going) | |
| **Chat** | threads list/create, :id GET, messages GET/POST, read | Notifications on message send |
| **Sparks** | deck, action (spark_up/pass/standout/undo), matches, matches/:id | Match auto-creates spark thread |
| **Notifications** | list, :id/read, read-all | In-app + OneSignal push (non-blocking) |
| **Safety** | blocks list/create/:id/delete, report | |
| **Search** | people, hubs, jobs | Full-text search |
| **Reference** | locations, institutions, orgs | Public — no auth required |

### Cross-Domain Wiring

- **Message sent** → notification to all other thread participants
- **Link requested** → notification to target
- **Link accepted** → notification to requester
- **Spark match** → notification to both accounts + auto-creates dating thread
- **All notifications** → fire OneSignal push in background thread if device registered

### Push Notifications

- `POST /v1/auth/device` — mobile client registers OneSignal player_id + platform
- `AccountDevice` model stores player_ids per account
- Non-blocking: push fires in daemon thread so API response never blocks

### Sparks (dating mode)

- Deck: returns accounts with dating profiles + sparks mode enabled, excluding already-acted-on
- Match: mutual spark_up/standout → auto-creates `type='spark'` `mode='dating'` thread
- Seed: 10 dating profiles with bios, intents, lifestyle data
- Seed mutual match (Samuel ↔ Aisha) + pre-spark (Henry → Samuel) for audit testing

### Account Lifecycle

- Soft-delete: `DELETE /v1/profile/me` → `deleted_at + account_status='closed'`
- Re-register: `otp_verify` reactivates closed account (avoids phone UNIQUE constraint)

### Seed Data (20 members, idiomatic Ugandan data)

- 20 accounts (samuel-ocen is `is_admin=1` for legacy admin tests)
- 43 interest tags across 8 dimensions
- 10 dating profiles with realistic bios
- 5 hubs with members + posts
- 10 jobs, 3 events, 2 threads, 10 links, spark data

### Legacy Backward Compat (`/api/*`)

- Auth, profile, wallet, chat, webhooks, admin, calls, ratings, Flutterwave routes preserved
- v1 JWT tokens work on `/api/admin/*` via `_AccountWrapper` (is_admin=1 → 'Admin' user_type)

---

## What Is Remaining

### Phase 1 — Next Priority

| Task ID | Description | Blocker |
| --- | --- | --- |
| **T-API-012** | File uploads → Cloudflare R2 (currently stored locally at `backend/uploads/`) | Need R2 credentials |
| **T-DEC-003** | DB migration MySQL → PostgreSQL | Required for pgvector/Interest Graph |
| **T-DEC-007** | Celery + Redis async queue | Required for ML jobs, bulk notifications |

### Interest Graph (Phase 2)

- Schema in place: `lu_interest_profiles` + `lu_interest_tags`
- 8-dimension taxonomy seeded (professional_domain, geography_mobility, lifestyle, etc.)
- Matching algorithm (cosine similarity across dimensions) **not yet implemented**
- Sparks deck currently sorts by `created_at desc` — should score by Interest Graph

### Sparks deck improvements

- Currently returns profiles ordered by creation date
- Should score by Interest Graph overlap (8 dimensions) × age preference match
- Blocked profiles + reports not yet applied to deck filter

### Platform (Phase 3)

- `POST /v1/profile/me/photo` — endpoint exists, needs actual storage (currently local)
- `GET /v1/profile/@handle` — public view works; need to respect `visibility_mode='private'` on dating profile
- Mentorship, referrals, certificate verification features
- Admin console rebuild (T-API-036)
- KYC level advancement (currently hardcoded at 1)

### Known Minor Items

- Profile completion caps at 90% without avatar — correct behavior; avatar upload works but needs storage backend
- `GET /v1/sparks/deck` returns fewer cards on repeated audit runs (acted-on accounts excluded — correct)
- `GET /v1/interests/search` returns exact tag matches only — fuzzy search would improve UX
- Job/event counts grow across audit runs (test data accumulates — acceptable for dev)

---

## How to Run

```bash
# Clean start
source venv/bin/activate
python -m backend.seed        # seeds all lu_* tables idempotently
python run.py                 # starts on :5001

# Full audit (106 tests, ~60s)
source venv/bin/activate && python audit.py
```

**Test credentials**: phone `+256700000001`, OTP `123456` (dev fixed OTP — always valid)
**Admin**: samuel-ocen (`is_admin=1`) — works on both `/v1/` and legacy `/api/admin/` routes

---

## Architecture Reference

Canonical docs in `/Users/mac/Desktop/github/linkup-mobo/`:

- `ABOUT.md` — product vision, Uganda-first, Interest Graph concept
- `ARCHITECTURE.md` — full tech stack, ML pipeline, infra
- `CORE_DATA_MODEL.md` — all entities (Account, Profile, Interest, Link, Spark, Hub, Job…)
- `MIGRATION_PLAN.md` — task backlog with IDs (T-MOB-###, T-API-###, T-DEC-###)
- `DESIGN_GUIDELINES.md` — canonical design system v1.0.0

## Forbidden Strings (build gate)

`truckeroo truck rideshare negoride ride trip driver negotiation vehicle boda ambulance cargo delivery pickup dropoff fare passenger payout`
