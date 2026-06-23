# LinkUp API — Status

**Last updated**: 2026-06-13
**Branch**: `T-API-004-delete-ride-backend`
**Audit result**: 371/371 PASS — idempotent (verified on 2 consecutive runs). Run with `python audit.py` (no patching needed).
**E2E coverage**: `python e2e_full.py` → **70/70 PASS** (the endpoints not covered by `audit.py`). Combined, **441 test cases cover 100% of the 230 `/v1` endpoints** (legacy `/api` excluded). Two real bugs found & fixed in this pass: `POST /v1/jobs/:id/contact-poster` (invalid `Message(msg_type=…)` kwarg → `type=`) and `POST /v1/jobs/:id/withdraw` (`lu_applications.status` enum missing `'withdrawn'` → migration `0031`).

> **2026-06-13 hardening pass** (see [IMPROVEMENT_PLAN.md](IMPROVEMENT_PLAN.md), Workstream A): fixed a live profile 500 + repaired 19 double-encoded `modes_enabled` rows; centralized JSON-column safety (`backend/shared/json_safe.py`); added a global JSON error envelope (no more HTML 500s); built the Faker dummy-data factory (`backend/factories/`, `python -m backend.factories --feature=<chat|professional_depth|dating_depth> --count=50`); made the audit a real gate; purged the last legacy ride code (forbidden-string gate clean); added `Idempotency-Key` support on the 5 irreversible writes. Migrations `0026`, `0027`. New dep: `Faker`.
>
> **2026-06-13 360° profiling pass** (Workstream I): professional depth (+14 cols, migration `0028` — pronouns, tagline, industry, years_experience, availability_status, social_links, portfolio_urls, achievements, languages_spoken, hourly_rate, …); dating depth (+18 cols, migration `0029` — height_cm, relationship_goal, smoking/drinking, religion/religiosity/tribe (sensitive, opt-in via `sensitive_optin`), love_languages, personality_type, deal_breakers, …); sectioned profile completion (`sections` + `sections_overall`) with an owner-only dating section. 50 dummy records backfilled per feature via the factory.
>
> **2026-06-13 realtime + intelligence + safety pass** (Workstreams B/C/D/F/G/E):
> **Realtime chat** — `backend/sockets/chat_events.py` + `realtime.py`: `message.new`, `typing.update`, `message.read`, `notification.new` over Socket.IO rooms (verified with two live clients). **Active-Now** staggering + heartbeat (active-24h 12→101). **Behavioral event log** (migration `0030` → `lu_behavioral_events`, `backend/shared/events/`, `GET /v1/admin/events`). **Explainability** on the Sparks deck (`why`/`compatibility_pct`). **Unified recommend** seam (`backend/domains/recommend/`). **Rate limiting** (`backend/shared/ratelimit.py`), **moderation hooks** (`backend/shared/moderation.py`), **mode-separation** audit guard. **Journey API** (`GET /v1/profile/journey`) + **zero-state** hints. **OpenAPI** (`GET /v1/openapi.json` — 228 paths; `GET /v1/_catalog` — 272 endpoints). New deps: `Faker`, `websocket-client` (test). **26/42 plan tasks done; remainder needs the mobile repo or external infra (Postgres/Redis/LiveKit/payments) — see IMPROVEMENT_PLAN.md §2.1.**

---

## What Has Been Done

### Architecture

- `backend/domains/<domain>/` restructure (T-API-001 ✅)
- All ride/trip/negotiation/payout code deleted (T-API-004..008 ✅)
- NegoRide → LinkUp rebrand (T-ID-001 ✅)
- Cloudflare R2 storage with local fallback (T-API-012 ✅)
- Interest Graph weighted Jaccard scoring engine (MySQL-native)
- Email service via SMTP/Gmail (STARTTLS port 587) — `backend/shared/email/service.py`
- Flask 3.0, SQLAlchemy, Flask-JWT-Extended, Flask-SocketIO (eventlet)

### DB Tables (lu_*)

| Table | Description |
| --- | --- |
| lu_accounts, lu_account_devices | Auth + push tokens + GPS + is_premium + notification_prefs |
| lu_otp_requests, lu_refresh_tokens | OTP and token lifecycle |
| lu_professional_profiles | Professional profiles with profile_views counter |
| lu_dating_profiles | Dating profiles (discoverability, gender, intent) |
| lu_education, lu_experience, lu_certifications | CV data |
| lu_interest_tags, lu_interest_profiles | 8-dimension Interest Graph |
| lu_links | Professional connections |
| lu_sparks, lu_matches | Dating actions + mutual matches |
| lu_hubs, lu_hub_memberships | Communities |
| lu_hub_posts, lu_hub_post_likes, lu_hub_post_comments | Social content |
| lu_threads, lu_thread_participants (is_archived), lu_messages, lu_message_reactions | Chat + archive |
| lu_jobs, lu_applications, lu_saved_jobs, lu_job_referrals | Job listings + referrals |
| lu_events, lu_event_rsvps | Events |
| lu_notifications | In-app notifications |
| lu_blocks, lu_reports | Safety (block/report) |
| lu_safety_contacts | Trusted safety contacts |
| lu_date_checkins (share_token, share_expires_at) | Date check-ins + live location share |
| lu_mentor_profiles | Mentorship availability |
| lu_mentorship_requests | Mentee → mentor pairing |
| lu_wallet_accounts, lu_wallet_transactions | Wallet + Flutterwave |
| lu_endorsements | Skill endorsements |
| lu_locations, lu_institutions, lu_orgs | Reference data |
| lu_verifications | KYC records |

### v1 Domain APIs — all tested in audit (366 tests)

| Domain | Key Endpoints |
| --- | --- |
| **Identity** | register, otp/*, login (OTP or password), me GET/PUT, logout, refresh, device, password, kyc/advance, location (GPS), otp/request?medium=email |
| **Profile** | me CRUD, @handle (view increments profile_views), @handle/posts, compatibility/:id, photo (R2), education/experience CRUD, certifications CRUD+PUT, dating GET/PUT/DELETE, completion, me/stats |
| **Interests** | taxonomy, search, me GET/POST, me/:tag_id PUT, remove/:id, suggestions, signal (behavioral), me?with_decay |
| **Links** | list, :id GET, request/accept/decline/remove, requests, suggestions (Interest Graph scored), mutual/:id |
| **Hubs** | list/mine/create, :id GET/PUT, join/leave/invite, members, posts GET/POST/PUT/DELETE, posts/:id detail, post likes, post comments CRUD |
| **Jobs** | list, mine, saved, applications, post/:id GET/PUT/close, apply, save, applicants, applications/:id/status (recruiter), referral, referrals/sent, referrals/received, referrals/:id/respond |
| **Events** | list, mine, going, create/:id GET/PUT/DELETE, attendees, rsvp |
| **Chat** | threads list (unread/archived filters)/create/:id, participants, archive toggle, messages GET/POST/DELETE (24h), reactions, read |
| **Sparks** | deck (scored + auto-refresh + distance filter), action, matches, matches/:id/unmatch, matches/:id/met |
| **Mentorship** | mentors browse/search, mentors/me CRUD, mentors/@handle, requests POST/sent/received, requests/:id/respond, requests/:id/complete, requests/:id/withdraw |
| **Feed** | home (mixed hub_posts/jobs/events, filterable, paginated) |
| **Wallet** | balance, transactions (filterable), topup initiate, topup/:ref/verify |
| **Endorsements** | create (connections only), received, @handle (public), :id DELETE |
| **Safety** | blocks, report, contacts CRUD, date-checkins CRUD + confirm, date-checkins/:id/share-location (POST/DELETE), location/:token (public), panic (SOS) |
| **Admin v1** | stats, accounts list/search/:id GET, accounts/:id status/premium PUT, reports list/resolve, hubs list |
| **Notifications** | list, unread-count, :id/read, read-all, preferences GET/PUT |
| **Search** | people (with total), hubs (with total), jobs (with total + org_name), events (NEW), all (universal) |
| **Reference** | locations, institutions, orgs (all public) |

### Email Service (`backend/shared/email/service.py`)

**SMTP config** (`.env`): `smtp.gmail.com:587 STARTTLS` | `info@mru.ac.ug`

**Templates wired into flows:**

| Trigger | Template |
| --- | --- |
| New account registered (has email) | `send_welcome_email` |
| OTP request with `?medium=email` | `send_otp_email` |
| KYC L0→L1 or L1→L2 | `send_kyc_email` |
| Admin suspend / reinstate / close | `send_account_status_email` |
| Mentorship request received | `send_mentorship_email` |
| Job application status updated | `send_application_status_email` |
| SOS panic triggered | `send_panic_email` (to contacts with email in phone field) |
| Date location shared | `send_location_share_email` (to contacts with email in phone field) |

All sends are **async** (daemon thread) — never blocks a request.

### Mentorship System (migration 0015)

- `lu_mentor_profiles` — professionals advertising mentorship
- `lu_mentorship_requests` — mentee → mentor requests
- `GET /v1/mentorship/mentors` — browse open mentors (filter: q, mode)
- `POST/GET/PUT/DELETE /v1/mentorship/mentors/me` — manage my mentor profile
- `GET /v1/mentorship/mentors/@handle` — public mentor profile
- `POST /v1/mentorship/requests` — send request (checks capacity, no duplicate pending/accepted)
- `GET /v1/mentorship/requests/sent` — my sent requests (as mentee)
- `GET /v1/mentorship/requests/received` — received requests (as mentor)
- `POST /v1/mentorship/requests/:id/respond` — accept or decline (mentor)
- `POST /v1/mentorship/requests/:id/complete` — mark done (either party, increments session_count)
- `POST /v1/mentorship/requests/:id/withdraw` — withdraw pending request (mentee)

### Live Location Sharing (extends Dating Safety)

- `POST /v1/safety/date-checkins/:id/share-location` — generate short-lived token + URL (`expires_hours` 1–24)
- `GET /v1/safety/location/:token` — **public**, no auth required; returns owner name + location + status
- `DELETE /v1/safety/date-checkins/:id/share-location` — revoke immediately (clears token)
- Token stored in `lu_date_checkins.share_token`; auto-expires at `share_expires_at`

### Notification Preferences

- `GET /v1/notifications/preferences` — all 17 notification types with enabled/disabled state (merged with defaults)
- `PUT /v1/notifications/preferences` — update; unknown keys rejected; only known types accepted
- `create_notification()` service checks prefs before creating (skips silently if disabled)
- Types: `message.sent`, `link.*`, `spark.*`, `post.*`, `endorsement.received`, `job.referral_*`, `mentorship.*`, `safety.*`, `admin.account_*`

### Chat Improvements

- `GET /v1/threads/:id/participants` — explicit participants list with last_read_at
- `POST /v1/threads/:id/archive` — toggle archive per-participant; archived threads hidden by default
- `GET /v1/threads?archived=true` — include archived threads
- `GET /v1/threads?unread=true` — only threads with unread messages
- `is_archived` column on `lu_thread_participants`

### Job Improvements

- `GET /v1/jobs/referrals/sent` — referrals I requested as job seeker (with embedded job info)
- `PUT /v1/jobs/applications/:id/status` — recruiter updates: `shortlisted|interview|rejected|hired`
- Application status email sent to applicant on update
- `lu_applications.status` enum extended to include `interview`

### Profile Improvements

- `PUT /v1/profile/me/certifications/:id` — update an existing certification
- `GET /v1/profile/me/stats` — profile_views, connections, endorsements_received, applications_sent, hub_posts
- Profile views auto-increment on non-self `GET /v1/profile/@handle` visits

### Other Features (from prior sessions)

- Dating Safety Toolkit: safety contacts, date check-ins, SOS panic
- Admin v1 API: platform stats, account management, report review
- Hub improvements: /mine route, institution_id filter, invite endpoint
- Search improvements: events search, universal /all, total counts in all results
- Sparks: auto-refresh + distance filter (`?max_distance_km=N`)
- Incognito gating: requires `is_premium=True`
- GPS location: `POST /v1/auth/location`
- Wallet, Endorsements, Feed, Job Referrals (prior sessions)

### Seed Data

- 20 members (samuel-ocen = admin + premium)
- 43 interest tags, 10 dating profiles, 5 hubs, 10 jobs, 3 events, sparks data

---

## What Is Remaining

### Infrastructure (Requires external services)

| Task | Blocker | Notes |
| --- | --- | --- |
| **PostgreSQL migration** | ~2 weeks effort | Unblocks pgvector + ANN embeddings |
| **Celery + Redis** | Infrastructure | Persistent weight decay, bulk push fanout, ML jobs |
| **NIRA integration (KYC L3)** | External API | Placeholder in place; L2→L3 blocked with message |
| **LinkUp+ subscription billing** | Payment integration | Premium flag + gating done; payment flow not wired |

### Interest Graph — Phase 2

- Embedding-based ANN — requires pgvector (PostgreSQL)
- Persistent weight decay — on-read only now; Celery job needed
- Training data export pipeline

### Sparks

- Distance filter live data — GPS fields stored; mobile must populate `last_lat`/`last_lng`

### Phase 3 (Future)

- Dating safety photo verification
- Hub institution-structured onboarding flow
- Admin console frontend (T-API-036) — API done; React/Vue not started
- Advanced mentorship: session scheduling, video calls, feedback ratings

---

## How to Run

```bash
# Development
source venv/bin/activate
python -m backend.seed          # idempotent seed
python run.py                   # :5001

# Apply ALL migrations (if starting fresh)
python -c "
from backend.app import create_app; app = create_app()
with app.app_context():
    from backend.models import db; import importlib.util
    for mfile in ['0010_hub_post_likes_and_message_reactions.py',
                  '0011_hub_post_comments_and_match_extras.py',
                  '0012_v1_wallet_and_referrals.py',
                  '0013_premium_and_gps.py',
                  '0014_dating_safety.py',
                  '0015_mentorship.py']:
        spec = importlib.util.spec_from_file_location('m', f'backend/database/migrations/{mfile}')
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        conn = db.engine.raw_connection(); m.up(conn); conn.close()
        print(f'Applied {mfile}')
    print('All migrations done')
"

# Full audit (366 tests, ~5 min)
python audit.py
```

**Dev credentials**: phone `+256700000001`, OTP `123456`, password `linkup2026`
**Admin + Premium**: samuel-ocen (`is_admin=1`, `is_premium=1`)
**Email**: `smtp.gmail.com:587` | `info@mru.ac.ug` (configured in `.env`)

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
