# LinkUp API — Phase 0 Status

**Last updated**: 2026-05-31  
**Branch**: `T-API-004-delete-ride-backend`  
**Audit result**: 74/74 PASS (idempotent — verified on 2 consecutive runs)

---

## What Has Been Done

### Architecture
- Backend restructured to `backend/domains/<domain>/` architecture (T-API-001 complete)
- All ride/trip/negotiation/payout backend code deleted (T-API-004..008 complete)
- NegoRide → LinkUp rebrand complete (T-ID-001 complete)

### v1 Domain APIs (`/v1/*`)

| Domain | Endpoints | Status |
|--------|-----------|--------|
| **Identity** | `/v1/auth/register`, `/v1/auth/otp/*`, `/v1/auth/login`, `/v1/auth/me`, `/v1/auth/logout`, `/v1/auth/refresh` | ✅ Complete |
| **Profile** | `/v1/profile/me` (GET/PUT/DELETE), `/@handle`, `/me/education`, `/me/experience`, `/me/dating`, `/completion` | ✅ Complete |
| **Interests** | `/v1/interests/taxonomy`, `/search`, `/me`, `/suggestions` | ✅ Complete |
| **Links** | `/v1/links` (list/request/accept/decline/remove), `/requests`, `/suggestions` | ✅ Complete |
| **Hubs** | `/v1/hubs` (CRUD), `/:id/join`, `/leave`, `/posts`, `/members` | ✅ Complete |
| **Jobs** | `/v1/jobs` (CRUD), `/apply`, `/save`, `/mine` | ✅ Complete |
| **Events** | `/v1/events` (CRUD), `/:id/rsvp` | ✅ Complete |
| **Chat** | `/v1/threads` (list/create), `/:id/messages` (GET/POST), `/:id/read` | ✅ Complete |
| **Sparks** | `/v1/sparks/deck`, `/action`, `/matches` | ✅ Complete |
| **Notifications** | `/v1/notifications` (list/read/read-all) | ✅ Complete |
| **Safety** | `/v1/safety/blocks` (list/block/unblock), `/report` | ✅ Complete |
| **Search** | `/v1/search/people`, `/hubs`, `/jobs` | ✅ Complete |
| **Reference** | `/v1/reference/locations`, `/institutions`, `/orgs` (all public, no auth) | ✅ Complete |

### Cross-Domain Notifications (added this session)
- Chat: message send → notifies all other thread participants
- Links: link request → notifies target; link accepted → notifies requester
- Sparks: match → notifies both accounts

### Account Lifecycle
- Soft-delete via `DELETE /v1/profile/me` (sets `deleted_at`, `account_status='closed'`)
- Re-registration of closed accounts works: `otp_verify` reactivates instead of re-creating (avoids phone unique constraint violation)

### Legacy Backward Compat (`/api/*`)
- Auth, profile, wallet, chat, webhooks, admin, calls, ratings, Flutterwave routes preserved
- `GET /api/admin/system/health` and `GET /api/admin/dashboard` working with v1 JWT tokens (samuel-ocen is `is_admin=1`)

### Infrastructure
- Health endpoint: `GET /v1/health`
- MAMP MySQL socket (development) + TCP fallback
- Flutterwave payment service, OneSignal notifications, Socket.IO call signaling
- Seed data: 20 Ugandan member accounts, 43 interest tags, 5 hubs, 10 jobs, 3 events, threads, links

---

## What Is Remaining

### Phase 1 Priorities
| Task | Description |
|------|-------------|
| **T-API-012** | Uploads → Cloudflare R2 (currently stored locally) |
| **T-DEC-003** | DB migration MySQL → PostgreSQL (needed for pgvector/Interest Graph) |
| **T-DEC-007** | Add Celery + Redis async queue for notifications, ML jobs |
| **Sparks deck** | `/v1/sparks/deck` returns 0 cards for samuel-ocen (he has sparks enabled but the deck algorithm needs Interest Graph data from more users) |
| **Calling** | Socket.IO WebRTC call signaling works (legacy) but needs v1 integration |

### Phase 2 (ML / Interest Graph)
- `lu_interest_profiles` + `lu_interest_tags` schema is in place
- Interest Graph matching algorithm (8 dimensions) not yet implemented
- Recommendation engine for Links/Sparks deck not yet implemented

### Phase 3 (Platform)
- Admin console rebuild (T-API-036)
- Mentorship, referrals, certificates features
- Push notifications via OneSignal (service exists, not wired to account devices)
- Media upload pipeline to R2

### Known Minor Issues
- `GET /v1/sparks/deck` returns 0 cards on fresh seed (expected — needs more accounts with sparks enabled and dating profiles)
- Job/event counts accumulate across audit runs (test data not fully cleaned between runs — expected behavior)
- `GET /v1/profile/completion` capped at 90% — missing fields logic needs review

---

## How to Run

```bash
# Development
source venv/bin/activate
python -m backend.seed   # seed fresh data
python run.py            # start server on :5001

# Audit all endpoints
source venv/bin/activate && python audit.py
```

**Test credentials**: phone `+256700000001`, OTP `123456` (dev mode — any OTP request generates `123456`)

---

## Architecture Reference

All canonical docs live in `/Users/mac/Desktop/github/linkup-mobo/`:
- `ABOUT.md` — product vision
- `ARCHITECTURE.md` — tech stack
- `CORE_DATA_MODEL.md` — all entities
- `MIGRATION_PLAN.md` — full task backlog (T-MOB-###, T-API-###, T-DEC-###)
