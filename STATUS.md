# LinkUp API — Phase 0/1 Status

**Last updated**: 2026-05-31
**Branch**: `T-API-004-delete-ride-backend`
**Audit result**: 132/132 PASS — idempotent (verified on 2 consecutive runs)

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
| **Identity** | register, otp/request, otp/verify, login, me GET/PUT, logout, refresh, device, password | Full account settings including modes and password |
| **Profile** | me GET/PUT/DELETE, @handle, compatibility/:id, photo, education CRUD, experience CRUD, certifications CRUD, dating GET/PUT, completion | Interest Graph breakdown via compatibility endpoint |
| **Interests** | taxonomy, search, me GET/POST, remove/:id, suggestions | 8-dimension taxonomy, 43 seed tags |
| **Links** | list, request, requests, :id/accept, :id/decline, :id/remove, suggestions | Suggestions ranked by Interest Graph; blocks filtered |
| **Hubs** | list, create, :id GET/PUT, join, leave, members, posts GET/POST, posts/:id DELETE | Join/leave/rejoin/double-join all tested |
| **Jobs** | list, mine, post, :id GET/PUT/close, apply, save, applicants | Poster-only: close and applicants list |
| **Events** | list, create, :id GET/PUT/DELETE, :id/rsvp, :id/attendees | Host-only: update, cancel, attendees with status filter |
| **Chat** | threads list/create, :id GET, messages GET/POST, read | Notifications on message send |
| **Sparks** | deck (scored), action, matches, matches/:id | Deck ranked by Interest Graph + blocks filtered |
| **Notifications** | list, :id/read, read-all | In-app + OneSignal push (non-blocking background thread) |
| **Safety** | blocks list/create/:id/delete, report | Blocks applied to deck/search/suggestions |
| **Search** | people, hubs, jobs | Blocks filtered; bio/headline/description included |
| **Reference** | locations, institutions, orgs | Public — no auth required |

### Interest Graph Scoring Engine (`backend/shared/scoring/interest_graph.py`)

Implemented weighted Jaccard similarity across all 8 dimensions. No pgvector required — runs on existing MySQL `lu_interest_profiles` data.

**Dimension weight profiles:**

| Dimension | Professional weight | Dating weight |
| --- | --- | --- |
| relationship_intent | 0.0 (excluded) | 4.0 |
| professional_domain | 3.0 | 0.5 |
| education_affiliation | 2.5 | 1.0 |
| geography_mobility | 2.0 | 2.0 |
| causes_values | 1.5 | 2.5 |
| lifestyle | 0.5 | 2.5 |
| hobbies_passions | 1.0 | 2.0 |
| personality_working_style | 1.5 | 1.0 |

**Applied to:**

- **Sparks deck** — ranked by Interest Graph (dating weights), blocks excluded
- **Links suggestions** — ranked by Interest Graph (professional weights), blocks excluded
- **Profile compatibility** — `GET /v1/profile/compatibility/:id?mode=professional|dating` returns dimension-by-dimension breakdown (explainability feature from `CORE_DATA_MODEL.md §6.5`)

### Safety (Blocks applied everywhere)

- Blocks are bidirectional: if A blocks B, B also disappears from A's surfaces
- Applied to: Sparks deck, Links suggestions, People search
- Reports stored for admin review; don't yet affect scoring (Phase 2 item)

### Account Settings

- `PUT /v1/auth/me` — update `display_name`, `email`, `modes_enabled`; guards: email uniqueness, at least one mode must stay enabled
- `POST /v1/auth/password` — change password with current-password verification; guards: min 8 chars, correct current required

### Push Notifications

- `POST /v1/auth/device` — mobile client registers OneSignal player_id + platform
- Non-blocking: push fires in daemon thread so API response never blocks

### Sparks (dating mode)

- Deck: ranked by Interest Graph (dating weights), sparks-enabled only, blocks excluded
- Match: mutual spark_up/standout → auto-creates `type='spark'` `mode='dating'` thread
- Seed: 10 dating profiles with bios, intents, lifestyle data + pre-seeded test match

### Seed Data (20 members, idiomatic Ugandan data)

- 20 accounts (samuel-ocen is `is_admin=1` for legacy admin tests)
- 43 interest tags across 8 dimensions
- 10 dating profiles with realistic bios
- 5 hubs, 10 jobs, 3 events, 2 threads, 10 links, spark data

### Legacy Backward Compat (`/api/*`)

- Auth, profile, wallet, chat, webhooks, admin, calls, ratings, Flutterwave routes preserved
- v1 JWT tokens work on `/api/admin/*` via `_AccountWrapper` (is_admin=1 → 'Admin' user_type)

---

## What Is Remaining

### Phase 1 — Infrastructure (external services required)

| Task ID | Description | Blocker / Status |
| --- | --- | --- |
| **T-API-012** | File uploads → Cloudflare R2 | Needs R2 credentials |
| **T-DEC-003** | MySQL → PostgreSQL + Alembic | Required for pgvector; ~2 week migration |
| **T-DEC-007** | Celery + Redis async queue | Infrastructure setup needed |

### Interest Graph — Phase 2 improvements

- **Embedding-based ANN search** — currently Jaccard on explicit tags; Phase 2 adds `vector(384)` embeddings via pgvector for semantic similarity (requires T-DEC-003)
- **Behavioral learning** — currently weights are static; should decay with time + reinforce from behavior events (`CORE_DATA_MODEL.md §6.5`)
- **Reports factor into scoring** — heavily-reported profiles should be deprioritized in deck
- **Sparks deck age filtering** — `DatingProfile.age_min/max` vs `Account.dob` not yet enforced (no `dob` column on Account)

### Sparks deck filtering gaps

- `discoverability` field on DatingProfile not yet enforced (paused/incognito users should be hidden)
- Distance-based filtering not yet implemented (requires live location data)

### Missing platform endpoints

- `GET /v1/jobs/saved` — list saved jobs
- `GET /v1/profile/me/applications` — my job applications
- `GET /v1/events/mine` — events I created
- `GET /v1/events/going` — events I'm attending
- `POST /v1/hubs/:id/posts/:id/like` — like a post
- `POST /v1/threads/:id/messages/:id/react` — message reaction
- `GET /v1/notifications/unread-count` — lightweight badge count

### Phase 2/3 (Platform)

- KYC advancement (currently hardcoded at level 1)
- Mentorship, referrals, certificate verification
- Admin console rebuild (T-API-036)
- Dating safety toolkit endpoints (share-date, panic, photo verify)
- Wallet + MoMo integration (Flutterwave service exists)
- Hub types: alumni (institution-linked), org (employer-linked)

---

## How to Run

```bash
# Clean start
source venv/bin/activate
python -m backend.seed        # seeds all lu_* tables idempotently
python run.py                 # starts on :5001

# Full audit (132 tests, ~90s)
source venv/bin/activate && python audit.py
```

**Test credentials**: phone `+256700000001`, OTP `123456` (dev fixed OTP — always valid)
**Admin**: samuel-ocen (`is_admin=1`) — works on both `/v1/` and legacy `/api/admin/` routes
**Password**: `linkup2026` (all seed accounts)

---

## Architecture Reference

Canonical docs in `/Users/mac/Desktop/github/linkup-mobo/`:

- `ABOUT.md` — product vision, Uganda-first, Interest Graph concept
- `ARCHITECTURE.md` — full tech stack, ML pipeline, infra
- `CORE_DATA_MODEL.md` — all entities + matching engine spec (§6)
- `MIGRATION_PLAN.md` — full task backlog (T-MOB-###, T-API-###, T-DEC-###)
- `DESIGN_GUIDELINES.md` — canonical design system v1.0.0

## Forbidden Strings (build gate)

`truckeroo truck rideshare negoride ride trip driver negotiation vehicle boda ambulance cargo delivery pickup dropoff fare passenger payout`
