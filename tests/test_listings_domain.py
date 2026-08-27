"""
Phase 1-2 tests for the listings (discovery-only) domain.

Covers: idempotent discovery upserts, the unavailable-source guard, the
DB-level uniqueness guarantee (not just app-level), pagination, and admin
authorization on the /v1/admin/listings/* routes. See
PROFILE_CLAIM_IMPORTER_PLAN.md for the design this verifies against.
"""
import unittest
import uuid

from flask_jwt_extended import create_access_token

from backend.app import create_app
from backend.models import db
from backend.domains.identity.models import Account
from backend.domains.listings.models import SourceListing, SourceCrawl
from backend.domains.listings.adapters.base import DiscoveredListing
from backend.domains.listings.service import ListingService


class ListingsDiscoveryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def setUp(self):
        self.created_listing_ids = []

    def tearDown(self):
        if self.created_listing_ids:
            SourceListing.query.filter(
                SourceListing.id.in_(self.created_listing_ids)
            ).delete(synchronize_session=False)
            db.session.commit()

    def _discovered(self, external_id, location_text='Kampala'):
        return DiscoveredListing(
            external_id=external_id,
            source_url=f'https://www.eurogirlsescort.com/escort/{external_id}/',
            canonical_url=f'https://www.eurogirlsescort.com/escort/{external_id}/',
            location_text=location_text,
        )

    def test_record_discovered_creates_new_row(self):
        external_id = f'test-{uuid.uuid4().hex[:8]}'
        row, created = ListingService.record_discovered('eurogirlsescort', self._discovered(external_id))
        self.created_listing_ids.append(row.id)

        self.assertTrue(created)
        self.assertEqual(row.claim_status, 'discovered')
        self.assertEqual(row.parser_version, 'eurogirlsescort-v1')
        # Discovery must never persist identifying content — assert the
        # model has nowhere to put it, not just that we didn't set it.
        self.assertFalse(hasattr(row, 'display_name'))
        self.assertFalse(hasattr(row, 'bio'))
        self.assertFalse(hasattr(row, 'photo_url'))

    def test_record_discovered_is_idempotent(self):
        external_id = f'test-{uuid.uuid4().hex[:8]}'
        row1, created1 = ListingService.record_discovered('eurogirlsescort', self._discovered(external_id))
        self.created_listing_ids.append(row1.id)
        row2, created2 = ListingService.record_discovered('eurogirlsescort', self._discovered(external_id))

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(row1.id, row2.id)

        count = SourceListing.query.filter_by(source='eurogirlsescort', external_id=external_id).count()
        self.assertEqual(count, 1)

        # Re-discovery bumps last_checked_at rather than touching anything else.
        self.assertIsNotNone(row2.last_checked_at)

    def test_repeated_crawl_ten_times_produces_one_row(self):
        external_id = f'test-{uuid.uuid4().hex[:8]}'
        last_row = None
        for _ in range(10):
            last_row, _ = ListingService.record_discovered('eurogirlsescort', self._discovered(external_id))
        self.created_listing_ids.append(last_row.id)

        count = SourceListing.query.filter_by(source='eurogirlsescort', external_id=external_id).count()
        self.assertEqual(count, 1)

    def test_unavailable_source_is_rejected(self):
        external_id = f'test-{uuid.uuid4().hex[:8]}'
        with self.assertRaises(ValueError):
            ListingService.record_discovered('ugandahotgirls', self._discovered(external_id))

        count = SourceListing.query.filter_by(source='ugandahotgirls', external_id=external_id).count()
        self.assertEqual(count, 0)

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError):
            ListingService.record_discovered('not_a_real_source', self._discovered('x'))

    def test_db_level_unique_constraint_blocks_duplicate_insert(self):
        """Proves the guarantee lives at the DB layer, not just in service.py —
        a raw duplicate INSERT (bypassing record_discovered's upsert check
        entirely) must still fail and must not corrupt the session."""
        external_id = f'test-{uuid.uuid4().hex[:8]}'
        row1 = SourceListing(
            source='eurogirlsescort', external_id=external_id,
            source_url='https://example.com/a', canonical_url='https://example.com/a',
            claim_status='discovered', parser_version='eurogirlsescort-v1',
        )
        db.session.add(row1)
        db.session.commit()
        self.created_listing_ids.append(row1.id)

        row2 = SourceListing(
            source='eurogirlsescort', external_id=external_id,
            source_url='https://example.com/b', canonical_url='https://example.com/b',
            claim_status='discovered', parser_version='eurogirlsescort-v1',
        )
        db.session.add(row2)
        with self.assertRaises(Exception):
            db.session.commit()
        db.session.rollback()

        count = SourceListing.query.filter_by(source='eurogirlsescort', external_id=external_id).count()
        self.assertEqual(count, 1)

    def test_list_sources_reports_both_configured_sources(self):
        sources = {s['source']: s for s in ListingService.list_sources()}
        self.assertIn('eurogirlsescort', sources)
        self.assertIn('ugandahotgirls', sources)
        self.assertEqual(sources['eurogirlsescort']['status'], 'discovery_only')
        self.assertEqual(sources['ugandahotgirls']['status'], 'unavailable')

    def test_list_discovered_pagination_and_filters(self):
        ids = []
        for i in range(3):
            row, _ = ListingService.record_discovered(
                'eurogirlsescort', self._discovered(f'page-test-{uuid.uuid4().hex[:8]}')
            )
            ids.append(row.id)
        self.created_listing_ids.extend(ids)

        items, total, page, last_page, per_page = ListingService.list_discovered(
            source='eurogirlsescort', page=1, per_page=2,
        )
        self.assertGreaterEqual(total, 3)
        self.assertEqual(len(items), 2)
        self.assertEqual(page, 1)

        items_empty, total_empty, *_ = ListingService.list_discovered(claim_status='published')
        self.assertEqual(total_empty, 0)
        self.assertEqual(items_empty, [])


class ListingsAdminRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def setUp(self):
        suffix = uuid.uuid4().hex[:8]
        self.admin = Account(handle=f'test_admin_{suffix}', display_name='Test Admin', is_admin=1)
        self.plain_user = Account(handle=f'test_user_{suffix}', display_name='Test User', is_admin=0)
        db.session.add_all([self.admin, self.plain_user])
        db.session.commit()

        self.admin_headers = {
            'Authorization': f'Bearer {create_access_token(identity=self.admin.id)}'
        }
        self.plain_headers = {
            'Authorization': f'Bearer {create_access_token(identity=self.plain_user.id)}'
        }

    def tearDown(self):
        Account.query.filter(Account.id.in_([self.admin.id, self.plain_user.id])).delete(
            synchronize_session=False
        )
        db.session.commit()

    def test_sources_endpoint_requires_authentication(self):
        resp = self.client.get('/v1/admin/listings/sources')
        self.assertEqual(resp.status_code, 401)

    def test_sources_endpoint_rejects_non_admin(self):
        resp = self.client.get('/v1/admin/listings/sources', headers=self.plain_headers)
        self.assertEqual(resp.status_code, 403)

    def test_sources_endpoint_allows_admin(self):
        resp = self.client.get('/v1/admin/listings/sources', headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        sources = {s['source'] for s in resp.get_json()['data']}
        self.assertIn('eurogirlsescort', sources)
        self.assertIn('ugandahotgirls', sources)

    def test_discovered_endpoint_allows_admin(self):
        resp = self.client.get('/v1/admin/listings/discovered', headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('data', resp.get_json())


if __name__ == '__main__':
    unittest.main()
