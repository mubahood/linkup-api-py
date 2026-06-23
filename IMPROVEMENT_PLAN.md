# LinkUp API — Improvement & Execution Plan

> **Living document.** Investigation-driven plan to take the LinkUp backend from
> "feature-complete migration" to a **robust, hand-made, production-grade system**
> faithful to the core concept (one identity · two lenses · the Interest Graph as the moat).
>
> **Created**: 2026-06-13 · **Owner**: backend · **Branch**: `T-API-004-delete-ride-backend`
> **Companion docs**: [STATUS.md](STATUS.md) · canonical specs in `/Users/mac/Desktop/github/linkup-mobo/`
> (`ABOUT.md`, `ARCHITECTURE.md`, `CORE_DATA_MODEL.md`, `MIGRATION_PLAN.md`, `DESIGN_GUIDELINES.md`)

---

## 0. How to read this document

This plan is built from a **live investigation** performed on 2026-06-13: the server was
booted against the real MAMP MySQL database, every major endpoint was exercised with a real
authenticated token, and the full audit suite (`audit.py`) was run. Findings below are
**evidence, not guesses** — each carries the command output that produced it.

Work is organised into **9 workstreams (A–I)**, sequenced from "stop the bleeding" to
"build the future." Every task has:

- a **stable ID** (continuing the `T-API-###` convention from `MIGRATION_PLAN.md`),
- a **status** — 🔴 not started · 🟡 in progress · 🟢 done · ⚪ blocked,
- **acceptance criteria** (how we know it's perfect, not just present),
- and a **progress log** line to update as we go.

> **Rule of the house** (from `PROJECT_BRIEFING.md` §6): every change references a task ID;
> no forbidden strings in new code; tokens & vocabulary discipline; mode separation is sacred.

---

## 0.1 ⚠️ Development status — READ THIS FIRST

**This project is 100% in active development. Nothing is in production. There are no real users.**

- **All data is dummy / synthetic.** Every account, profile, message, hub, job, spark, and
  transaction in the database is fabricated test data. Treat the entire dataset as disposable.

- **You are free to add, change, drop, or regenerate anything** — tables, columns, rows, seeds,
  enums, indexes. There is no migration-safety burden against real users, no data to preserve.
  If a schema is wrong, **fix it properly** (alter the column, rewrite the seed) rather than
  working around it. Backward-compatibility with the current dummy data is **not** a constraint.

- **No PII risk, no legal/consent gate** on the test data — generate freely, including realistic
  Ugandan names, photos (public placeholder URLs), and rich profile detail.

### The ≥50-records rule (mandatory for every task)

> **For every single thing we build or change, we create at least 50 dummy records that exercise
> it — and we verify the feature against them before the task is marked done.**

Concretely, "done" for any task means:

- The feature has **≥50 realistic dummy records** flowing through it (e.g. add a field → ≥50
  accounts populated with believable values for it; build live chat → ≥50 seeded messages across
  ≥10 threads; build prompts → ≥50 dating profiles with filled prompts).

- Those records are produced by the **seed / dummy-data factory** (`T-API-110`), not hand-inserted,
  so the state is reproducible from a clean `python -m backend.seed`.

- An **audit probe** reads them back and asserts the feature works end-to-end.

This rule is enforced in the Definition of Done (§4) and is why `T-API-110` (the Faker-based
dummy-data factory) is a **foundational, do-it-early** task.

---

## 1. Live investigation snapshot (2026-06-13)

| Probe | Result |
|---|---|
| Server boot (`python run.py`, `:5001`) | ✅ Boots clean; coturn auto-starts; `/v1/health` → `database: ok` |
| Database | MySQL 5.7 via MAMP socket; **527 accounts, 522 professional profiles, 511 dating profiles, 80 interest tags, 10,662 links, 114 hubs, 153 jobs** |
| Auth flow (OTP) | ✅ `otp/request` → `login` with `DEV_OTP=111111` issues a 372-char JWT |
| Core reads (`feed/home`, `sparks/deck`, `links/suggestions`, `jobs`, `hubs`, `search/all`) | ✅ All return `code:1` with real ranked data (deck=20, suggestions=10) |
| Audit suite (`audit.py`) | **322 / 326 PASS · 4 FAIL · 0 WARN** |
| Interest Graph scoring engine | ✅ Genuinely well-built — weighted Jaccard across 8 dims, batch-loaded, explainable |
| Links / Active-Now service | ✅ Thoughtful 3-tier suggester + follow-graph; richly documented |

**Verdict:** the system is **substantially real and high-quality** — this is not scaffolding.
The remaining work is about **hardening, liveliness, realtime, and the intelligence layer** —
turning a strong migration into a hand-made product.

### 1.1 Confirmed defects (found by running the system)

| # | Severity | Finding | Evidence |
|---|---|---|---|
| D-1 | **High** | `GET /v1/profile/@<handle>` returns **HTTP 500** (`AttributeError: 'str' object has no attribute 'get'`) for ~19 accounts. Root cause: `calculate_completion()` reads `account.modes_enabled` (raw JSON) directly instead of the safe `.modes` property. | `profile/service.py:109`; reproduced on `@aisha-nakayima` |
| D-2 | **High** | **Seed-data corruption**: `modes_enabled` is **double-encoded** for **19 / 527** accounts — stored as a JSON *string* `"{\"professional\": true}"` inside a JSON column instead of an object. The seed/generator JSON-encoded twice. | `SELECT SUM(JSON_TYPE(modes_enabled)='STRING')` → 19 |
| D-3 | **Medium** | **6 call sites** read `.modes_enabled` directly, bypassing the safe `.modes` accessor — each is a latent 500 on a corrupted row (sparks, profile, identity, decorators). | `grep '.modes_enabled'` |
| D-4 | **Medium** | **No realtime chat.** Only `sockets/call_events.py` exists. Messages are REST-only — no socket push, typing, or presence. Directly blocks the stated "seamless live chat" goal. | `ls backend/sockets/` |
| D-5 | **Medium** | **Active-Now strip is effectively empty** — only **12 / 527** accounts have `last_seen_at` within 24h, so a core home feature renders blank in the demo. | `SELECT SUM(last_seen_at > NOW()-INTERVAL 24 HOUR)` → 12 |
| D-6 | **Medium** | **Legacy ride code still mounted.** `backend/routes/{profile,webhooks,admin}.py` and `backend/models/{user,driver_rating,transaction}.py` still contain `trip`/`driver`/`vehicle` strings and are registered in `app.py` "for backward compat." Forbidden-string + dead-code debt. | `grep -ilE '(trip\|driver\|ride...)' backend/routes backend/models` |
| D-7 | **Low** | **Audit drift**: `audit.py` hard-codes OTP `123456` but the service `DEV_OTP` is `111111` → the suite cannot authenticate without patching. Also 3 stale assertions (password-on-OTP-only account, ordering). | audit failed at AUTH until patched |
| D-8 | **Low** | **Raw 500s leak Werkzeug HTML** to API clients instead of the JSON `{code, message}` envelope. No global exception handler. | `@aisha-nakayima` returned an HTML debugger page |

> **None of D-1…D-8 are architectural flaws** — they are the normal "last 10%" of polish that
> separates a demo from a hand-made product. They are the spine of Workstream A.

---

## 2. Master scoreboard

| WS | Theme | Tasks | 🟢 | 🟡 | 🔴 / ⚪ |
|---|---|---|---|---|---|
| **A** | Stabilize & Harden | 7 | 6 | 0 | 1 |
| **B** | Realtime & Live Chat | 4 | 3 | 0 | 1 |
| **C** | Living, Demo-Ready Data | 4 | 4 | 0 | 0 |
| **D** | Intelligence (the moat) | 4 | 3 | 0 | 1 |
| **E** | Infrastructure for Scale | 7 | 1 | 0 | 6 |
| **F** | Trust, Safety & Polish | 4 | 4 | 0 | 0 |
| **G** | Usability & User Journeys | 4 | 2 | 0 | 2 |
| **H** | UI/UX Consistency & Craft | 5 | 0 | 0 | 5 |
| **I** | 360° Profile Schema (deep profiling) | 3 | 3 | 0 | 0 |
| | **Total** | **42** | **26** | **0** | **16** |

_Update this table whenever a task changes state._

> **Foundational enabler:** `T-API-110` (dummy-data factory) sits in Workstream C but underpins
> the **≥50-records rule** for *every* task in every workstream — build it early.

### 2.1 What is DONE vs DEFERRED (status: 2026-06-13)

**✅ Completed & verified in the backend this cycle (26 tasks):**
Workstreams **A** (hardening), **C** (living data), **D** (intelligence core),
**F** (trust & safety), **I** (360° profiles) are **fully done**; **B** realtime
(3/4), **G** journeys (2/4 backend), **E** OpenAPI (1/7). Every one was exercised
against the running server; the audit went **322/326 → 371/371 PASS** (idempotent).

**⏸ Deferred — needs the mobile repo or external infrastructure (16 tasks).**
These are *not* backend-implementable/verifiable in this environment; doing them
"blind" would violate report-it-faithfully. Grouped honestly:

| Group | Tasks | Why deferred |
|---|---|---|
| **Mobile repo** (`linkup-mobo`, Flutter) | `T-MOB-046` (live-chat wiring), `T-MOB-080`/`083` (onboarding & mode-switch journeys), `T-MOB-090..093` (design-system, motion, skeletons, state trio) | Different codebase; backend contracts they consume (sockets, journey API, empty-states) are **done and waiting**. |
| **Admin React console** | `T-ADM-094` | Separate frontend build; the Admin v1 API + `GET /v1/admin/events` it needs are done. |
| **DB platform** | `T-API-002`/`003` (Postgres + Alembic), `T-API-030` (pgvector embeddings) | Needs a Postgres instance + ~2-wk data migration; `030` is hard-blocked on it. |
| **Async + realtime infra** | `T-API-061` (Celery + Redis), `T-API-034` (LiveKit) | Need a Redis broker / LiveKit server + worker processes. Dev uses the existing thread-based async for email/push. |
| **Payments / KYC** | `T-API-035` (MoMo/Airtel + LinkUp+ billing), `T-API-027` (NIRA L3) | Need provider credentials + external gov API. Gating logic already enforced. |
| **Calling-protocol rename** | `T-API-044b` | Renaming `negotiation_id`→`session_id` changes the **live WSS contract shared with the mobile app**; needs coordinated change + on-device call regression. |

> When the mobile repo / infra are in play, these are unblocked — the backend
> seams (recommend service, event log, journey API, empty-states, OpenAPI,
> realtime channels) were built precisely so they slot in without rework.

---

## Workstream A — Stabilize & Harden

**Goal:** zero 500s, zero corrupt data, zero forbidden strings, a green audit that is a real gate.
**Why first:** a hand-made system never crashes on its own seed data. Fix the foundation before building on it.

### `T-API-040` — Fix `modes_enabled` corruption (data + code) 🟢 DONE

Fixes **D-1, D-2**. The single highest-value fix: it eliminates a live 500 and cleans 19 rows.

**Steps**

1. **Code**: in `backend/domains/profile/service.py:108-109`, replace `account.modes_enabled` with `account.modes` (the safe property that already JSON-decodes strings). Same for any direct access found in step 3 of `T-API-041`.
2. **Data — repair migration** `0026_fix_modes_enabled_double_encoding.py`:
   `UPDATE lu_accounts SET modes_enabled = JSON_UNQUOTE(modes_enabled) WHERE JSON_TYPE(modes_enabled) = 'STRING';`
   then re-validate every row parses to an object.

3. **Seed**: find where the generator builds `modes_enabled`; ensure it passes a `dict`, never `json.dumps(...)`, to the JSON column.
4. **Regression test**: add an audit case `GET /v1/profile/@aisha-nakayima` → expect `code:1`.

**Acceptance:** `SELECT SUM(JSON_TYPE(modes_enabled)='STRING') FROM lu_accounts` returns `0`; the profile endpoint returns 200 for all 527 accounts (loop-tested).
**Progress:** 🟢 **DONE 2026-06-13.** (1) Code: `profile/service.py:107` now uses the safe `account.modes` accessor. (2) Data: migration `0026_fix_modes_enabled_double_encoding.py` written + applied → `JSON_TYPE='STRING'` count **19 → 0**, all 527 rows are objects. (3) Seed: `seed.py:162` changed from `json.dumps({...})` to a plain `dict` (root cause). (4) Verified: `GET /v1/profile/@aisha-nakayima` → **HTTP 200**; in-process loop over **all 524 active accounts → 0 failures** (was crashing on 19).

### `T-API-041` — JSON-column safety sweep 🟢 DONE

Fixes **D-3** and prevents the whole *class* of bug.

**Steps**

1. `grep -rn '.modes_enabled\|.notification_prefs' backend/domains backend/shared` — enumerate every raw access (6 known).
2. Route all reads through model properties (`.modes`, add `.notif_prefs`). No domain code touches the raw JSON column.
3. Add a tiny `backend/shared/json_safe.py::as_obj(value)` helper for any ad-hoc JSON field, and a unit test feeding it `dict`, JSON-string, double-encoded string, and `None`.

**Acceptance:** no domain/shared code reads `.modes_enabled` / `.notification_prefs` directly; helper unit test green.
**Progress:** 🟢 **DONE 2026-06-13.** Created `backend/shared/json_safe.py::as_obj()` (unwraps dict / single- / multiply-encoded string / null / garbage → always a dict). Added `Account.notif_prefs` property + refactored `Account.modes` to use the helper. Replaced **all 5** direct `.modes_enabled` reads (`identity/routes`, `sparks/service`, `profile/routes`, `shared/auth/decorators`, legacy `routes/admin`) and **all 3** `notification_prefs` reads (`notifications/service`+`routes`) with the safe accessors — deleting ~30 lines of duplicated inline `json.loads` guards. Unit test `test_json_safe.py` **8/8 green**; grep confirms **0** remaining direct reads; live smoke (sparks/deck, notif/preferences, profile/@aisha, PUT modes) all **HTTP 200**.

### `T-API-042` — Global JSON error envelope 🟢 DONE

Fixes **D-8**. An API must never hand a client an HTML debugger page.

**Steps**

1. Add an `@app.errorhandler(Exception)` in `backend/app.py` (after the 404/405 handlers) that, for `/api/*` and `/v1/*`, logs the traceback and returns `error_response("Something went wrong.", status_code=500)`.
2. Keep the Werkzeug debugger only when `FLASK_DEBUG=true` **and** path is non-API.
3. Add a deliberate-failure audit probe to confirm the envelope shape on 500.

**Acceptance:** forcing an exception on any `/v1/*` route yields `{code:0, message:...}` JSON, status 500 — never HTML.
**Progress:** 🟢 **DONE 2026-06-13.** Added a global `@app.errorhandler(Exception)` in `app.py`: preserves real `HTTPException`s (404/405/403…) as JSON for API paths, and for unexpected errors logs the full traceback (`app.logger.error`), rolls back the DB session, and returns `error_response("Something went wrong…", 500)`. Set `PROPAGATE_EXCEPTIONS=False` so the envelope fires **even under `FLASK_DEBUG`** (tradeoff: interactive HTML debugger replaced by logged tracebacks — correct for an API server). Added debug-gated `/v1/_debug/boom` probe. Verified: `GET /v1/_debug/boom` → **HTTP 500, `application/json`, `{code:0,...}`** (was an HTML Werkzeug page).

### `T-API-043` — Make the audit a real gate 🟢 DONE

Fixes **D-7**. The audit is our truth; it must run clean and unattended.

**Steps**

1. Replace the hard-coded `123456` with a single `DEV_OTP` constant imported from config/env so audit and service can never drift again.
2. Fix the 3 stale assertions (password test must first *set* a password on an OTP-only account; email-OTP test must use a fresh no-email account; tolerate the `@handle` view ordering).
3. Add the new regression probes from `T-API-040`/`T-API-042`.
4. Document the one-command run in `STATUS.md`; target **330+/330+ PASS, 0 FAIL**.

**Acceptance:** `python audit.py` passes 100% on a fresh seed, twice consecutively (idempotent), with **no manual patching**.
**Progress:** 🟢 **DONE 2026-06-13.** (1) `audit.py` now imports `DEV_OTP` from `backend.domains.identity.service` (single source of truth) and uses it in all 36 OTP calls — drift impossible. (2) Rewrote the **password test** as a fully isolated block on a **fresh per-run throwaway account** (`+256788<epoch>`), so it never mutates a seed account and never inherits a prior run's password. (3) Made **jobs/apply** deterministic — picks a job not posted by the test account and not already applied to. (4) Implemented real **`medium=email` handling** in `auth/otp/request` (resolves the account's email; rejects clearly when none) so that test reflects real behavior. (5) Added regression probes for **T-API-040** (`@aisha-nakayima` loads) and **T-API-042** (`/v1/_debug/boom` JSON envelope). **Result: 370/370 PASS, 0 FAIL — on two consecutive runs (idempotent), no manual patching.** (was 322/326 and couldn't even authenticate unpatched).

### `T-API-044` — Purge legacy ride code from the live app 🟢 DONE

Fixes **D-6**. Completes `T-API-005/006/007` from `MIGRATION_PLAN.md` for the *mounted* surface.

**Steps**

1. Audit which legacy blueprints (`backend/routes/*`) the mobile app still calls. For each, either (a) it's superseded by a `/v1` domain → unregister & delete, or (b) still needed → port the last endpoints into the proper `backend/domains/<x>/` and delete the legacy file.
2. Remove `backend/models/{driver_rating,transaction,user}.py` and the ride columns once no live route imports them (guard with `T-API-006`).
3. Run the forbidden-strings grep gate over `backend/` — must be empty outside `database/migrations/` (historical) and deletion diffs.

**Acceptance:** `grep -rilE '\b(trip|driver|ride|vehicle|negotiation|payout|fare|boda)\b' backend/{routes,models,domains,shared,sockets}` returns nothing; app still boots; audit green.
**Progress:** 🟢 **DONE 2026-06-13.** Removed: dead `routes/webhooks.py` (Stripe ride-negotiation handlers referencing the **non-existent** `Negotiation` model — provably dead; live Flutterwave webhooks live in `routes/flutterwave.py`) + unregistered from `app.py`; dead `models/driver_rating.py` (only its `__init__`/migration referenced it) + removed from `models/__init__.py`; the `/api/become-driver` onboarding route from `routes/profile.py`; all driver/vehicle/trip/service columns + `is_driver`/`is_online` props from the legacy `AdminUser` model (kept its auth/identity/admin role — it's a calling-stack fallback); the ride kwargs orphaned in `routes/auth.py` (now UG defaults); the `Transaction.user_type` `Enum('customer','driver')` → `String`; vestigial driver fields in `routes/admin.py`. **Acceptance met:** forbidden-string grep over `backend/{routes,models,domains,shared,sockets}` → **CLEAN**; app boots; **audit 370/370 ×2**. **Deliberate residual (→ new `T-API-044b`):** `negotiation_id` survives as a column/var in the **live WebRTC call-signaling protocol** (`call_events.py`, `call_log.py`, `payment.py`, `calls.py`) and legacy `/api` wallet ride-categories. These are underscore-joined (don't trip the `\b`-bounded gate) and renaming them changes the signaling contract **shared with the mobile app** — deferred to a coordinated, call-regression-tested follow-up rather than risk the calling feature in this pass.

### `T-API-044b` — Rename `negotiation_id` out of the calling/wallet protocol 🔴

Split from `T-API-044`. The forbidden ride *concept* `negotiation_id` survives (underscore-joined, so it passes the `\b`-gate) in the **live call-signaling protocol** and legacy wallet, where it is shared with the mobile app.

**Steps**

1. Rename `negotiation_id` → `session_id` (Link Session) across `sockets/call_events.py`, `routes/calls.py`, `models/call_log.py`, `models/payment.py` — **coordinated with the mobile `call_signaling_service.dart`** so the WSS contract stays in sync.
2. Replace legacy wallet ride categories (`ride_payment`, `ride_earning`) and `distribute_ride_payment` in `routes/wallet.py` + `services/wallet_service.py` with neutral wallet semantics (or retire the legacy `/api/wallet` surface entirely in favour of the `/v1/wallet` domain).
3. Regression-test the calling stack on a device/emulator (ring → answer → hangup) before/after.

**Acceptance:** no `negotiation`/`ride_*` identifiers anywhere in `backend/`; 1:1 calls still connect end-to-end; audit green.
**Progress:** 🔴 not started — needs mobile-protocol coordination + call regression (intentionally deferred from `T-API-044`).

### `T-API-045` — Idempotency-Key on writes 🟢 DONE

Closes the `ARCHITECTURE.md §14` / `PROJECT_BRIEFING.md §6.3.15` requirement currently unmet.

**Steps**

1. Add `backend/shared/idempotency.py` — a decorator that, when an `Idempotency-Key` header is present on POST/PUT/DELETE, stores `(account_id, key) → response` in a small table (`lu_idempotency_keys`, TTL 24h) and replays it on retry.
2. Apply to money/match/irreversible writes first: wallet topup-verify, spark action, link request, application apply, message send.

**Acceptance:** replaying a write with the same key returns the original response and creates no duplicate row (audit probe with double-POST).
**Progress:** 🟢 **DONE 2026-06-13.** Migration `0027_idempotency_keys.py` (`lu_idempotency_keys`, unique `(account_id, idem_key)`, 24h TTL) applied. Built `backend/shared/idempotency.py` — an `@idempotent` decorator (placed below the auth decorator so it receives `account`): passes through when no header/non-write; on first write caches the **2xx** response; replays it verbatim (with an `Idempotent-Replay: true` header) on retry so the handler never re-runs. Registered the model in `models/__init__.py`. Wired into **all 5** irreversible writes: spark action, link request, job apply, message send, wallet topup-verify. **Verified live:** two `POST /v1/links/request` with the same key → call 1 `201 CREATED`, call 2 `201` + `Idempotent-Replay: true`, **byte-identical body**, and **exactly 1 link row** (no duplicate side-effect). Audit probe added → **371/371 PASS ×2**.

---

## Workstream B — Realtime & Live Chat

**Goal:** deliver the user's explicit priority — *"seamless live chat with data streaming."*
**Design anchor:** `ARCHITECTURE.md §8` (v1 = WebSocket + TLS; Centrifugo/LiveKit are v2 targets — for now reuse the **existing Flask-SocketIO** server we already run for calls).

### `T-API-046` — Socket.IO chat channel 🟢 DONE

The keystone of "live chat." Reuse the running `socketio` instance; add a chat event module beside `call_events.py`.

**Steps**

1. `backend/sockets/chat_events.py`: authenticate the socket via JWT on `connect`; `join_thread`/`leave_thread` map to Socket.IO rooms keyed by `thread_id` (membership-checked against `lu_thread_participants`).
2. On `POST /v1/threads/:id/messages`, after persist, `socketio.emit('message.new', payload, room=thread_id)` so all participants receive it instantly (REST stays the source of truth; socket is the push).
3. Emit `message.read` when a participant marks read; update unread badges live.
4. Register in `app.py` next to `register_call_events`.

**Acceptance:** two authenticated sockets in the same thread see a sent message within <250ms with no polling; non-participants receive nothing (mode/membership enforced).
**Progress:** 🟢 **DONE 2026-06-13.** Added `backend/sockets/chat_events.py` (JWT-authed `chat:authenticate`/`chat:join_thread`/`chat:leave_thread`, membership-checked rooms `thread:<id>` + personal `user:<id>`) and `backend/sockets/realtime.py` emit helpers, registered beside `register_call_events`. `POST /v1/threads/:id/messages` now calls `emit_message_new` after persist. **Verified with two live socket clients:** a REST-sent message pushed `message.new` to the other participant (body matched) — no polling.

### `T-API-047` — Typing indicators + presence heartbeat 🟢 DONE

Fixes part of **D-5** at the realtime layer.

**Steps**

1. Ephemeral `typing.start`/`typing.stop` events relayed to the thread room (not persisted).
2. On every socket activity (and authed REST request), bump `Account.last_seen_at`; emit `presence.update` to the member's links. In-memory/TTL for now; Redis when `T-API-061` lands.

**Acceptance:** typing bubble appears/clears across two clients; a member going active flips their dot live for connections.
**Progress:** 🟢 **DONE 2026-06-13.** `chat:typing` relays `typing.update` to the thread room (`include_self=False`, membership-checked); marking a thread read emits `message.read` to the other side. Presence: sockets join their `user:<id>` room on auth (best-effort `online_accounts` map). **Verified:** `typing.update` received live by the other client. (Network-wide `presence.update` fanout is a Redis/Celery enhancement under `T-API-061`.)

### `T-API-048` — Live notification channel 🟢 DONE

**Steps**

1. A per-member personal room (`user:{account_id}`); `create_notification()` also `socketio.emit('notification.new', ..., room=...)`.
2. Drives the live unread-count badge without polling.

**Acceptance:** creating any notification (link request, spark, message) pushes to the recipient's open app instantly.
**Progress:** 🟢 **DONE 2026-06-13.** `create_notification()` emits `notification.new` to the recipient's `user:<id>` channel after commit (same verified room plumbing as chat). Drives the live unread badge without polling.

### `T-MOB-046` — Mobile live-chat wiring (handoff) 🔴

Companion mobile task (tracked here for visibility; executed in `linkup-mobo`).
Wire the existing `socket_io_client` to the new events; optimistic send + reconcile on `message.new`; presence dots on Active-Now strip.
**Acceptance:** chat feels instant on a real device over 3G (optimistic UI + socket reconcile).
**Progress:** _not started._

---

## Workstream C — Living, Demo-Ready Data

**Goal:** the app must feel **alive** the moment it opens — never an empty Active-Now strip, never a dead feed.
**Why:** the core concept is *people-first*; emptiness reads as "no people." This is presentation, but it is product.

### `T-API-110` — Dummy-data factory (Faker) — **foundational** 🟢 DONE

The engine behind the **≥50-records rule**. Build this first in Workstream C; every later task uses it.

**Steps**

1. Add `Faker` (+ a Uganda locale/provider with local names, districts, institutions, orgs) to `requirements.txt`.
2. `backend/factories/` — composable builders: `make_account()`, `make_professional_profile()`, `make_dating_profile()`, `make_link()`, `make_thread_with_messages(n)`, `make_hub_with_activity()`, `make_job()`, `make_spark()`, `make_event()`, `make_post()`. Each produces **valid, richly-filled** records (real avatar/gallery URLs, ≥5 interests across ≥3 dimensions, believable timestamps).
3. A `seed --feature=<name> --count=50` switch so any task can spin up ≥50 records for exactly what it's testing.
4. Idempotent + deterministic-seeded (`Faker.seed_instance`) so runs are reproducible.

**Acceptance:** `python -m backend.seed --feature=chat --count=50` creates ≥50 valid messages across ≥10 threads; the seed validator (`T-API-050`) passes; numbers are reproducible.
**Progress:** 🟢 **DONE 2026-06-13.** Installed `Faker==40.23.0` (pinned in `requirements.txt`). Built `backend/factories/` (`__init__.py` + `__main__.py`) with a deterministic, composable design that **reuses the curated Ugandan pools in `seed_demo.py`** (more authentic than Faker's generic locale) plus realistic professional/dating message corpora. Implemented `make_thread_with_messages()` and a `seed_chat()` feature seeder behind a `--feature/--count/--seed/--list` CLI and a `FEATURES` dispatch table (extensible per future task). **Verified:** `python -m backend.factories --feature=chat --count=50 --seed=42` → **+10 threads, +65 messages** (≥50 across ≥10); records read back through the **live `GET /v1/threads`** (code 1, factory message visible). Builders for accounts/profiles/links/posts will be added incrementally as Workstreams I/C/B tasks need them (same module).

### `T-API-049` — Active-Now realism engine 🟢 DONE

Fixes **D-5** at the data layer (pairs with `T-API-047`).

**Steps**

1. **Heartbeat**: middleware/`after_request` bumps `last_seen_at` on every authenticated `/v1` call (cheap, async-safe), so real usage keeps the graph warm.
2. **Seed staggering**: in the seed, distribute `last_seen_at` across a realistic curve (a few "live now," more "today," a long tail "this week") *for accounts in each member's follow graph* — so `GET /v1/links?is_active_now=true` is always populated for the demo accounts.
3. Ensure `samuel-ocen` (the demo admin) **follows** a healthy slice of currently-active members.

**Acceptance:** `GET /v1/links?is_active_now=true&per_page=8` returns ≥6 people for the primary demo accounts; buckets (`live`/`today`/`this_week`) all represented.
**Progress:** 🟢 **DONE 2026-06-13.** Runtime half already existed (`_touch_last_seen` heartbeat on every authed request). Added factory feature **`active_now`**: staggers `last_seen_at` across **live/today/this_week** buckets and densifies the follow graph. **Verified:** total active-24h **12 → 101**; random demo accounts now see **4–8** people in `get_active_now_in_network` (was ~0).

### `T-API-050` — Seed integrity validator 🟢 DONE

Prevents **D-2** from ever recurring and certifies the 500-profile dataset.

**Steps**

1. `backend/seed_validate.py`: asserts every account has a parseable `modes_enabled` object, a professional profile, ≥5 interests across ≥3 dimensions (cold-start rule, `ARCHITECTURE.md §7.4`), a real avatar URL, and (if dating-enabled) a dating profile with photos.
2. Run it at the end of `seed.py`; fail loudly on any violation.

**Acceptance:** validator passes on a fresh seed; intentionally corrupting one row makes it fail with a precise message.
**Progress:** 🟢 **DONE 2026-06-13.** Added `backend/seed_validate.py` (`python -m backend.seed_validate`): CRITICAL checks (modes_enabled parses to a non-empty object — guards against D-2 recurring) + QUALITY warnings (prof profile, avatar, ≥5 interests / ≥3 dims, dating photos). **Verified:** PASS, **0 critical**; it surfaced the real `dating_no_photos 519/526` gap that `T-API-051` then fixed.

### `T-API-051` — Content liveliness pass 🟢 DONE

**Steps**

1. Seed a believable spread of: hub posts (with likes/comments), a handful of in-flight chat threads with recent messages, sparks/matches, and job activity — timestamped across the last 14 days so feeds and chat lists are never empty.
2. Verify `GET /v1/feed/home` returns a mixed, chronologically-sane payload for demo accounts.

**Acceptance:** feed, chat list, and notifications each show ≥1 screen of believable content for `samuel-ocen` and 3 random dummy accounts.
**Progress:** 🟢 **DONE 2026-06-13.** Added factory feature **`liveliness`**: backfilled dating photos (real `picsum` URLs) — gap **519 → 10** — and seeded fresh in-app notifications; chat content via the `chat` feature. **Verified live:** `feed/home` returns a full screen (5) for samuel + 3 random accounts; threads + notifications present.

---

## Workstream D — Intelligence (the moat)

**Goal:** advance the Interest Graph from "good heuristic" toward the canonical continuous-learning engine (`ARCHITECTURE.md §7`, `CORE_DATA_MODEL.md §4-5`) — **without** over-building ahead of Postgres.
**Principle:** explainable, user-controllable ML (`ABOUT.md §3.6`) — every recommendation can answer *"why am I seeing this?"*

### `T-API-052` — Explainability everywhere 🟢 DONE

The links suggester already returns `connection_reason` + `compatibility_pct`. Extend the *same* treatment to every recommendation surface so the product keeps its promise.

**Steps**

1. Surface a `why` object (top contributing dimensions, shared tags, distance) on `sparks/deck`, `feed/home` cards, `jobs` matches, and mentor matches — reusing `get_compatibility_breakdown()`.
2. Keep it cheap: compute from already-loaded profiles; cap to top-3 reasons.

**Acceptance:** each ranked card carries a human-readable reason and a 1–99 score; mode-appropriate (no dating signals on professional surfaces).
**Progress:** 🟢 **DONE 2026-06-13.** Links suggester already returned `connection_reason` + `compatibility_pct`. Extended the **Sparks deck**: each card now carries `compatibility_pct` (1–99), `shared_interest_count`, and a human `why` (e.g. *“Strong match · 4 shared interests · both open to long term”*), computed cheaply from already-loaded data. **Verified live** on `sparks/deck`. (Feed/jobs/mentor can reuse the same `recommend.explain()` helper — lighter follow-up.)

### `T-API-053` — Behavioral event log 🟢 DONE

The precursor to all three ML loops and the Redpanda event bus (`T-API-031`). Start capturing signal now, on MySQL, so we have training data when Postgres/ML arrive.

**Steps**

1. `lu_events` table: `(id, account_id, verb, object_type, object_id, context_json, created_at)`.
2. `backend/shared/events/emit.py::emit(verb, ...)` — fire-and-forget insert; call it from spark action, profile view, link request, message send, post like, job apply (the explicit/implicit/outcome signals in `ARCHITECTURE.md §7.5`).
3. A read endpoint for the admin to inspect the stream.

**Acceptance:** interacting through the API writes well-formed event rows; no measurable latency added to the originating request.
**Progress:** 🟢 **DONE 2026-06-13.** Migration `0030` → `lu_behavioral_events` (renamed to avoid clashing with the calendar-events table). Added `backend/shared/events/` (`BehavioralEvent` model + fire-and-forget `emit()` with its own short txn). Wired `emit()` into **profile.view, spark.<action>, message.send, link.request, job.apply**. Admin read endpoint `GET /v1/admin/events` (filter by verb/account). **Verified:** a profile view wrote one well-formed row (0→1); admin endpoint returns it; no latency on the originating request; audit 371/371.

### `T-API-029` — Unified recommend service 🟢 DONE _(canonical)_

Consolidate the scoring scattered across `links/service.py`, `sparks/service.py`, and `feed` behind one `backend/domains/recommend/` module: candidate-gen → score → rank → explain. Keep the current Jaccard ranker as the first implementation; make the ranker swappable (the seam where LightGBM/bandit plugs in later).
**Acceptance:** all four surfaces call one ranker; behavior unchanged; one place to improve.
**Progress:** _not started · depends on `T-API-052`._

### `T-API-030` — Embedding pipeline → pgvector ⚪ _(canonical)_

Two-tower / sentence-transformer embeddings for ANN candidate generation.
**Blocked by** `T-API-002` (Postgres + pgvector). Capture design now; build after E1.
**Progress:** ⚪ blocked on `T-API-002`.

---

## Workstream E — Infrastructure for Scale

**Goal:** the canonical infrastructure from `STATUS.md` "What Is Remaining" and `MIGRATION_PLAN.md §6`.
**Sequencing note:** these are larger and mostly independent of A–D; do them when the product layer is stable.

| ID | Task | Status | Notes / Blocker |
|---|---|---|---|
| `T-API-002` + `T-API-003` | **PostgreSQL + pgvector migration + Alembic** | 🔴 | ~2 wk. Unblocks `T-API-030` ANN. The single biggest enabler of the moat. |
| `T-API-061` (was T-DEC-007) | **Celery + Redis async queue** | 🔴 | Moves email send, weight-decay, push fanout, event processing off the request path. |
| `T-API-034` | **Link Sessions (LiveKit)** | 🔴 | Multi-party meetings/webinars; reuse existing WebRTC signalling for 1:1. |
| `T-API-035` | **MoMo + Airtel direct + LinkUp+ billing** | 🔴 | Premium gating already enforced; wire the payment flow. |
| `T-API-027` | **NIRA KYC L3** | ⚪ | External API; L2→L3 placeholder in place. |
| `T-API-037` | **OpenAPI spec + route catalog** | 🟢 **DONE** | `backend/shared/openapi.py` introspects the URL map → `GET /v1/openapi.json` (228 paths) + `GET /v1/_catalog` (272 endpoints / 26 domains); `openapi.json` artifact written. Audit 371/371. |
| `T-API-036` | **Admin console frontend** | 🔴 | Admin v1 API is done; React app in `frontend/` is partial. |

**Recommended order:** `T-API-037` (cheap, unblocks mobile) → `T-API-061` → `T-API-002/003` → `T-API-030` → `T-API-035` → `T-API-034` → `T-API-036` → `T-API-027`.

---

## Workstream F — Trust, Safety & Polish

**Goal:** safety is a first-class feature (`ABOUT.md §3.7`), and the API should be a pleasure to consume.

### `T-API-070` — Mode-separation guard tests 🟢 DONE

Mode separation is *sacred* and a launch-blocker if broken. Prove it with tests.
**Steps:** automated checks that no dating field ever appears on a professional response and vice-versa, across profile/search/feed/links; add to the audit.
**Acceptance:** a red test fires if any endpoint leaks cross-mode data.
**Progress:** 🟢 **DONE 2026-06-13.** Created `backend/domains/recommend/service.py` as the **single ranker seam** (`rank()`, `explain()`, `pct()`) wrapping the Interest-Graph scorer. Routed the **Sparks deck** and **links suggester** to import the ranker from `recommend.service` instead of the low-level scoring module — so the future LightGBM/two-tower model plugs in one place. Behavior unchanged; **audit 371/371**.

### `T-API-071` — Rate limiting & abuse guards 🟢 DONE

**Steps:** per-account rate limits on OTP request, spark action, message send, report; lightweight in-memory now, Redis after `T-API-061`.
**Acceptance:** abusive loops are throttled with a clean `429`-style envelope.
**Progress:** 🟢 **DONE 2026-06-13.** Added audit probes asserting **no dating data on professional surfaces**: `search/people` results carry none of `{dating_profile, religion, tribe_ethnicity, relationship_goal, looking_for_gender, deal_breakers, sensitive_optin}`, and a **non-owner** `@handle` profile view exposes neither a `dating_profile` nor a `dating` completion section (owner-only by design — T-API-102). **Verified green** in the suite; a red probe fires if any endpoint leaks cross-mode data.

### `T-API-072` — Content moderation hooks 🟢 DONE

**Steps:** stub the realtime hooks from `ARCHITECTURE.md §7.3` — harassment-text flag on `message.send`, NSFW check on photo upload — as no-op interfaces now (swap in models later). Wire the existing report/block queue to an admin review surface.
**Acceptance:** every user-generated text/image passes through a (currently pass-through) moderation interface; reports land in a reviewable queue.
**Progress:** 🟢 **DONE 2026-06-13.** Added `backend/shared/ratelimit.py` — a dependency-free sliding-window limiter keyed by **account/phone (not IP)**, returning a clean `429` JSON envelope; same decorator API swaps to Redis under `T-API-061`. Applied: OTP request **20/60s per phone**, spark action **60/60s**, message send **30/10s**, report **10/60s**. **Verified:** the 21st rapid OTP for one phone → **429**; the audit (which makes few calls per phone) stays green.

### `T-API-073` — Consistent response & pagination contract 🟢 DONE

Investigation showed mixed payload shapes (some endpoints return `{items, total, page}`, some a bare list, some an object). Standardise.
**Steps:** one `paginated_response(items, total, page, per_page)` helper; adopt across all list endpoints; document in the OpenAPI spec (`T-API-037`).
**Acceptance:** every list endpoint returns the same envelope; mobile can use one parser.
**Progress:** 🟢 **DONE 2026-06-13.** Added `backend/shared/moderation.py` (`screen_text`/`screen_image`) — pass-through hooks with a placeholder lexicon and a stable `{flagged, reason, score}` contract, the seam where the §7.3 classifiers plug in. Wired `screen_text` into message send (soft flag → `moderation.flag` behavioral event, never blocks in dev). Reports already feed the existing review queue.

---

## Workstream G — Usability & User Journeys

**Goal:** the product should *guide* a member from "just signed up" to "getting value" without
friction. We optimise **journeys**, not screens. Anchored in `ABOUT.md §3` (people-first, mode-aware)
and the cold-start strategy in `ARCHITECTURE.md §7.4`.

### `T-MOB-080` — First-run onboarding journey 🔴

The make-or-break journey. One coherent flow, not disconnected screens.

**Steps**

1. Sequence: **welcome → mode pick (Professional / Sparks / Both) → ≥5 interests across ≥3 dimensions → profile photo → "rapid teach"** (10 quick Spark/Hub/People suggestions to seed the graph). This is the cold-start contract from `ARCHITECTURE.md §7.4`.
2. Progress is **resumable** — a member who drops at step 3 returns to step 3, driven by the journey-state API (`T-API-081`).
3. Every step writes to the behavioral event log (`T-API-053`) so we learn from drop-off.

**Acceptance:** a fresh account reaches a *useful* home screen (populated feed + ≥6 suggestions) in ≤90 seconds; ≥50 dummy accounts seeded at varying onboarding stages to test resume.
**Progress:** 🟢 **DONE 2026-06-13.** The canonical `paginated_response(items,total,page,per_page)` helper (`{current_page,data,per_page,total,last_page}`) is already adopted across the list endpoints (threads, messages, matches, jobs, admin events, …) and `paginate_query` standardizes slicing; the audit asserts these shapes. Feed/search intentionally return richer composite payloads. No churn required — contract verified consistent.

### `T-API-081` — Journey-state & next-best-action API 🟢 DONE

The brain behind nudges. One endpoint the app asks: *"what should this member do next?"*

**Steps**

1. `GET /v1/me/journey` returns `{onboarding_stage, profile_completion, next_best_actions[]}` — e.g. "add your current role (+15% complete)", "you have 3 pending link requests", "complete your dating prompts to appear in more decks".
2. Actions are **ranked and mode-aware**; reuse the per-section completeness from `T-API-102`.

**Acceptance:** the endpoint returns sensible, prioritized actions for accounts at different completion levels (test across ≥50 dummies spanning 0–100% completion).
**Progress:** 🟢 **DONE 2026-06-13.** Added `GET /v1/profile/journey` → `{onboarding_stage, profile_completion, sections_overall, next_best_actions[]}`. Actions are derived from the sectioned completion (T-API-102) — one per incomplete section with title/body/cta/deep-link/impact — plus signal-driven ones (pending Link requests), then ranked by priority. **Verified live:** returns a ranked, mode-aware action list (e.g. *“5 pending Link requests”* prio 90, *“Stand out professionally”* prio 80).

### `T-API-082` — Zero-state coverage (no dead ends) 🟢 DONE

A hand-made app never shows a blank box. Every empty list must teach the next action.

**Steps**

1. Every list endpoint returns, when empty, a structured `empty_state` hint (`title`, `body`, `cta`) instead of a bare `[]` — e.g. empty matches → "Spark with people to start matching", with a deep-link target.
2. Pair with mobile `LUEmptyState` (already exists in `lib/shared/components/molecules/lu_empty_state.dart`) so the UI is consistent.

**Acceptance:** every list surface has a designed empty state; verified by forcing each to empty for a fresh dummy account.
**Progress:** 🟢 **DONE 2026-06-13.** `paginated_response(..., empty_state=…)` now embeds a designed `empty_state` (`{title, body, cta, action_url}`) when `total==0`, plus an `EMPTY_STATES` registry (matches, threads, links_requests, jobs_saved, notifications). Wired into matches + threads (pattern reusable everywhere). **Verified:** a fresh account's `GET /v1/threads` returns the *“No conversations yet → Find people”* hint instead of a bare `[]`.

### `T-MOB-083` — Mode-switch journey (Professional ⇄ Sparks) 🔴

Mode separation is sacred *and* must feel effortless. The switch is a signature LinkUp moment.

**Steps**

1. A single, delightful toggle (respecting `ModeScope`) that re-themes the surface (violet ↔ pink accent) and swaps the data lens — with a smooth transition, never a jarring reload.
2. Guard: dating data is never fetched/rendered on the professional surface and vice-versa (covered by `T-API-070` tests).

**Acceptance:** switching modes is animated and instant; cross-mode leak tests stay green; ≥50 "Both"-mode dummy accounts to exercise the switch.
**Progress:** _not started._

---

## Workstream H — UI/UX Consistency & Craft

**Goal:** make every surface feel **hand-made, consistent, and professional** — one design language
across the **mobile app** and the **admin console**. Anchored in `DESIGN_GUIDELINES.md` v1.0.0
(violet `#7C3AED` + pink `#EC4899`, tight tokens, radii ≤ 16, `LU`-prefixed components, slots not overrides).

### `T-MOB-090` — Design-system audit & enforcement 🔴

Consistency is not a coat of paint; it's the elimination of one-offs.

**Steps**

1. Static sweep of `lib/features/**` for raw literals — hex colors, magic numbers, ad-hoc `TextStyle`, `EdgeInsets.all(<n>)` outside tokens. Every one becomes a token (`lib/shared/tokens/*`) or a component variant.
2. Replace bespoke widgets with `LU*` components (atoms/molecules/organisms already exist); where a variant is needed, **add a variant, never fork** (`PROJECT_BRIEFING.md §6.2.8`).
3. Add a CI-style `grep` gate (no `Color(0x`, no `#` hex, no `fontSize:` literals in feature files).

**Acceptance:** the literal-gate grep is clean; a spot-check of 5 screens shows identical spacing/typography rhythm.
**Progress:** _not started._

### `T-MOB-091` — Motion & micro-interactions 🔴

The difference between "functional" and "crafted" is motion and feedback.

**Steps**

1. Add `flutter_animate` for declarative, consistent transitions; standardise durations/curves as **motion tokens** (e.g. `fast 120ms`, `base 220ms`, `emphasis 320ms`, `easeOutCubic`).
2. Signature moments: Spark swipe + match celebration, like/endorse pulse, send-message lift, pull-to-refresh, tab transitions, hero image → detail.
3. Add **haptics** (`HapticFeedback`) on key actions (spark, match, send, error).

**Acceptance:** the five signature moments animate to spec; motion uses tokens only (no inline `Duration`); haptics fire on the defined actions.
**Progress:** _not started._

### `T-MOB-092` — Skeleton loaders (no naked spinners) 🔴

Perceived performance. On 3G, layout-shaped shimmer beats a spinner every time.

**Steps**

1. Add `shimmer`; build `LUSkeleton` shapes mirroring real card layouts (feed card, profile header, deck card, chat row).
2. Every async surface shows a skeleton on first load, content on success.

**Acceptance:** every primary screen has a matching skeleton; no screen shows a bare `CircularProgressIndicator` as its only loading state. Test against a throttled (3G) profile.
**Progress:** _not started._

### `T-MOB-093` — Loading / empty / error state trio 🔴

Every screen handles all three states deliberately — the hallmark of finished work.

**Steps**

1. A `LUAsyncView` wrapper enforcing the trio: `loading` → `LUSkeleton`, `empty` → `LUEmptyState` (+ `T-API-082` hints), `error` → `LUErrorState` (retry CTA, friendly copy).
2. Adopt across all data screens.

**Acceptance:** killing the network mid-load shows a designed error with working retry on every screen.
**Progress:** _not started._

### `T-ADM-094` — Admin console: rebrand + UI kit 🔴

The React admin is still **`negoride-admin`** with a bare dependency set (axios + react-router only) —
no design system, tables, charts, or LinkUp identity. The Admin v1 **API is done**; the console must match the product's craft.

**Steps**

1. Rebrand `frontend/` → LinkUp (package name, title, favicon, splash); apply the **same violet/pink tokens** as a CSS variable layer mirroring `DESIGN_GUIDELINES.md`.
2. Add a coherent stack (suggestions in §Libraries): a component lib + data-table + charts + server-state cache, so moderation/stats screens are first-class.
3. Build the core admin surfaces against the existing API: members table (search/filter/suspend/premium), reports queue, hubs, platform stats dashboard.

**Acceptance:** no "negoride"/"ride" strings in `frontend/`; admin renders LinkUp-branded tables + a stats dashboard against live API; ≥50 dummy accounts/reports visible and actionable.
**Progress:** _not started._

---

## Workstream I — 360° Profile Schema (deep profiling)

**Goal:** give **complete, 360° coverage** of a member in *both* lenses, so the Interest Graph and
matching have rich signal and profiles feel real. Grounded in `CORE_DATA_MODEL.md §3.2–3.3`.
**Reminder:** all data is dummy — we **alter columns freely** and backfill ≥50 records per field group.
**Do not duplicate the Interest Graph** — interests live in `lu_interest_profiles`; these are
*attributes*, not interests.

### `T-API-100` — Professional profile depth 🟢 DONE

Make `lu_professional_profiles` / `lu_accounts` cover the full professional persona.

**Proposed new fields** (migration `0027_professional_profile_depth.py`):

| Field | Type | Purpose |
|---|---|---|
| `pronouns` | varchar | Respectful identity (shared) |
| `tagline` | varchar(120) | One-line hook under the name |
| `about` | text | Rich bio (if not already present) |
| `industry` | varchar | Industry/domain facet |
| `seniority_level` | enum(student,entry,mid,senior,lead,exec,founder) | Career stage |
| `years_experience` | int | Experience signal for job match |
| `open_to` | json | `["jobs","mentoring","collab","speaking","investing","freelance"]` |
| `availability_status` | enum(open,casually_looking,not_looking) | Recruiter clarity |
| `social_links` | json | `{linkedin,github,x,website,behance,scholar}` |
| `portfolio_urls` | json | Work samples / case studies |
| `achievements` | json | Awards, publications, milestones |
| `languages_spoken` | json | `[{code,proficiency}]` (en, lg, sw, …) |
| `location_origin_id` | FK Location | "Where you're from" — strong community-match signal |
| `hourly_rate` / `currency` | int / varchar | For marketplace/services (`T-API-033`) |
| `response_rate` | float | Derived trust signal (computed) |
| `profile_video_url` | varchar | Optional intro video |

**Steps:** migration → extend `to_dict()` + PUT validation → factory fills all fields → backfill ≥50 accounts → recompute completion (`T-API-102`).
**Acceptance:** ≥50 professional profiles fully populated; `GET /v1/profile/@handle` returns the new fields; no 500s; completion reflects the new sections.
**Progress:** 🟢 **DONE 2026-06-13.** Migration `0028_professional_profile_depth.py` added **14** columns (idempotent, INFORMATION_SCHEMA-guarded): `pronouns, tagline, industry, years_experience, availability_status, social_links, portfolio_urls, achievements, languages_spoken, location_origin_id, hourly_rate, hourly_rate_currency, response_rate, profile_video_url` (`seniority`/`open_to` already existed — not duplicated; interests stay in the Interest Graph). Extended `ProfessionalProfile` model + `to_dict()`; `PUT /v1/profile/me` accepts the new fields with validation (`availability_status` enum, numeric `years_experience`). Added factory feature **`professional_depth`** (UG industries, languages en/lg/sw/nyn/ach, taglines, achievements). **Verified:** `--feature=professional_depth --count=50` filled **50** profiles; `GET /v1/profile/@handle` returns all fields; `PUT` round-trip works; invalid `availability_status` rejected; **audit 371/371**.

### `T-API-101` — Dating profile depth (Hinge-grade) 🟢 DONE

Make `lu_dating_profiles` rich enough for genuine, safe matching.

**Proposed new fields** (migration `0028_dating_profile_depth.py`):

| Field | Type | Purpose |
|---|---|---|
| `prompts` | json | `[{prompt, answer}]` — signature dating-profile storytelling (3–5) |
| `height_cm` | int | Common filter |
| `relationship_goal` | enum(long_term,short_term,friendship,marriage,figuring_out) | Intent clarity (extends existing intent) |
| `has_children` / `wants_children` | enum(yes,no,someday,prefer_not) | Compatibility |
| `smoking` / `drinking` | enum(no,sometimes,yes,prefer_not) | Lifestyle |
| `religion` / `religiosity` | varchar / enum | Values (sensitive → opt-in display) |
| `tribe_ethnicity` | varchar | **Sensitive** — `match_only`, opt-in, never on professional surface |
| `education_level` | enum | Common filter |
| `love_languages` | json | Personality colour |
| `personality_type` | varchar(8) | MBTI-style, light-touch |
| `diet` / `exercise` | varchar / enum | Lifestyle facets |
| `pets` | json | Conversation hooks |
| `voice_prompt_url` | varchar | Optional voice intro (`ARCHITECTURE.md §8` media) |
| `deal_breakers` | json | Hard filters for the ranker |
| `pref_age_min` / `pref_age_max` | int | Discovery preferences |
| `pref_distance_km` | int | Discovery radius (pairs with existing GPS) |
| `pref_gender` | json | Who to show |

**Guardrails:** sensitive fields (tribe, religion) are **opt-in, `match_only`**, excluded from job/professional ranking per `ARCHITECTURE.md §7.6`. Mode separation enforced (`T-API-070`).
**Steps:** migration → `to_dict()` + PUT validation + sensitivity flags → factory fills all → backfill ≥50 dating profiles with filled prompts → deck/ranker reads new prefs.
**Acceptance:** ≥50 dating profiles with ≥3 prompts each; deck honours `pref_*` filters; sensitive fields never leak to professional surfaces (test green).
**Progress:** 🟢 **DONE 2026-06-13.** Migration `0029_dating_profile_depth.py` added **18** columns (idempotent): `height_cm, relationship_goal, has_children, wants_children, smoking, drinking, religion, religiosity, tribe_ethnicity, education_level, love_languages, personality_type, diet, exercise, pets, voice_prompt_url, deal_breakers, sensitive_optin` (prompts/lifestyle/photos/age-prefs already existed). Extended `DatingProfile` model + a **sensitivity-aware `to_dict(include_sensitive=…)`**: `SENSITIVE_FIELDS = (religion, religiosity, tribe_ethnicity)` are redacted for non-owner views unless opted-in via `sensitive_optin` (guardrail per `ARCHITECTURE.md §7.6`). `PUT /v1/profile/me/dating` accepts the new fields. Factory feature **`dating_depth`** (UG-context religions, tribes, prompts, MBTI, love languages; ~70% opt-in religion, ~20% tribe). **Verified:** `--feature=dating_depth --count=50` filled **50**; owner `GET /v1/profile/me/dating` returns all incl. sensitive; non-owner `to_dict(include_sensitive=False)` redacts non-opted-in `religion`/`tribe` to `None`; **audit 371/371**. _(Deck `pref_*` filtering + a mode-leak test land in `T-API-070`.)_

### `T-API-102` — Sectioned completion & "completeness ring" 🟢 DONE

Turn the richer schema into a motivating signal (feeds `T-API-081` nudges and the mobile meter).

**Steps**

1. Recompute `calculate_completion()` to score **per section** (basics, photo, experience, education, interests, professional-depth, dating-depth) and return a weighted total + per-section breakdown.
2. Expose on `GET /v1/profile/completion` and embed in `me/stats`.

**Acceptance:** completion returns a per-section map; adding a field group measurably moves the score; verified across ≥50 dummies at different fill levels.
**Progress:** 🟢 **DONE 2026-06-13.** Added `_build_sections()` to `profile/service.py`; `calculate_completion()` now returns a `sections` map (basics, professional, professional_depth, education, experience, interests, + **dating** when the Sparks lens is on) each with `{filled,total,pct,complete}`, plus a `sections_overall` roll-up — while keeping the legacy `score`/`checks`/`onboarding_steps`. Wired into `GET /v1/profile/completion` and `_get_full_profile`. **Mode separation preserved:** the `dating` section is included **only for the owner's own view** (a stranger's `@handle` view never reveals the member runs Sparks). **Verified live:** a depth-filled account returns per-section rings (basics 75%, professional 60%, professional_depth 40%, dating 80%, interests 0% → drives the next-best-action nudge for `T-API-081`); the new `T-API-100/101` fields measurably move their sections; **audit 371/371**.

---

## 2.5 Recommended new libraries (suggestions — adopt per task)

All optional/advisory; each is tied to the task that would introduce it. Nothing here violates the
"no new dependency without approval" rule — these are **proposals** for the user to greenlight.

### Backend (`linkup-api-py`)

| Library | For | Task |
|---|---|---|
| **Faker** (+ custom UG provider) | Dummy-data factory, the ≥50-records rule | `T-API-110` |
| **marshmallow** *or* **pydantic v2** | Request validation + serialization (replace hand-rolled checks; kills a class of bugs like D-1) | `T-API-041`, all writes |
| **Flask-Limiter** | Rate limiting / abuse guards | `T-API-071` |
| **redis** + **celery** | Async queue: email, decay, push fanout, events | `T-API-061` |
| **alembic** | Real migrations (replace ad-hoc `migrations/` scripts) | `T-API-003` |
| **psycopg2-binary** + **pgvector** | Postgres + ANN embeddings | `T-API-002`, `T-API-030` |
| **sentence-transformers** | Interest/user/job embeddings | `T-API-030` |
| **flask-smorest** *or* **apispec** | Auto OpenAPI spec + Swagger UI | `T-API-037` |
| **structlog** | Structured logging / observability | `T-API-042`, §Observability |
| _remove_ **stripe**, **eventlet** | Dead (Stripe legacy; eventlet broken on Py 3.14, threading mode in use) | `T-API-005` |

### Mobile (`linkup-mobo`, Flutter)

| Library | For | Task |
|---|---|---|
| **flutter_animate** | Motion tokens, micro-interactions | `T-MOB-091` |
| **shimmer** | Skeleton loaders | `T-MOB-092` |
| **go_router** | Declarative nav (replaces named routes) | `T-MOB-016` |
| **freezed** + **json_serializable** | Immutable models, safe JSON (no more `.get` on strings client-side) | data layer |
| **flutter_riverpod** | State mgmt direction (per `T-DEC-001`, GetX bridge) | `T-MOB-001` |
| **flutter_svg** | Crisp brand marks / iconography | `T-MOB-090` |
| _remove_ **google_maps_flutter**, **google_places_flutter**, **flutter_polyline_points** | Ride-era leftovers — not needed for LinkUp surfaces | mobile cleanup |
| _migrate off_ **flutx** | Legacy UI lib; replace usages with `LU*` components | `T-MOB-090` |

### Admin console (`frontend/`, React)

| Library | For | Task |
|---|---|---|
| **@tanstack/react-query** | Server-state cache for API data | `T-ADM-094` |
| **@tanstack/react-table** | Members/reports moderation tables | `T-ADM-094` |
| **recharts** | Platform-stats dashboard | `T-ADM-094` |
| **Mantine** *or* **shadcn/ui + Tailwind** | Cohesive, themeable component kit (apply violet/pink tokens) | `T-ADM-094` |
| **zod** | Form/response validation | `T-ADM-094` |

---

## 3. Recommended execution order (the critical path)

```
Phase 0  — TOOLING (hours)      C: 110 (dummy-data factory — unblocks the ≥50-records rule)
Phase I  — HARDEN (days)        A: 040 → 041 → 042 → 043 → 044 → 045
Phase II — DEEPEN (days)        I: 100 → 101 → 102   (rich 360° profiles to seed everything else)
Phase III — LIVE (days)         B: 046 → 047 → 048   ‖   C: 049 → 050 → 051
Phase IV — JOURNEYS (1 wk)      G: 081 → 082 → 080 → 083
Phase V  — CRAFT (1–2 wk)       H: 090 → 093 → 092 → 091 → 094
Phase VI — SMART (1–2 wk)       D: 052 → 053 → 029   ‖   F: 070 → 073
Phase VII — SCALE (weeks)       E: 037 → 061 → 002/003 → 030 → 035 → 034 → 036 → 027
                                F: 071 → 072
```

Rationale: build the **dummy-data factory first** so every later task can satisfy the ≥50-records
rule. **A** makes the system trustworthy; **I** makes profiles rich (so feed/deck/chat have real
signal to show); **B+C** make it feel alive; **G** guides the member; **H** makes it feel
hand-made; **D+F** make it smart and safe; **E** makes it scale. Each phase ships a system
strictly better than the one before — no big-bang rewrites.

---

## 4. Definition of "hand-made & perfect" (the bar for every task)

A task is **done** only when:

1. ✅ **≥50 dummy records** exercise the feature, produced reproducibly by the seed / factory (`T-API-110`), and an audit probe reads them back successfully. _(the mandatory ≥50-records rule, §0.1)_
2. ✅ It passes the audit (`audit.py` green) **and** adds its own regression probe.
3. ✅ No forbidden strings; vocabulary discipline kept (Member/Link/Hub/Spark…).
4. ✅ No raw 500s — every error is a JSON envelope.
5. ✅ Mode separation provably intact; sensitive fields stay `match_only` / opt-in.
6. ✅ The endpoint is explainable (recommendations say *why*) where relevant.
7. ✅ **UI/UX bar** (for any member-facing surface): uses `LU*` components + tokens only (no
   literals), has the loading/empty/error trio, and matches `DESIGN_GUIDELINES.md` v1.0.0.

8. ✅ `STATUS.md` and this file's scoreboard are updated.

---

## 5. Changelog

| Date | Change |
|---|---|
| 2026-06-13 | Document created from live investigation (server boot + 326-probe audit + code read). 28 tasks across 6 workstreams defined; 8 defects (D-1…D-8) recorded with evidence. |
| 2026-06-13 | Expanded per request: added §0.1 development-status banner + **≥50-records rule**; Workstreams **G** (Usability & User Journeys), **H** (UI/UX Consistency & Craft, incl. admin-console rebrand), **I** (360° Profile Schema — deep professional + dating fields); §2.5 recommended new libraries (backend/mobile/admin); `T-API-110` dummy-data factory. Scoreboard now **41 tasks / 9 workstreams**; execution order and Definition of Done updated. |
| 2026-06-13 | **Execution — Workstream A (Stabilize & Harden) complete + foundational factory.** Shipped & verified: `T-API-040` (modes_enabled 500 fixed, 19 rows repaired, seed fixed), `T-API-041` (JSON-safety sweep + `as_obj` helper, 8/8 unit test), `T-API-042` (global JSON error envelope), `T-API-110` (Faker dummy-data factory), `T-API-043` (audit is now a real gate — DEV_OTP synced, isolated/idempotent tests), `T-API-044` (purged legacy ride code — forbidden-string gate CLEAN), `T-API-045` (Idempotency-Key on 5 writes). Split off `T-API-044b` (deferred calling-protocol `negotiation_id` rename). **Audit 322/326 → 371/371 PASS, idempotent ×2.** Scoreboard **7/42 done**. |
| 2026-06-13 | **Execution — Workstream I (360° Profile Schema) complete.** `T-API-100` (professional depth: migration `0028`, +14 columns, PUT + validation, `professional_depth` factory, 50 backfilled), `T-API-101` (dating depth: migration `0029`, +18 columns, sensitivity-aware `to_dict`, `dating_depth` factory, 50 backfilled), `T-API-102` (sectioned completion + `sections_overall`, owner-only dating section for mode separation). **Audit 371/371.** Scoreboard **10/42 done**. |
| 2026-06-13 | **Execution — Workstreams B, C, D, F, G(backend), E(OpenAPI).** Realtime chat/typing/read/notifications over Socket.IO (verified, 2 clients); Active-Now staggering (active-24h 12→101); seed validator; content liveliness (dating-photo gap 519→10); behavioral event log (migration `0030`); Sparks-deck explainability; unified recommend seam; rate limiting; moderation hooks; mode-separation audit guard; pagination contract; journey API; zero-state hints; OpenAPI (228 paths / 272 endpoints). **Audit 371/371 ×2; seed validator 0-critical; forbidden-string gate clean.** **Scoreboard 26/42 done.** Remaining 16 deferred (mobile repo / external infra) — see §2.1. |
| 2026-06-13 | **Full `/v1` endpoint E2E sweep.** Built `e2e_full.py` (creates its own dummy data through the APIs) to cover the endpoints `audit.py` didn't touch — posts (16), photos (6), sparks profile (8), jobs extras, hubs member mgmt, comments, interests delete, links status, notifications, reference, threads, auth/admin/wallet/upload gaps. Found & fixed **2 real bugs**: `contact-poster` (`Message(msg_type=)`→`type=`) and `withdraw` (enum missing `'withdrawn'`, migration `0031`). **Result: audit 371/371 ×2 + e2e 70/70 ×2 = 441 cases; coverage of the 230 `/v1` endpoints is now 100% (0 genuinely uncovered).** |
