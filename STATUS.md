# LinkUp API — Status

**Last updated**: 2026-05-31
**Branch**: `T-API-004-delete-ride-backend`
**Audit result**: 179/179 PASS — idempotent (verified on 2 consecutive runs)

---

## What Has Been Done

### Architecture

- `backend/domains/<domain>/` restructure (T-API-001 ✅)
- All ride/trip/negotiation/payout code deleted (T-API-004..008 ✅)
- NegoRide → LinkUp rebrand (T-ID-001 ✅)
- Cloudflare R2 storage with local fallback (T-API-012 ✅)
- Interest Graph weighted Jaccard scoring engine (no pgvector needed yet)
- Flask 3.0, SQLAlchemy, Flask-JWT-Extended, Flask-SocketIO (eventlet)

### DB Tables (lu_*)

| Table | Description |
| --- | --- |
| lu_accounts, lu_account_devices | Auth + push device tokens |
| lu_otp_requests, lu_refresh_tokens | OTP and token lifecycle |
| lu_professional_profiles, lu_dating_profiles | Dual-persona profiles |
| lu_education, lu_experience, lu_certifications | CV data |
| lu_interest_tags, lu_interest_profiles | 8-dimension Interest Graph |
| lu_links | Professional connections |
| lu_sparks, lu_matches | Dating actions + mutual matches |
| lu_hubs, lu_hub_memberships | Communities |
| lu_hub_posts, lu_hub_post_likes, lu_hub_post_comments | Social content |
| lu_threads, lu_thread_participants, lu_messages, lu_message_reactions | Chat |
| lu_jobs, lu_applications, lu_saved_jobs | Job listings |
| lu_events, lu_event_rsvps | Events |
| lu_notifications | In-app notifications |
| lu_blocks, lu_reports | Safety |
| lu_locations, lu_institutions, lu_orgs | Reference data |
| lu_verifications | KYC verification records |

### v1 Domain APIs — all tested in audit

| Domain | Key Endpoints |
| --- | --- |
| **Identity** | register, otp/*, login, me GET/PUT, logout, refresh, device, password |
| **Profile** | me CRUD, @handle, compatibility/:id, photo (R2), education/experience/certifications CRUD, dating GET/PUT/DELETE (soft+hard), completion |
| **Interests** | taxonomy, search, me GET/POST, remove/:id, suggestions, signal (behavioral), me?with_decay |
| **Links** | list, :id GET, request/accept/decline/remove, requests, suggestions (Interest Graph scored) |
| **Hubs** | list/create/:id GET/PUT, join/leave, members, posts GET/POST/PUT/DELETE, post likes, post comments CRUD |
| **Jobs** | list, mine, saved, applications, post/:id GET/PUT/close, apply, save, applicants |
| **Events** | list, mine, going, create/:id GET/PUT/DELETE, attendees, rsvp |
| **Chat** | threads list/create/:id, messages GET/POST/DELETE (24h window), reactions, read |
| **Sparks** | deck (scored + refresh), action, matches, matches/:id/unmatch, matches/:id/met |
| **Notifications** | list, unread-count, :id/read, read-all |
| **Safety** | blocks list/create/:id/delete, report |
| **Search** | people (bio/headline, blocks filtered), hubs (description), jobs (description) |
| **Reference** | locations, institutions, orgs (all public) |

### Interest Graph Scoring

- Weighted Jaccard across 8 dimensions — MySQL-native, no pgvector needed
- Professional weights: professional_domain ×3, education ×2.5, geography ×2, ...
- Dating weights: relationship_intent ×4, causes_values ×2.5, lifestyle ×2.5, ...
- Applied to: Sparks deck ranking, Links suggestions, profile compatibility breakdown
- Weight decay on read: `w × (1 - rate)^months` — explicit 0.01/mo, behavioral 0.02/mo

### Sparks Deck Quality (all filters in one pass)

1. Already acted-on (or only spark_up/standout if `?refresh=true`)
2. Blocked (bidirectional)
3. Heavily reported (≥3 reports)
4. Discoverability = paused or incognito
5. Age preference hard filter (both directions, if birth_year set)
6. Gender preference soft filter (if both sides have data)
7. Interest Graph ranking (dating weights)

### Social Features

**Hub post comments** (`lu_hub_post_comments`):

- POST/GET/PUT/DELETE on comments; replies via parent_id
- comment_count maintained; notification to post author
- Non-member guard; soft-delete shows `[Comment deleted]`

**Hub post likes** (`lu_hub_post_likes`):

- Toggle like/unlike; like_count maintained; notification to author

**Message reactions** (`lu_message_reactions`):

- Toggle emoji reactions; grouped summary with counts + top reactors

**Message delete/unsend**:

- Sender can delete within 24h; body replaced with `[Message deleted]`

### Match Management

- `POST /v1/sparks/matches/:id/unmatch` — soft unmatch, notifies other party
- `POST /v1/sparks/matches/:id/met` — ML outcome signal (met in real life)
- Match states: `active` | `unmatched` | `expired`

### Dating Profile

- `discoverability`: `discoverable` | `paused` | `incognito`
- `birth_year` → age derived on read
- `gender` + `looking_for_gender` for soft deck filtering
- `DELETE /v1/profile/me/dating` — soft pause OR `?permanent=true` for hard delete

### Notifications

- In-app + OneSignal push (non-blocking) on: message, link request/accept, match, post like, comment
- Badge count, single-read, bulk read-all
- Notification types: `message.sent`, `link.requested`, `link.accepted`, `spark.match`, `spark.unmatched`, `post.liked`, `post.commented`

### Behavioral Interest Signals

- `POST /v1/interests/signal` — mobile reinforces on job_view, hub_visit, profile_view, etc.
- Reinforces weight (+strength, cap 1.0), creates implicit if new
- `GET /v1/interests/me?with_decay=true` — shows effective_weight after time-based decay

### Cloudflare R2 (T-API-012)

- `backend/shared/storage/r2.py` — R2 + local fallback
- Profile photo upload uses R2 (falls back to local in dev)
- Env vars: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_BASE_URL`

### Seed Data

- 20 members (samuel-ocen = admin)
- 43 interest tags, 10 dating profiles (birth_year, gender, discoverability)
- 5 hubs with posts + comment threads + likes
- 10 jobs, 3 events, 2 direct threads, 10 links, sparks data

---

## What Is Remaining

### Phase 1 — Infrastructure

| Task | Status | Notes |
| --- | --- | --- |
| **T-API-012 R2** | Code done ✅ | Set `R2_*` env vars in production `.env` |
| **T-DEC-003 PostgreSQL** | Not started | ~2 weeks; unblocks pgvector + embeddings |
| **T-DEC-007 Celery + Redis** | Not started | Needed for bulk push fanout, scheduled decay, ML jobs |

### Interest Graph — Phase 2

- **Embedding-based ANN** — requires pgvector (PostgreSQL); upgrade Jaccard to cosine similarity on `vector(384)` embeddings
- **Persistent weight decay** — currently on-read only; needs Celery job to periodically write decayed weights back to DB
- **Training data export** — Celery job to export `lu_interest_profiles` + engagement events for ML training

### Sparks

- **Distance filtering** — requires live GPS from mobile (no lat/lng on Account currently)
- **Deck exhaustion strategy** — `?refresh=true` exists; should auto-apply after N days instead of explicit param
- **Incognito premium tier** — `discoverability=incognito` stored but not yet gated behind LinkUp+

### Missing Platform Endpoints

- `GET /v1/hubs/:id/posts/:id` — single post detail with comments
- `GET /v1/profile/@handle/posts` — a member's public hub activity
- `PUT /v1/profile/me/interests/:tag_id` — update single interest weight/mode
- `GET /v1/links/mutual/:account_id` — mutual connections between two accounts
- KYC level advancement endpoint

### Phase 2/3

- Mentorship, referrals, certificate verification
- Dating safety toolkit (share-date, photo verify, panic)
- Wallet + MoMo integration (Flutterwave service exists, wallet routes preserved)
- Hub types: institution-linked alumni, org-linked communities
- Admin console rebuild (T-API-036)

---

## How to Run

```bash
# Development
source venv/bin/activate
python -m backend.seed          # idempotent seed
python run.py                   # :5001

# Apply migrations (if starting fresh)
python -c "
from backend.app import create_app; app = create_app()
with app.app_context():
    from backend.models import db; import importlib.util
    for mfile in ['0010_hub_post_likes_and_message_reactions.py',
                  '0011_hub_post_comments_and_match_extras.py']:
        spec = importlib.util.spec_from_file_location('m', f'backend/database/migrations/{mfile}')
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        conn = db.engine.raw_connection(); m.up(conn); conn.close()
    print('Migrations done')
"

# Full audit (179 tests, ~3 min)
python audit.py
```

**Dev credentials**: phone `+256700000001`, OTP `123456`, password `linkup2026`
**Admin**: samuel-ocen (is_admin=1)

---

## Architecture Reference

Canonical docs: `/Users/mac/Desktop/github/linkup-mobo/`

- `ABOUT.md` — product vision, Interest Graph concept
- `ARCHITECTURE.md` — tech stack, ML pipeline, infra
- `CORE_DATA_MODEL.md` — all entities + matching engine spec
- `MIGRATION_PLAN.md` — full task backlog
- `DESIGN_GUIDELINES.md` — design system v1.0.0

## Forbidden Strings (build gate)

`truckeroo truck rideshare negoride ride trip driver negotiation vehicle boda ambulance cargo delivery pickup dropoff fare passenger payout`
