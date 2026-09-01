"""
Migration 0038: lu_source_listings + lu_source_crawls — discovery-only stage
of the claim-and-verify profile importer (see PROFILE_CLAIM_IMPORTER_PLAN.md).

lu_source_listings stores the bare minimum needed to point a future claim
flow at a public listing: source, external id, URL, coarse location, and
claim status. It deliberately has NO columns for name, age, bio, phone,
photos, or video — those only get collected post-authorization, in tables
that don't exist yet (Phase 5+). That's a hard architectural boundary: a
crawler cannot leak identifying content into this table even by mistake,
because there is nowhere to put it.

lu_source_crawls is the per-run audit log a scheduled/manual crawl writes to.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_source_listings` (
                `id`                VARCHAR(36)   NOT NULL,
                `source`            VARCHAR(50)   NOT NULL,
                `external_id`       VARCHAR(200)  NOT NULL,
                `source_url`        VARCHAR(1000) NOT NULL,
                `canonical_url`     VARCHAR(1000) NOT NULL,
                `location_text`     VARCHAR(200)  DEFAULT NULL,
                `discovered_at`     DATETIME      NOT NULL,
                `last_checked_at`   DATETIME      DEFAULT NULL,
                `claim_status`      VARCHAR(30)   NOT NULL DEFAULT 'discovered',
                `parser_version`    VARCHAR(50)   DEFAULT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_source_external` (`source`, `external_id`),
                KEY `idx_listing_claim_status` (`claim_status`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_source_crawls` (
                `id`                VARCHAR(36)  NOT NULL,
                `source`            VARCHAR(50)  NOT NULL,
                `started_at`        DATETIME     NOT NULL,
                `completed_at`      DATETIME     DEFAULT NULL,
                `pages_visited`     INT          NOT NULL DEFAULT 0,
                `listings_found`    INT          NOT NULL DEFAULT 0,
                `listings_new`      INT          NOT NULL DEFAULT 0,
                `errors`            INT          NOT NULL DEFAULT 0,
                `status`            VARCHAR(20)  NOT NULL DEFAULT 'running',
                `error_detail`      TEXT         DEFAULT NULL,
                PRIMARY KEY (`id`),
                KEY `idx_crawl_source` (`source`),
                KEY `idx_crawl_status` (`status`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `lu_source_crawls`")
        cur.execute("DROP TABLE IF EXISTS `lu_source_listings`")
    conn.commit()
