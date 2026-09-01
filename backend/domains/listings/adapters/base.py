"""
Source adapter interface for the profile claim-and-verify pipeline.

See PROFILE_CLAIM_IMPORTER_PLAN.md for the full design. The invariant this
interface exists to enforce: `discover_listings()` may only return minimal,
non-identifying stubs. Fetching a person's actual photos, bio, or contact
details is a *different* method (`fetch_authorized_content`) that the
pipeline is only allowed to call after a claim reaches `authorized` — no
adapter method by itself can cause identifying content to be stored, because
the core pipeline (not implemented until Phase 4-7) is what decides when
each method gets called, based on claim_status.

No concrete adapter exists yet (Phase 3). This module is the contract future
adapters implement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domains.listings.models import SourceListing


@dataclass(frozen=True)
class DiscoveredListing:
    """Minimal, non-identifying stub for one listing found during discovery.

    Deliberately has no fields for name, age, bio, photos, or contact info —
    the discovery stage must not collect any of that (plan §0.1 / §1).
    """
    external_id: str
    source_url: str
    canonical_url: str
    location_text: str | None = None


@dataclass(frozen=True)
class ClaimableSummary:
    """Just enough to render a 'is this you?' confirmation screen (plan §4.2).

    `blurred_thumbnail_ref` is a reference the frontend resolves to a heavily
    blurred/low-res preview — never the raw source image URL, and never
    persisted unless a claim later reaches `authorized`.
    """
    external_id: str
    location_text: str | None
    blurred_thumbnail_ref: str | None = None


@dataclass(frozen=True)
class SourceProfileContent:
    """Full profile content for import. Only ever requested post-authorization."""
    display_name: str | None = None
    bio: str | None = None
    attributes: dict = field(default_factory=dict)
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)


class SourceAdapter(ABC):
    """Base class every per-site adapter implements.

    The core pipeline (service.py, routes.py, tasks.py) only ever calls these
    three methods and never branches on which site it's talking to —
    pagination, AJAX, JSON-vs-HTML, and layout differences all stay inside
    the adapter. Adding a new source should never require changing this
    class or the pipeline code that calls it.
    """

    source_key: str
    parser_version: str

    @abstractmethod
    def discover_listings(self, since: datetime | None = None) -> list[DiscoveredListing]:
        """Return minimal listing stubs discovered since the given timestamp
        (or all, if None). MUST NOT fetch or return photos/bio/contact info."""
        raise NotImplementedError

    @abstractmethod
    def fetch_claimable_summary(self, listing: "SourceListing") -> ClaimableSummary:
        """Called when a user starts a claim on `listing`. Still no full
        content fetch — only enough for an identity-confirmation screen."""
        raise NotImplementedError

    @abstractmethod
    def fetch_authorized_content(self, listing: "SourceListing") -> SourceProfileContent:
        """Called ONLY after `listing.claim_status == 'authorized'`. Full
        content fetch for staging into the user's editable draft profile."""
        raise NotImplementedError
