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
from backend.domains.listings.service import ListingService, SOURCE_REGISTRY

# Both real-world sources are 'unavailable' as of 2026-08-27 (ugandahotgirls:
# robots.txt connection reset; eurogirlsescort: active Cloudflare block — see
# PROFILE_CLAIM_IMPORTER_PLAN.md §0.1/Phase 3). The upsert/dedup/pagination
# *mechanism* is independent of which real sources currently pass the
# accessibility gate, so these tests exercise it against a registered fixture
# source rather than asserting a real source is reachable when it isn't.
FIXTURE_SOURCE = 'test_fixture_source'


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
        SOURCE_REGISTRY[FIXTURE_SOURCE] = {
            'label': 'Fixture Source (tests only)',
            'base_url': 'https://example.com/',
            'mechanism': 'pagination',
            'status': 'discovery_only',
            'parser_version': 'test_fixture_source-v1',
            'crawl_delay_seconds': 0,
        }

    def tearDown(self):
        SOURCE_REGISTRY.pop(FIXTURE_SOURCE, None)
        if self.created_listing_ids:
            SourceListing.query.filter(
                SourceListing.id.in_(self.created_listing_ids)
            ).delete(synchronize_session=False)
            db.session.commit()

    def _discovered(self, external_id, location_text='Kampala'):
        return DiscoveredListing(
            external_id=external_id,
            source_url=f'https://example.com/listing/{external_id}/',
            canonical_url=f'https://example.com/listing/{external_id}/',
            location_text=location_text,
        )

    def test_record_discovered_creates_new_row(self):
        external_id = f'test-{uuid.uuid4().hex[:8]}'
        row, created = ListingService.record_discovered(FIXTURE_SOURCE, self._discovered(external_id))
        self.created_listing_ids.append(row.id)

        self.assertTrue(created)
        self.assertEqual(row.claim_status, 'discovered')
        self.assertEqual(row.parser_version, 'test_fixture_source-v1')
        # Discovery must never persist identifying content — assert the
        # model has nowhere to put it, not just that we didn't set it.
        self.assertFalse(hasattr(row, 'display_name'))
        self.assertFalse(hasattr(row, 'bio'))
        self.assertFalse(hasattr(row, 'photo_url'))

    def test_record_discovered_is_idempotent(self):
        external_id = f'test-{uuid.uuid4().hex[:8]}'
        row1, created1 = ListingService.record_discovered(FIXTURE_SOURCE, self._discovered(external_id))
        self.created_listing_ids.append(row1.id)
        row2, created2 = ListingService.record_discovered(FIXTURE_SOURCE, self._discovered(external_id))

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(row1.id, row2.id)

        count = SourceListing.query.filter_by(source=FIXTURE_SOURCE, external_id=external_id).count()
        self.assertEqual(count, 1)

        # Re-discovery bumps last_checked_at rather than touching anything else.
        self.assertIsNotNone(row2.last_checked_at)

    def test_repeated_crawl_ten_times_produces_one_row(self):
        external_id = f'test-{uuid.uuid4().hex[:8]}'
        last_row = None
        for _ in range(10):
            last_row, _ = ListingService.record_discovered(FIXTURE_SOURCE, self._discovered(external_id))
        self.created_listing_ids.append(last_row.id)

        count = SourceListing.query.filter_by(source=FIXTURE_SOURCE, external_id=external_id).count()
        self.assertEqual(count, 1)

    def test_unavailable_source_is_rejected(self):
        """Both real-world sources are currently unavailable — ugandahotgirls
        (robots.txt connection reset) and eurogirlsescort (active Cloudflare
        block). Confirms record_discovered refuses both, for their own
        documented reasons, not just one."""
        for source in ('ugandahotgirls', 'eurogirlsescort'):
            external_id = f'test-{uuid.uuid4().hex[:8]}'
            with self.assertRaises(ValueError):
                ListingService.record_discovered(source, self._discovered(external_id))

            count = SourceListing.query.filter_by(source=source, external_id=external_id).count()
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
            source=FIXTURE_SOURCE, external_id=external_id,
            source_url='https://example.com/a', canonical_url='https://example.com/a',
            claim_status='discovered', parser_version='test_fixture_source-v1',
        )
        db.session.add(row1)
        db.session.commit()
        self.created_listing_ids.append(row1.id)

        row2 = SourceListing(
            source=FIXTURE_SOURCE, external_id=external_id,
            source_url='https://example.com/b', canonical_url='https://example.com/b',
            claim_status='discovered', parser_version='test_fixture_source-v1',
        )
        db.session.add(row2)
        with self.assertRaises(Exception):
            db.session.commit()
        db.session.rollback()

        count = SourceListing.query.filter_by(source=FIXTURE_SOURCE, external_id=external_id).count()
        self.assertEqual(count, 1)

    def test_list_sources_reports_both_configured_sources(self):
        sources = {s['source']: s for s in ListingService.list_sources()}
        self.assertIn('eurogirlsescort', sources)
        self.assertIn('ugandahotgirls', sources)
        # Both real sources are unavailable as of 2026-08-27 — see the
        # SOURCE_REGISTRY comments in service.py for why each one is blocked.
        self.assertEqual(sources['eurogirlsescort']['status'], 'unavailable')
        self.assertEqual(sources['ugandahotgirls']['status'], 'unavailable')

    def test_list_discovered_pagination_and_filters(self):
        ids = []
        for i in range(3):
            row, _ = ListingService.record_discovered(
                FIXTURE_SOURCE, self._discovered(f'page-test-{uuid.uuid4().hex[:8]}')
            )
            ids.append(row.id)
        self.created_listing_ids.extend(ids)

        items, total, page, last_page, per_page = ListingService.list_discovered(
            source=FIXTURE_SOURCE, page=1, per_page=2,
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


# ─── Phase 4-6: claim + verification + authorization state machine ─────────

from backend.domains.listings.models import ListingClaim, ClaimVerificationEvent
from backend.domains.listings.claim_service import ListingClaimService, ClaimError, ADMIN_ALLOWED_TRANSITIONS

DEV_OTP_CODE = '111111'  # backend.domains.identity.service.DEV_OTP — fixed in dev mode, no real SMS sent.


def _fake_image(name='selfie.jpg'):
    from werkzeug.datastructures import FileStorage
    import io
    return FileStorage(stream=io.BytesIO(b'not-a-real-image-just-test-bytes'), filename=name)


class ListingClaimServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def setUp(self):
        self.listing = SourceListing(
            source='test_fixture_source',
            external_id=f'claim-test-{uuid.uuid4().hex[:8]}',
            source_url='https://example.com/listing/x',
            canonical_url='https://example.com/listing/x',
            location_text='Kampala',
            claim_status='discovered',
            parser_version='test-v1',
        )
        db.session.add(self.listing)
        db.session.commit()

    def tearDown(self):
        ClaimVerificationEvent.query.filter(
            ClaimVerificationEvent.claim_id.in_(
                db.session.query(ListingClaim.id).filter_by(source_listing_id=self.listing.id)
            )
        ).delete(synchronize_session=False)
        ListingClaim.query.filter_by(source_listing_id=self.listing.id).delete(synchronize_session=False)
        db.session.delete(self.listing)
        db.session.commit()

    def test_start_claim_creates_claim_and_syncs_listing_status(self):
        claim = ListingClaimService.start_claim(self.listing.id, '+256700000123')
        self.assertEqual(claim.status, 'claim_requested')
        db.session.refresh(self.listing)
        self.assertEqual(self.listing.claim_status, 'claim_requested')

    def test_start_claim_is_idempotent_per_listing(self):
        claim1 = ListingClaimService.start_claim(self.listing.id, '+256700000123')
        claim2 = ListingClaimService.start_claim(self.listing.id, '+256700000456')
        self.assertEqual(claim1.id, claim2.id)
        self.assertEqual(ListingClaim.query.filter_by(source_listing_id=self.listing.id).count(), 1)

    def test_start_claim_rejects_non_claimable_listing(self):
        self.listing.claim_status = 'published'
        db.session.commit()
        with self.assertRaises(ClaimError):
            ListingClaimService.start_claim(self.listing.id, '+256700000123')

    def test_start_claim_rejects_unknown_listing(self):
        with self.assertRaises(ClaimError):
            ListingClaimService.start_claim(str(uuid.uuid4()), '+256700000123')

    def test_otp_then_liveness_authorizes(self):
        claim = ListingClaimService.start_claim(self.listing.id, '+256700000123')
        ListingClaimService.request_otp(claim.id)
        ok, _ = ListingClaimService.verify_otp_step(claim.id, DEV_OTP_CODE)
        self.assertTrue(ok)
        self.assertNotEqual(claim.status, 'authorized')  # one factor only

        ListingClaimService.submit_liveness_capture(claim.id, _fake_image())
        admin = Account(handle=f'test_admin_{uuid.uuid4().hex[:8]}', display_name='Admin', is_admin=1)
        db.session.add(admin)
        db.session.commit()
        try:
            ListingClaimService.admin_review_liveness(claim.id, admin, passed=True)
            db.session.refresh(claim)
            self.assertEqual(claim.status, 'authorized')
            self.assertIsNotNone(claim.authorized_at)
            db.session.refresh(self.listing)
            self.assertEqual(self.listing.claim_status, 'authorized')
        finally:
            db.session.delete(admin)
            db.session.commit()

    def test_liveness_then_otp_authorizes_order_independent(self):
        claim = ListingClaimService.start_claim(self.listing.id, '+256700000123')
        ListingClaimService.submit_liveness_capture(claim.id, _fake_image())

        admin = Account(handle=f'test_admin_{uuid.uuid4().hex[:8]}', display_name='Admin', is_admin=1)
        db.session.add(admin)
        db.session.commit()
        try:
            ListingClaimService.admin_review_liveness(claim.id, admin, passed=True)
            db.session.refresh(claim)
            self.assertNotEqual(claim.status, 'authorized')  # one factor only

            ListingClaimService.request_otp(claim.id)
            ok, _ = ListingClaimService.verify_otp_step(claim.id, DEV_OTP_CODE)
            self.assertTrue(ok)
            db.session.refresh(claim)
            self.assertEqual(claim.status, 'authorized')
        finally:
            db.session.delete(admin)
            db.session.commit()

    def test_failed_liveness_review_does_not_authorize_even_with_otp_passed(self):
        claim = ListingClaimService.start_claim(self.listing.id, '+256700000123')
        ListingClaimService.request_otp(claim.id)
        ListingClaimService.verify_otp_step(claim.id, DEV_OTP_CODE)
        ListingClaimService.submit_liveness_capture(claim.id, _fake_image())

        admin = Account(handle=f'test_admin_{uuid.uuid4().hex[:8]}', display_name='Admin', is_admin=1)
        db.session.add(admin)
        db.session.commit()
        try:
            ListingClaimService.admin_review_liveness(claim.id, admin, passed=False, notes='does not match')
            db.session.refresh(claim)
            self.assertNotEqual(claim.status, 'authorized')
        finally:
            db.session.delete(admin)
            db.session.commit()

    def test_wrong_otp_code_records_failed_event_and_does_not_authorize(self):
        claim = ListingClaimService.start_claim(self.listing.id, '+256700000123')
        ListingClaimService.request_otp(claim.id)
        ok, message = ListingClaimService.verify_otp_step(claim.id, '000000')
        self.assertFalse(ok)

        events = ClaimVerificationEvent.query.filter_by(claim_id=claim.id, method='otp').all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].result, 'failed')
        db.session.refresh(claim)
        self.assertNotEqual(claim.status, 'authorized')

    def test_admin_review_liveness_requires_capture_submitted_first(self):
        claim = ListingClaimService.start_claim(self.listing.id, '+256700000123')
        admin = Account(handle=f'test_admin_{uuid.uuid4().hex[:8]}', display_name='Admin', is_admin=1)
        db.session.add(admin)
        db.session.commit()
        try:
            with self.assertRaises(ClaimError):
                ListingClaimService.admin_review_liveness(claim.id, admin, passed=True)
        finally:
            db.session.delete(admin)
            db.session.commit()

    def test_no_admin_transition_can_target_authorized(self):
        """Structural guarantee: 'authorized' does not appear as a destination
        in ADMIN_ALLOWED_TRANSITIONS at all, for any starting status."""
        destinations = {to_status for (_, to_status) in ADMIN_ALLOWED_TRANSITIONS}
        self.assertNotIn('authorized', destinations)

    def test_admin_transition_to_authorized_is_rejected_regardless_of_current_status(self):
        claim = ListingClaimService.start_claim(self.listing.id, '+256700000123')
        admin = Account(handle=f'test_admin_{uuid.uuid4().hex[:8]}', display_name='Admin', is_admin=1)
        db.session.add(admin)
        db.session.commit()
        try:
            with self.assertRaises(ClaimError):
                ListingClaimService.admin_transition(claim.id, 'authorized', admin)
        finally:
            db.session.delete(admin)
            db.session.commit()

    def test_search_listings_only_returns_claimable_statuses(self):
        other = SourceListing(
            source='test_fixture_source', external_id=f'claim-test-published-{uuid.uuid4().hex[:8]}',
            source_url='https://example.com/listing/y', canonical_url='https://example.com/listing/y',
            location_text='Kampala', claim_status='published', parser_version='test-v1',
        )
        db.session.add(other)
        db.session.commit()
        try:
            items, total, *_ = ListingClaimService.search_listings(source='test_fixture_source')
            ids = {i['id'] for i in items}
            self.assertIn(self.listing.id, ids)
            self.assertNotIn(other.id, ids)
            # Public search must never expose the raw source_url.
            for item in items:
                self.assertNotIn('source_url', item)
        finally:
            db.session.delete(other)
            db.session.commit()


class ListingClaimRoutesTests(unittest.TestCase):
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
        self.listing = SourceListing(
            source='test_fixture_source', external_id=f'route-test-{uuid.uuid4().hex[:8]}',
            source_url='https://example.com/listing/z', canonical_url='https://example.com/listing/z',
            location_text='Kampala', claim_status='discovered', parser_version='test-v1',
        )
        db.session.add(self.listing)
        suffix = uuid.uuid4().hex[:8]
        self.admin = Account(handle=f'test_admin_{suffix}', display_name='Test Admin', is_admin=1)
        db.session.add(self.admin)
        db.session.commit()
        self.admin_headers = {'Authorization': f'Bearer {create_access_token(identity=self.admin.id)}'}

    def tearDown(self):
        ClaimVerificationEvent.query.filter(
            ClaimVerificationEvent.claim_id.in_(
                db.session.query(ListingClaim.id).filter_by(source_listing_id=self.listing.id)
            )
        ).delete(synchronize_session=False)
        ListingClaim.query.filter_by(source_listing_id=self.listing.id).delete(synchronize_session=False)
        db.session.delete(self.listing)
        Account.query.filter_by(id=self.admin.id).delete(synchronize_session=False)
        db.session.commit()

    def test_public_search_route(self):
        resp = self.client.get('/v1/listings/search', query_string={'source': 'test_fixture_source'})
        self.assertEqual(resp.status_code, 200)
        ids = {row['id'] for row in resp.get_json()['data']['data']}
        self.assertIn(self.listing.id, ids)

    def test_public_claim_flow_end_to_end_via_http(self):
        start = self.client.post('/v1/listings/claims', json={
            'source_listing_id': self.listing.id, 'phone': '+256700000999',
        })
        self.assertEqual(start.status_code, 200)
        claim_id = start.get_json()['data']['claim_id']

        otp_req = self.client.post(f'/v1/listings/claims/{claim_id}/otp/request')
        self.assertEqual(otp_req.status_code, 200)

        otp_verify = self.client.post(f'/v1/listings/claims/{claim_id}/otp/verify', json={'code': DEV_OTP_CODE})
        self.assertEqual(otp_verify.status_code, 200)

        liveness = self.client.post(
            f'/v1/listings/claims/{claim_id}/liveness',
            data={'capture': (_io_bytes(), 'selfie.jpg')},
            content_type='multipart/form-data',
        )
        self.assertEqual(liveness.status_code, 200)

        review = self.client.post(
            f'/v1/admin/listings/claims/{claim_id}/review-liveness',
            json={'passed': True}, headers=self.admin_headers,
        )
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.get_json()['data']['status'], 'authorized')

        status = self.client.get(f'/v1/listings/claims/{claim_id}')
        self.assertEqual(status.get_json()['data']['status'], 'authorized')

    def test_admin_transition_route_rejects_authorized_as_target(self):
        start = self.client.post('/v1/listings/claims', json={
            'source_listing_id': self.listing.id, 'phone': '+256700000999',
        })
        claim_id = start.get_json()['data']['claim_id']

        resp = self.client.post(
            f'/v1/admin/listings/claims/{claim_id}/transition',
            json={'status': 'authorized'}, headers=self.admin_headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_admin_transition_route_requires_admin(self):
        start = self.client.post('/v1/listings/claims', json={
            'source_listing_id': self.listing.id, 'phone': '+256700000999',
        })
        claim_id = start.get_json()['data']['claim_id']

        resp = self.client.post(
            f'/v1/admin/listings/claims/{claim_id}/transition', json={'status': 'rejected'},
        )
        self.assertEqual(resp.status_code, 401)

    def test_list_claims_route_requires_admin(self):
        resp = self.client.get('/v1/admin/listings/claims')
        self.assertEqual(resp.status_code, 401)
        resp2 = self.client.get('/v1/admin/listings/claims', headers=self.admin_headers)
        self.assertEqual(resp2.status_code, 200)

    def test_list_claims_route_enriches_with_listing_and_events(self):
        """The admin UI's Claims table needs listing context + which factors
        passed without an extra round trip per row — confirms list_claims()
        actually includes them, not just the bare claim fields."""
        start = self.client.post('/v1/listings/claims', json={
            'source_listing_id': self.listing.id, 'phone': '+256700000999',
        })
        claim_id = start.get_json()['data']['claim_id']
        self.client.post(f'/v1/listings/claims/{claim_id}/otp/request')
        self.client.post(f'/v1/listings/claims/{claim_id}/otp/verify', json={'code': DEV_OTP_CODE})

        resp = self.client.get('/v1/admin/listings/claims', headers=self.admin_headers)
        row = next(r for r in resp.get_json()['data']['data'] if r['id'] == claim_id)
        self.assertEqual(row['listing']['source'], 'test_fixture_source')
        self.assertEqual(row['listing']['location_text'], 'Kampala')
        methods_passed = {e['method'] for e in row['verification_events'] if e['result'] == 'passed'}
        self.assertIn('otp', methods_passed)
        self.assertNotIn('liveness_match', methods_passed)


def _io_bytes():
    import io
    return io.BytesIO(b'not-a-real-image-just-test-bytes')


if __name__ == '__main__':
    unittest.main()
