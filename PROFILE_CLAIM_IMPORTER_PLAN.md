# Profile Claim & Import System — Implementation Plan

## Progress Log

**Phase 1 (Architecture) + Phase 2 (Discovery Database) — DONE, verified locally (2026-08-27).**

Built:
- `backend/database/migrations/0038_listing_discovery.py` — `lu_source_listings` +
  `lu_source_crawls`. Applied locally via `migrate.py migrate`; local DB confirmed
  to have had zero pre-existing tables of these names before this migration
  (checked directly against the DB, not just against migration file history).
- `backend/domains/listings/{models,service,routes}.py`, `adapters/{__init__,base}.py`.
- Wired into `backend/models/__init__.py` (model registration) and `backend/app.py`
  (`listings_bp` registered at `/v1/admin/listings`).
- `tests/test_listings_domain.py` — 12 tests, all passing against the real local
  MySQL DB (not mocked): idempotent discovery upsert, DB-level unique-constraint
  enforcement (not just app-level), the `unavailable`-source guard, unknown-source
  rejection, pagination/filters, and admin-route auth (401/403/200 paths).
- Ran the pre-existing test suite (`tests/test_enforcement_regression.py`) as a
  regression check — it fails, but on a pre-existing, unrelated cause (missing
  `backend.models.negotiation`, fallout from this branch's in-progress ride-backend
  deletion, confirmed via `git diff` to be untouched by this work).

Deviations from the original file-layout sketch in §1.1, made to match this repo's
actual conventions (found by inspecting the codebase before writing code, not
assumed):
- Tests live in the existing root-level `tests/` directory using `unittest.TestCase`
  against a real DB, matching `tests/test_enforcement_regression.py` — not a
  `backend/domains/listings/tests/` subfolder.
- No `tasks.py` / `sources/eurogirlsescort/` adapter yet — out of scope per your
  instruction to stop after Phase 1–2.
- Added one guard not in the original spec text: `ListingService.record_discovered()`
  refuses to write any row for a source whose registry `status` is `'unavailable'`
  (raises `ValueError`). This makes the §0.1 gate for `ugandahotgirls` enforced in
  code, not just in the source-adapter that hasn't been written yet — verified by
  `test_unavailable_source_is_rejected`.

**Not yet deployed to the production server** — see the "Deployment" note added
below the rollout sequence (§15A). Local-only so far.

**Next**: Phase 3 (eurogirlsescort discovery adapter) — blocked on your go-ahead,
and `ugandahotgirls`'s adapter stays blocked on the §0.1 accessibility re-check.

---

## 0. What this system is (and isn't)

This is **not** a scraper that copies third-party profiles into LinkUp. It is a
**claim-and-verify** system:

1. A crawler discovers that a public listing *exists* on a source site and stores
   the bare minimum needed to point someone at it (source, URL, rough location).
   No photos, videos, bio, or contact details are stored at this stage.
2. The person the listing is about can find that listing inside LinkUp and start
   a claim.
3. They prove control of the listing via OTP **and** a liveness-selfie match
   against the photos they're claiming — not by an admin clicking approve.
4. Only after that verification succeeds does the system fetch the actual
   content (photos, bio, videos) from the source, and it lands in a staging area
   that the verified person edits before anything is public.
5. They own the resulting account from that point: edit, remove media, delete,
   or request takedown at any time.

An admin can never move a claim from `verification_pending` to `authorized`.
That transition only happens through the verification event itself. Admins can
approve/reject *publication* of already-authorized content — a data-quality
gate, not a consent gate.

## 0.1 Preconditions before any source goes live

These are gates, not tasks — Phase 4+ adapters must not be enabled for real
users until each is explicitly signed off:

- [ ] **Legal review (Uganda-specific).** Both initial sources advertise
  commercial sexual services. Even with individual consent captured via the
  claim flow, importing that content into a mainstream dating product may carry
  advertising/facilitation exposure under Ugandan law. Get counsel sign-off
  before Phase 4 adapters process real listings, not just before publication.
- [ ] **Platform/store policy review.** LinkUp's own data model
  (`backend/domains/reference/dating_options.py`) is a general dating app.
  Google Play and Apple App Store policies restrict content that facilitates
  prostitution/escort services. Confirm this feature fits LinkUp's content
  policy and won't trigger store takedown before enabling it for real users.
- [ ] **Per-source robots.txt / ToS check**, re-verified at adapter-enable time,
  not just at design time (sites change their policy).
  - `eurogirlsescort.com`: `robots.txt` = `User-agent: * / Crawl-delay: 5` as of
    2026-08-27. No disallowed paths found — discovery-level crawling is
    permitted at a 5s+ delay.
  - `ugandahotgirls.com`: `robots.txt` fetch reset the connection twice (2026-08-27).
    This reads as active bot-detection. Per the no-circumvention rule, this
    source starts in `status=unavailable` — do **not** reach for browser
    automation to work around it. Re-check manually before building its
    adapter; if it's genuinely inaccessible to a well-behaved client, it stays
    disabled.

---

## Phase 1 — Architecture

### 1.1 New domain: `backend/domains/listings/`

```
backend/domains/listings/
    __init__.py
    models.py              # SourceListing, ListingClaim, ClaimVerificationEvent,
                            # ListingImportBatch, ListingMedia, ListingTakedown
    service.py              # ListingService — claim/verification/import orchestration
    routes.py                # public claim endpoints + admin discovery/review endpoints
    importer.py             # post-authorization content fetch (bio/photos/videos)
    media.py                 # download/validate/hash/dedupe, wraps shared.storage
    verification.py         # OTP + liveness-selfie match orchestration
    tasks.py                 # crawl_source(), retry_failed_media(), reindex_takedowns()
    adapters/
        __init__.py
        base.py               # SourceAdapter ABC
        eurogirlsescort.py    # discovery-only adapter
        ugandahotgirls.py     # discovery-only adapter (disabled until 0.1 gate clears)
    tests/
        test_adapters.py
        test_claim_flow.py
        test_dedup.py
        test_media.py
```

Matches the existing `domains/<name>/{models,service,routes}.py` convention
(see `domains/safety`, `domains/app_version`). `is_admin`-gated endpoints reuse
the existing `_admin_required` decorator pattern from `domains/admin/routes.py`;
OTP reuses `identity/service.py`'s `create_otp`/`verify_otp` with a new
`purpose='listing_claim'`.

### 1.2 Source adapter interface (`adapters/base.py`)

```python
from abc import ABC, abstractmethod

class SourceAdapter(ABC):
    source_key: str            # 'eurogirlsescort', 'ugandahotgirls'
    parser_version: str        # 'eurogirlsescort-v1'

    @abstractmethod
    def discover_listings(self, since=None) -> list["DiscoveredListing"]:
        """Return minimal listing stubs only: source_url, canonical_url,
        external_id, rough location, discovered_at. MUST NOT fetch or return
        photos, videos, bio, or contact fields."""

    @abstractmethod
    def fetch_claimable_summary(self, listing) -> "ClaimableSummary":
        """Called when someone starts a claim on this listing. Returns just
        enough to render a 'is this you?' confirmation screen: a blurred/low-res
        thumbnail reference + rough location. Still no full content fetch."""

    @abstractmethod
    def fetch_authorized_content(self, listing) -> "SourceProfileContent":
        """Called ONLY after a claim reaches AUTHORIZED. Fetches full bio,
        photos, videos for import into staging."""
```

Three methods, not two, is a deliberate change from the original spec's
`discover/fetch/parse` split — it enforces that "fetch everything" and
"fetch just enough to confirm identity" are different capabilities that can't
be accidentally conflated in a single `fetch_profile()` call.

**Acceptance criteria:** a new source adapter can be added by implementing
these three methods and a config file; zero changes required in
`service.py`, `routes.py`, or the claim state machine.

---

## Phase 2 — Discovery Database

### 2.1 Migration `0038_listing_discovery.py`

```sql
CREATE TABLE `lu_source_listings` (
    `id`                VARCHAR(36)  NOT NULL,
    `source`            VARCHAR(50)  NOT NULL,          -- 'eurogirlsescort'
    `external_id`       VARCHAR(200) NOT NULL,           -- source's own listing id/slug
    `source_url`        VARCHAR(1000) NOT NULL,
    `canonical_url`     VARCHAR(1000) NOT NULL,
    `location_text`     VARCHAR(200) DEFAULT NULL,        -- e.g. "Kampala" — coarse only
    `discovered_at`     DATETIME NOT NULL,
    `last_checked_at`   DATETIME DEFAULT NULL,
    `claim_status`      VARCHAR(30) NOT NULL DEFAULT 'discovered',
    `parser_version`    VARCHAR(50) NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_source_external` (`source`, `external_id`),
    KEY `idx_claim_status` (`claim_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `lu_source_crawls` (
    `id`                VARCHAR(36)  NOT NULL,
    `source`            VARCHAR(50)  NOT NULL,
    `started_at`        DATETIME NOT NULL,
    `completed_at`      DATETIME DEFAULT NULL,
    `pages_visited`     INT DEFAULT 0,
    `listings_found`    INT DEFAULT 0,
    `listings_new`      INT DEFAULT 0,
    `errors`            INT DEFAULT 0,
    `status`            VARCHAR(20) NOT NULL DEFAULT 'running', -- running|completed|failed|paused_health
    `error_detail`      TEXT DEFAULT NULL,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Objective:** persist only enough to point at a listing and drive the claim
flow — deliberately excludes name, age, bio, photos, phone.
**Files:** `backend/database/migrations/0038_listing_discovery.py`,
`backend/domains/listings/models.py` (`SourceListing`, `SourceCrawl`).
**Dependencies:** none.
**Acceptance criteria:** running the discovery adapter twice against the same
source produces zero duplicate rows (enforced by the `uq_source_external`
unique constraint, not just application logic).

### 2.2 `claim_status` enum values

```
discovered → claim_available → claim_requested → verification_pending
    → verified → authorized → importing → imported → user_review
    → published
                                     ↘ rejected
                                     ↘ removal_requested → removed
```

Stored as a plain `VARCHAR` with validation in `service.py`, not a MySQL ENUM
(matches existing style, e.g. `PanicAlert.status`), so adding a state later is
a code change, not a migration.

---

## Phase 3 — Source Adapters (Discovery Only)

### 3.1 `adapters/eurogirlsescort.py`

**Objective:** implement `discover_listings()` for the paginated listing pages
under `/escorts/uganda/`.
**Implementation details:**
- `httpx` client, custom `User-Agent: LinkUpListingBot/1.0 (+contact URL)`,
  5s+ delay between requests (matches published `Crawl-delay: 5`).
- Parse listing cards for: profile URL, listing id (from URL slug), coarse
  city text. Do not follow into gallery/detail markup at this stage.
- Pagination: follow `rel="next"` / numbered page links; stop on repeat page,
  empty page, or a configurable `MAX_PAGES` safety limit.
- Prefer JSON-LD if the listing pages expose it (check at implementation
  time); fall back to semantic HTML selectors documented in `selectors.py`.

**Files:** `adapters/eurogirlsescort.py`, `adapters/eurogirlsescort_selectors.py`.
**Dependencies:** Phase 1 base class, Phase 2 tables.
**Acceptance criteria:** dry run against `/escorts/uganda/` produces a stable
count of discovered listings across two consecutive runs with no site changes,
and zero rows written outside `lu_source_listings`/`lu_source_crawls`.

### 3.2 `adapters/ugandahotgirls.py` — **blocked**

Do not implement until the Phase 0.1 robots.txt/accessibility gate clears
through a manual, non-programmatic check (e.g. a human visiting the site and
confirming there's no bot-blocking, and that request behavior is documented).
If it turns out the site actively blocks automated clients, this source stays
`status=unavailable` in the sources table permanently — that is a valid, final
outcome, not a problem to engineer around.

---

## Phase 4 — Claim System

### 4.1 "Find your listing" flow

**Objective:** let a real person locate the discovery stub about them without
LinkUp ever having shown them identifying content first.
**Implementation details:** search by source + coarse location only (never by
name/photo, since none is stored yet). Returns listing stubs with
`claim_status IN ('discovered','claim_available')`. Rate-limited per IP/session
to prevent enumeration scraping of the discovery table itself.
**Files:** `routes.py` (`GET /v1/listings/search`), `service.py`.
**Acceptance criteria:** the search response never includes `source_url`
directly to unauthenticated callers past what's needed to disambiguate (e.g.
show "Escort listing, Kampala, discovered 2026-08-10" not the raw source link)
— avoids turning this into a directory of the source site.

### 4.2 Claim request → `fetch_claimable_summary()`

Objective: once someone selects "this is me," fetch just enough (blurred
thumbnail reference, rough location) to render a confirmation screen, without
importing full content. Transition `claim_available → claim_requested`.

---

## Phase 5 — Verification System

### 5.1 Migration `0039_listing_claims.py`

```sql
CREATE TABLE `lu_listing_claims` (
    `id`                    VARCHAR(36) NOT NULL,
    `source_listing_id`     VARCHAR(36) NOT NULL,
    `claimant_phone`        VARCHAR(30) DEFAULT NULL,
    `claimant_account_id`   VARCHAR(36) DEFAULT NULL,   -- set once a LinkUp account exists
    `status`                VARCHAR(30) NOT NULL DEFAULT 'claim_requested',
    `otp_request_id`        VARCHAR(36) DEFAULT NULL,   -- FK to lu_otp_requests
    `liveness_check_id`     VARCHAR(36) DEFAULT NULL,
    `authorized_at`         DATETIME DEFAULT NULL,
    `authorization_event_id` VARCHAR(36) DEFAULT NULL,
    `rejected_reason`       VARCHAR(200) DEFAULT NULL,
    `created_at`            DATETIME NOT NULL,
    `updated_at`            DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    CONSTRAINT `fk_claim_listing` FOREIGN KEY (`source_listing_id`)
        REFERENCES `lu_source_listings`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `lu_claim_verification_events` (
    `id`                VARCHAR(36) NOT NULL,
    `claim_id`          VARCHAR(36) NOT NULL,
    `method`            VARCHAR(30) NOT NULL,   -- 'otp' | 'liveness_match'
    `result`            VARCHAR(20) NOT NULL,   -- 'passed' | 'failed'
    `confidence`        DECIMAL(5,2) DEFAULT NULL,  -- liveness_match score, null for otp
    `created_at`        DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    CONSTRAINT `fk_verif_claim` FOREIGN KEY (`claim_id`)
        REFERENCES `lu_listing_claims`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Two-factor by construction: `authorized_at` may only be set by
`ListingService._try_authorize(claim)`, which requires **both** an `otp`
`passed` event **and** a `liveness_match` `passed` event to exist for that
claim. There is no code path — admin or otherwise — that sets `authorized_at`
directly.

### 5.2 OTP factor

Reuses `identity/service.py::create_otp/verify_otp` with `purpose='listing_claim'`,
sent to the phone number the claimant enters (never auto-trusted from the
source listing itself, since — as you noted — that number may belong to an
agency). Writes a `lu_claim_verification_events` row with `method='otp'` on
success.

### 5.3 Liveness-selfie factor

**Objective:** confirm the claimant is the person in the photos being claimed,
not just someone with access to a phone number.
**Implementation details:** in-app camera capture (no gallery upload, to
resist someone submitting a saved photo) compared against the blurred
reference thumbnail from `fetch_claimable_summary()` using a face-match
service. Start with a manual admin visual check for this comparison in v1
(cheap, no new infra) with a `confidence` field left null; swap in an
automated face-match provider in v2 once volume justifies it. Either way this
writes a second `lu_claim_verification_events` row (`method='liveness_match'`).
**Acceptance criteria:** a claim with only an `otp` event and no
`liveness_match` event cannot reach `authorized` — covered by a unit test that
asserts `_try_authorize` raises/no-ops in that case.

### 5.4 Explicitly out of scope

Never implement "log into the source site to verify ownership" as a
verification method — that would mean collecting a third party's credentials
for a site LinkUp doesn't operate.

---

## Phase 6 — Authorization State Machine

Implemented as a single function, `ListingService.transition(claim, event)`,
with a hard-coded adjacency list of legal transitions (mirrors the diagram in
§2.2). Admin-facing endpoints can only call transitions tagged
`admin_allowed=True` (e.g. `imported → user_review`, `user_review → published`,
anything `→ rejected`). `verification_pending → authorized` is tagged
`system_only=True` and is unreachable from `routes.py`'s admin blueprint —
enforce this with a test that walks every admin route and asserts none can
reach a `system_only` transition.

---

## Phase 7 — Post-Authorization Import

### 7.1 `importer.py`

**Objective:** once `authorized`, fetch full content and stage it — this is
the only point where `fetch_authorized_content()` is called.
**Flow:** `authorized → importing` → adapter fetch → normalize → write to
`lu_listing_import_batches` (raw + normalized JSON, `parser_version`) →
`imported → user_review`.
**Acceptance criteria:** if the adapter throws mid-fetch, the claim rolls back
to `authorized` (not stuck in `importing`, not silently marked `imported`) so
a retry is safe and idempotent.

### 7.2 User review UI (mobile app, not admin)

The verified claimant — now creating their actual LinkUp account — sees the
imported bio/photos/videos as an editable draft: edit name/bio/attributes,
delete any photo or video, reorder gallery, pick profile photo, or discard the
whole import and start a normal blank profile instead. Nothing here is
optional-to-skip in a way that publishes without their edit pass.

---

## Phase 8 — Media Handling

### 8.1 `media.py`

Wraps `backend.shared.storage.save_upload`/`get_url` (already
R2-with-local-fallback) rather than a parallel storage path. Adds:
- Download only after `authorized` (never during discovery).
- SHA-256 checksum per file for dedup; store in `lu_listing_media`.
- Extension/MIME allow-list reusing `storage/r2.py`'s `ALLOWED_*_EXTENSIONS`,
  extended with a `ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm'}` set.
- Failed downloads recorded in `lu_listing_media_failures` (url, reason,
  http_status, attempt_count) for retry — never silently dropped.

### 8.2 Migration `0040_listing_media.py`

```sql
CREATE TABLE `lu_listing_media` (
    `id`                VARCHAR(36) NOT NULL,
    `claim_id`          VARCHAR(36) NOT NULL,
    `media_type`        VARCHAR(10) NOT NULL,   -- 'image' | 'video'
    `source_url`        VARCHAR(1000) NOT NULL,
    `local_path`        VARCHAR(500) DEFAULT NULL,
    `checksum`          VARCHAR(64) DEFAULT NULL,
    `sort_order`        INT DEFAULT 0,
    `is_profile_photo`  TINYINT(1) DEFAULT 0,
    `created_at`        DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_claim_checksum` (`claim_id`, `checksum`),
    CONSTRAINT `fk_media_claim` FOREIGN KEY (`claim_id`)
        REFERENCES `lu_listing_claims`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## Phase 9 — Deduplication

Layered, per the original spec:
1. **Source identity** — `uq_source_external (source, external_id)` on
   `lu_source_listings` (DB-level, not app-level).
2. **Content fingerprint** — normalized-text hash on imported bio, stored on
   the import batch, checked before creating a second claim path for what
   looks like the same person re-listed under a new external_id.
3. **Media checksum** — `uq_claim_checksum` above; cross-claim perceptual
   hashing (e.g. `imagehash`) as a v2 enhancement to catch the same photo
   reused across two different source listings.

**Acceptance criteria:** re-running discovery ten times against an unchanged
source produces exactly the same row count in `lu_source_listings` as running
it once.

---

## Phase 10 — Removal / Takedown

### 10.1 `lu_listing_takedowns`

```sql
CREATE TABLE `lu_listing_takedowns` (
    `id`                VARCHAR(36) NOT NULL,
    `source_listing_id` VARCHAR(36) NOT NULL,
    `reason`            VARCHAR(50) NOT NULL,  -- account_deleted|withdrawn|reported|coerced
    `requested_by`      VARCHAR(36) DEFAULT NULL,  -- account_id, null if source-initiated
    `created_at`        DATETIME NOT NULL,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

A row here permanently suppresses that `(source, external_id)` from ever being
re-discovered or re-claimed — the discovery adapter checks this table before
inserting a new `lu_source_listings` row. This also doubles as the exit for
anyone who reports they were pressured into claiming a listing (`reason =
'coerced'`): the account, its media, and the source listing itself are all
locked out from reappearing, and this reason code should route to a
human safety reviewer rather than just an automated log entry, given the
coercion/trafficking risk inherent in phone-based verification of listings
that may have been posted by a third party.

---

## Phase 11 — Admin Dashboard

Extends `domains/admin/routes.py` with a `listings` section, reusing
`_admin_required`. Three separate views, matching your requirement that
discovery/authorization/import/publication stay conceptually distinct:

- **Sources** — per-source status (`active`/`unavailable`/`paused_health`),
  last crawl, next scheduled crawl, `[Crawl Now]`, `[Pause]`, `[View Logs]`.
- **Claims** — list by `claim_status`, showing verification event history
  (read-only — no approve button that skips verification).
- **Review queue** — `user_review` and `imported` items awaiting the
  claimant's own edit pass, plus final `published` admin sign-off for data
  quality (not identity/consent, which is already settled by this stage).

---

## Phase 12 — Scheduling

No Celery/APScheduler currently in this codebase. Recommended: a
secret-token-protected endpoint (`POST /v1/admin/listings/sources/<id>/crawl`,
header `X-Cron-Secret`) triggered by the existing hosting environment's system
cron — consistent with a small Flask app on shared/managed hosting rather than
introducing a new worker/queue infrastructure. `[Crawl Now]` in the dashboard
calls the same code path synchronously for small sources or enqueues a
DB-tracked job row for larger ones.

---

## Phase 13 — Monitoring / Parser Health

Before writing `lu_source_listings` rows from a crawl, compare counts against
a trailing average for that source. If discovered listings drop by more than
(configurable) 80% versus the trailing 7-day average, or a required field is
missing on >50% of parsed stubs, mark the crawl `status='paused_health'`,
disable further scheduled crawls for that source, and leave existing data
untouched — never let a source redesign silently blank out or corrupt
existing discovery records.

---

## Phase 14 — Testing

- **Adapter tests**: fixture HTML/JSON captured from each source (checked into
  `tests/fixtures/`, not live-fetched in CI) — pagination termination,
  zero-duplicate discovery, graceful handling of a malformed listing card.
- **Claim/verification tests**: assert `authorized_at` is unreachable without
  both verification events (§5.3); assert admin routes cannot trigger
  `system_only` transitions (§6).
- **Dedup tests**: run discovery 10x against the same fixture, assert row
  count is stable.
- **Media tests**: duplicate checksum rejected; unsupported extension
  rejected; failed download recorded and retryable.
- **Recovery tests**: malformed HTML on one listing card doesn't abort the
  rest of the page; a mid-import adapter exception rolls the claim back to
  `authorized`, not a stuck `importing` state.

---

## Phase 15 — Rollout Sequence

1. Implement Phases 1–3 for `eurogirlsescort` only, discovery-only, `DRY_RUN`.
2. Manually review a sample of discovered stubs — confirm no photos/bio/contact
   fields leaked into `lu_source_listings` (a code-level guarantee, but verify
   the actual DB rows too).
3. Clear the §0.1 legal/policy preconditions.
4. Enable the claim flow (Phases 4–7) behind a feature flag, small user
   sample.
5. Only then evaluate `ugandahotgirls` or any future source, repeating
   Phase 3's structure-analysis step fresh each time — per your original
   principle, the core pipeline shouldn't need to change, only a new adapter.

---

## Definition of Done

- Discovery never persists identifying content (enforced by schema, not just
  convention — `lu_source_listings` has no columns for photos/bio/contact).
- `authorized` is unreachable without two independent verification events, and
  no admin code path can set it directly.
- Claimed accounts are fully owned by the verified user post-import (edit,
  remove media, delete, request takedown).
- Takedown/suppression prevents re-discovery of removed listings.
- A coercion report routes to human safety review, not just a log line.
- Sources that fail robots.txt/accessibility checks stay disabled rather than
  being worked around.
- Repeated crawls are idempotent at the database-constraint level.
- The §0.1 legal and platform-policy gates are explicitly signed off — not
  silently skipped — before any source moves past discovery-only.
