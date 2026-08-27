"""
Migration 0039: lu_listing_claims + lu_claim_verification_events — claim and
two-factor verification stage of the profile importer (Phase 4-6 of
PROFILE_CLAIM_IMPORTER_PLAN.md).

Two independent verification events (otp + liveness_match) are required
before a claim can be authorized — enforced in application code
(ListingClaimService._try_authorize), not just by convention. `authorized_at`
has no default and no code path sets it directly from an admin action; it is
only ever written after both events exist. This migration just provides the
tables that invariant is checked against.

`liveness_capture_path` stores the claimant's own in-app camera capture (not
scraped content — the person uploads this themselves as part of proving they
are who they say they are), used for a manual admin visual comparison in v1
until an automated face-match provider is introduced.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_listing_claims` (
                `id`                     VARCHAR(36)  NOT NULL,
                `source_listing_id`      VARCHAR(36)  NOT NULL,
                `claimant_phone`         VARCHAR(30)  DEFAULT NULL,
                `claimant_account_id`    VARCHAR(36)  DEFAULT NULL,
                `status`                 VARCHAR(30)  NOT NULL DEFAULT 'claim_requested',
                `liveness_capture_path`  VARCHAR(500) DEFAULT NULL,
                `liveness_reviewed_by`   VARCHAR(36)  DEFAULT NULL,
                `authorized_at`          DATETIME     DEFAULT NULL,
                `authorization_event_id` VARCHAR(36)  DEFAULT NULL,
                `rejected_reason`        VARCHAR(200) DEFAULT NULL,
                `created_at`             DATETIME     NOT NULL,
                `updated_at`             DATETIME     NOT NULL,
                PRIMARY KEY (`id`),
                KEY `idx_claim_listing` (`source_listing_id`),
                KEY `idx_claim_status` (`status`),
                CONSTRAINT `fk_claim_listing` FOREIGN KEY (`source_listing_id`)
                    REFERENCES `lu_source_listings`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_claim_verification_events` (
                `id`          VARCHAR(36)  NOT NULL,
                `claim_id`    VARCHAR(36)  NOT NULL,
                `method`      VARCHAR(30)  NOT NULL,
                `result`      VARCHAR(20)  NOT NULL,
                `confidence`  DECIMAL(5,2) DEFAULT NULL,
                `notes`       VARCHAR(500) DEFAULT NULL,
                `created_at`  DATETIME     NOT NULL,
                PRIMARY KEY (`id`),
                KEY `idx_verif_claim` (`claim_id`),
                CONSTRAINT `fk_verif_claim` FOREIGN KEY (`claim_id`)
                    REFERENCES `lu_listing_claims`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `lu_claim_verification_events`")
        cur.execute("DROP TABLE IF EXISTS `lu_listing_claims`")
    conn.commit()
