"""
Listings domain service layer.

Phase 1-2 scope only: discovery-stage read/write helpers and the static
source registry. Claim, verification, and import logic (Phase 4+) is not
implemented yet — see PROFILE_CLAIM_IMPORTER_PLAN.md.
"""
from __future__ import annotations

import logging
from datetime import datetime

from backend.models import db
from backend.domains.listings.models import SourceListing, SourceCrawl

logger = logging.getLogger(__name__)


# Static registry of configured sources. `status` gates whether a source may
# be crawled at all — set here at the config level, not inferred at crawl
# time, so a source can be paused/disabled without touching adapter code.
#
#   discovery_only  — adapter may run discover_listings() only (current cap
#                      for every source until the plan's §0.1 legal/policy
#                      gate is explicitly cleared).
#   active          — full pipeline permitted (claim flow enabled).
#   paused_health   — auto-disabled by parser-health monitoring (Phase 13).
#   unavailable     — must not be crawled at all; adapter must not be built
#                      or invoked while a source is in this state.
SOURCE_REGISTRY = {
    'eurogirlsescort': {
        'label': 'EuroGirlsEscort (Uganda)',
        'base_url': 'https://www.eurogirlsescort.com/escorts/uganda/',
        'mechanism': 'pagination',
        'status': 'unavailable',
        'parser_version': None,
        'crawl_delay_seconds': None,
        # Surfaced in the admin UI so "unavailable" isn't a dead end — see
        # plan §0.1 / Phase 3 for the full record.
        'notes': (
            "robots.txt itself is permissive (Crawl-delay: 5, no Disallow), but "
            "the site sits behind Cloudflare and returned an explicit \"Sorry, "
            "you have been blocked\" challenge page (HTTP 403) to a single, "
            "honestly self-identifying request (checked 2026-08-27). Do not "
            "retry with a different User-Agent, headless browser, or any other "
            "technique to get past it — pursue legitimate access instead."
        ),
    },
    'ugandahotgirls': {
        'label': 'UgandaHotGirls',
        'base_url': 'https://www.ugandahotgirls.com/',
        'mechanism': 'ajax',
        'status': 'unavailable',
        'parser_version': None,
        'crawl_delay_seconds': None,
        'notes': (
            "robots.txt fetch reset the connection on two separate attempts "
            "(2026-08-27) — reads as active bot-detection. Needs an independent "
            "human recheck before this can be revisited."
        ),
    },
}


class ListingService:
    """Read/write helpers for the discovery-stage tables. No claim,
    verification, or import logic lives here yet (Phase 4+)."""

    @staticmethod
    def list_sources() -> list[dict]:
        """Configured source registry merged with live discovery/crawl stats."""
        result = []
        for key, cfg in SOURCE_REGISTRY.items():
            last_crawl = (
                SourceCrawl.query
                .filter_by(source=key)
                .order_by(SourceCrawl.started_at.desc())
                .first()
            )
            result.append({
                'source': key,
                **cfg,
                'total_discovered': SourceListing.query.filter_by(source=key).count(),
                'last_crawl': last_crawl.to_dict() if last_crawl else None,
            })
        return result

    @staticmethod
    def list_discovered(source: str | None = None, claim_status: str | None = None,
                         page: int = 1, per_page: int = 20):
        """Paginated view over lu_source_listings, admin-only consumer."""
        from backend.shared.utils.pagination import paginate_query

        query = SourceListing.query
        if source:
            query = query.filter_by(source=source)
        if claim_status:
            query = query.filter_by(claim_status=claim_status)
        query = query.order_by(SourceListing.discovered_at.desc())

        items, total, current_page, last_page, per_page = paginate_query(query, page, per_page)
        return [i.to_dict(include_source_url=True) for i in items], total, current_page, last_page, per_page

    @staticmethod
    def record_discovered(source: str, listing) -> tuple[SourceListing, bool]:
        """
        Upsert one discovered listing stub. Returns (row, created).

        `listing` is a DiscoveredListing (see adapters/base.py) — duck-typed
        here rather than imported, to keep this module import-order-safe
        with respect to the adapters package.

        Idempotent by design: re-running discovery against an unchanged
        source must never create duplicate rows. The real guarantee is the
        DB-level UNIQUE KEY on (source, external_id) — this method's
        select-then-insert is just the common-case fast path; on a race
        (two concurrent crawls discovering the same listing) the unique
        constraint violation is caught and treated as "already exists",
        never as a hard failure.
        """
        cfg = SOURCE_REGISTRY.get(source)
        if cfg is None:
            raise ValueError(f"Unknown source '{source}' — not in SOURCE_REGISTRY.")
        if cfg['status'] == 'unavailable':
            raise ValueError(
                f"Source '{source}' is marked unavailable and must not be crawled "
                f"(see PROFILE_CLAIM_IMPORTER_PLAN.md §0.1)."
            )

        existing = SourceListing.query.filter_by(
            source=source, external_id=listing.external_id
        ).first()
        if existing:
            existing.last_checked_at = datetime.utcnow()
            db.session.commit()
            return existing, False

        row = SourceListing(
            source=source,
            external_id=listing.external_id,
            source_url=listing.source_url,
            canonical_url=listing.canonical_url,
            location_text=listing.location_text,
            claim_status='discovered',
            parser_version=cfg['parser_version'],
        )
        db.session.add(row)
        try:
            db.session.commit()
        except Exception:
            # Unique-constraint race: another concurrent crawl inserted the
            # same (source, external_id) between our SELECT and this INSERT.
            db.session.rollback()
            existing = SourceListing.query.filter_by(
                source=source, external_id=listing.external_id
            ).first()
            if existing:
                logger.info(
                    f"[Listings] race on discovery upsert source={source} "
                    f"external_id={listing.external_id} — resolved to existing row."
                )
                return existing, False
            raise

        logger.info(f"[Listings] discovered new listing source={source} external_id={listing.external_id}")
        return row, True
