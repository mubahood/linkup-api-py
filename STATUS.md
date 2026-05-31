# LinkUp API — Status

**Last updated**: 2026-05-31
**Branch**: `T-API-004-delete-ride-backend`
**Audit result**: 161/161 PASS — idempotent (verified on 2 consecutive runs)

---

## What Has Been Done

### Architecture

- Restructured to `backend/domains/<domain>/` architecture (T-API-001 ✅)
- All ride/trip/negotiation/payout code deleted (T-API-004..008 ✅)
- NegoRide → LinkUp rebrand complete (T-ID-001 ✅)
- Flask 3.0, SQLAlchemy, Flask-JWT-Extended, Flask-SocketIO (eventlet)
- Cloudflare R2 storage client with local fallback (T-API-012 ✅)
- Interest Graph scoring engine — weighted Jaccard across 8 dimensions (no pgvector needed yet)

### v1 Domain APIs — all tested in audit

| Domain | Key Endpoints |
| --- | --- |
| **Identity** | register, otp/*, login, me GET/PUT, logout, refresh, device, password |
| **Profile** | me CRUD, @handle, compatibility/:id, photo (R2), education/experience/certifications CRUD, dating GET/PUT (discoverability + age), completion |
| **Interests** | taxonomy, search, me GET/POST, remove/:id, suggestions, signal (behavioral) |
| **Links** | list, request/accept/decline/remove, requests, suggestions (Interest Graph scored) |
| **Hubs** | list/create/:id GET/PUT, join/leave, members, posts GET/POST/DELETE, post like/unlike, post likes list |
| **Jobs** | list, mine, saved, applications (mine), post/:id GET/PUT/close, apply, save, applicants |
| **Events** | list, mine, going, create/:id GET/PUT/DELETE, attendees (status filter), rsvp |
| **Chat** | threads list/create/:id, messages GET/POST, message react/reactions, read |
| **Sparks** | deck (Interest Graph + safety + age/gender/discoverability filters), action, matches, matches/:id |
| **Notifications** | list, unread-count, :id/read, read-all |
| **Safety** | blocks list/create/:id/delete, report |
| **Search** | people (bio/headline, blocks filtered), hubs (description), jobs (description) |
| **Reference** | locations, institutions, orgs (all public) |

### Interest Graph Scoring (`backend/shared/scoring/interest_graph.py`)

Weighted Jaccard similarity across all 8 dimensions — runs on MySQL, no pgvector needed.

**Applied everywhere:**

- **Sparks deck** — ranked by dating weights (relationship_intent × 4, causes_values × 2.5, lifestyle × 2.5, …)
- **Links suggestions** — ranked by professional weights (professional_domain × 3, education × 2.5, …)
- **Profile compatibility** — `GET /v1/profile/compatibility/:id?mode=professional|dating` — full dimension breakdown with shared tag IDs (explainability)

### Sparks Deck Quality

Deck filters applied (all in one pass):

1. **Already acted on** — excluded
2. **Blocked (bidirectional)** — excluded
3. **Heavily reported (≥3 reports)** — excluded
4. **Discoverability** — `paused` and `incognito` profiles excluded
5. **Age preference** — actor's age_min/max vs candidate's birth_year, AND candidate's preferences vs actor's age
6. **Gender preference** — soft filter applied when both sides have data
7. **Interest Graph ranking** — remaining candidates scored and sorted (dating weights)

### Social Features

**Hub post likes** (`lu_hub_post_likes` table):

- `POST /v1/hubs/:id/posts/:id/like` — toggle (like / unlike)
- `GET /v1/hubs/:id/posts/:id/likes` — list with account details
- `like_count` on `HubPost` maintained in sync
- Notification fired to post author on like (not on self-like)

**Message reactions** (`lu_message_reactions` table):

- `POST /v1/threads/:id/messages/:id/react` — toggle emoji reaction
- `GET /v1/threads/:id/messages/:id/reactions` — grouped by emoji with count + top reactors
- UNIQUE constraint: one emoji per user per message
- Supports any emoji (up to 10 chars)

### Behavioral Interest Signals

`POST /v1/interests/signal`:

- Mobile calls this when user engages (job view, hub visit, profile click, search)
- Reinforces existing interest weight (`+strength`, capped at 1.0)
- Creates new implicit interest (source=`behavioral`) if tag not yet in profile
- Pinned interests are never modified by signals
- Increments tag popularity counter

### Cloudflare R2 Storage (T-API-012)

`backend/shared/storage/r2.py`:

- Same interface as `local.py` (`save_upload`, `get_url`)
- Reads `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_BASE_URL` from environment
- Falls back to local `backend/uploads/` transparently in dev (credentials absent)
- Profile photo upload now uses R2 client
- `.env.example` updated with all R2 variables

### Account Settings

- `PUT /v1/auth/me` — display_name, email (uniqueness check), modes_enabled (at-least-one guard)
- `POST /v1/auth/password` — current-password verified, minimum 8 chars

### Notifications

- In-app notifications created on: message send, link request/accept, spark match, post like
- OneSignal push in background thread (non-blocking) if device registered
- `GET /v1/notifications/unread-count` — lightweight badge count
- `POST /v1/notifications/:id/read` — single-notification read
- `POST /v1/notifications/read-all` — bulk clear

### Seed Data (20 members, idiomatic Ugandan data)

- 20 accounts (samuel-ocen is admin)
- 43 interest tags across 8 dimensions
- 10 dating profiles with birth_year, gender, looking_for_gender, discoverability
- 5 hubs, 10 jobs, 3 events, threads, links, sparks, hub post likes

### Legacy Backward Compat (`/api/*`)

- Auth, profile, wallet, chat, webhooks, admin, calls, ratings, Flutterwave routes preserved
- v1 tokens work on legacy admin via `_AccountWrapper`

---

## What Is Remaining

### Phase 1 — Infrastructure

| Task | Status | Notes |
| --- | --- | --- |
| **T-API-012 R2** | Code done ✅ | Needs `R2_*` env vars in `.env` for production |
| **T-DEC-003 PostgreSQL** | Not started | ~2 week migration; unblocks pgvector + embeddings |
| **T-DEC-007 Celery + Redis** | Not started | Needed for ML training jobs, bulk push fanout |

### Interest Graph — Phase 2

- **Embeddings** — requires pgvector (PostgreSQL) for semantic similarity beyond explicit tags
- **Behavioral weight decay** — weights should decay over time if not reinforced (currently static)
- **Training data export** — need Celery job to export engagement events for ML training

### Sparks Deck Gaps

- Distance-based filtering (requires live GPS data from mobile)
- "Have we met?" outcome signal (post-match engagement feedback for ML)
- Deck refresh strategy (when all candidates exhausted, allow re-sees of `pass` actions)

### Missing Platform Endpoints

- `DELETE /v1/profile/me/dating` — remove dating profile (pause vs permanent delete)
- `GET /v1/hubs/:id/posts/:id/comments` + `POST` — hub post comments
- `DELETE /v1/threads/:id/messages/:id` — message delete/unsend
- `GET /v1/links/:id` — link detail
- `PUT /v1/hubs/:id/posts/:id` — edit a post
- KYC level advancement (currently hardcoded at 1)
- Admin console rebuild (T-API-036)

### Phase 2/3

- Mentorship, referrals, certificate verification
- Dating safety toolkit (share-date, photo verify, panic)
- Wallet + MoMo integration (Flutterwave service exists)
- Hub types: institution-linked alumni, org-linked communities

---

## How to Run

```bash
# Development setup
source venv/bin/activate
python -m backend.seed      # seed all lu_* tables idempotently
python run.py               # start on :5001

# Run migration 0010 (if fresh DB)
python -c "
from backend.app import create_app; app = create_app()
with app.app_context():
    from backend.models import db; import importlib.util
    spec = importlib.util.spec_from_file_location('m', 'backend/database/migrations/0010_hub_post_likes_and_message_reactions.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    conn = db.engine.raw_connection(); m.up(conn); conn.close(); print('Done')
"

# Full audit (161 tests, ~2 min)
python audit.py
```

**Dev credentials**: phone `+256700000001`, OTP `123456`, password `linkup2026`
**Admin**: samuel-ocen (is_admin=1)

---

## Architecture Reference

All canonical docs: `/Users/mac/Desktop/github/linkup-mobo/`

- `ABOUT.md` — product vision, Interest Graph concept
- `ARCHITECTURE.md` — tech stack, ML pipeline, infra
- `CORE_DATA_MODEL.md` — all entities + matching engine spec
- `MIGRATION_PLAN.md` — full task backlog
- `DESIGN_GUIDELINES.md` — design system v1.0.0

## Forbidden Strings (build gate)

`truckeroo truck rideshare negoride ride trip driver negotiation vehicle boda ambulance cargo delivery pickup dropoff fare passenger payout`
