"""
Tests for POST /v1/admin/accounts — admin-created accounts with an optional
complete dating/professional profile in one request.
"""
import unittest
import uuid

from flask_jwt_extended import create_access_token

from backend.app import create_app
from backend.models import db
from backend.domains.identity.models import Account
from backend.domains.profile.models import DatingProfile, ProfessionalProfile
from backend.domains.reference.models import Location


class AdminAccountCreationTests(unittest.TestCase):
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
        self.admin_headers = {'Authorization': f'Bearer {create_access_token(identity=self.admin.id)}'}
        self.plain_headers = {'Authorization': f'Bearer {create_access_token(identity=self.plain_user.id)}'}
        self.created_account_ids = []

    def tearDown(self):
        if self.created_account_ids:
            DatingProfile.query.filter(DatingProfile.account_id.in_(self.created_account_ids)).delete(synchronize_session=False)
            ProfessionalProfile.query.filter(ProfessionalProfile.account_id.in_(self.created_account_ids)).delete(synchronize_session=False)
            Account.query.filter(Account.id.in_(self.created_account_ids)).delete(synchronize_session=False)
        Account.query.filter(Account.id.in_([self.admin.id, self.plain_user.id])).delete(synchronize_session=False)
        db.session.commit()

    def _phone(self):
        return f'+2567{uuid.uuid4().int % 10**8:08d}'

    def test_requires_authentication(self):
        resp = self.client.post('/v1/admin/accounts', json={'display_name': 'X', 'phone': self._phone()})
        self.assertEqual(resp.status_code, 401)

    def test_rejects_non_admin(self):
        resp = self.client.post('/v1/admin/accounts', json={'display_name': 'X', 'phone': self._phone()},
                                 headers=self.plain_headers)
        self.assertEqual(resp.status_code, 403)

    def test_minimal_creation_generates_password(self):
        phone = self._phone()
        resp = self.client.post('/v1/admin/accounts', json={
            'display_name': 'Jane Doe', 'phone': phone,
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()['data']
        self.created_account_ids.append(data['id'])

        self.assertIn('generated_password', data)
        self.assertGreaterEqual(len(data['generated_password']), 10)

        acct = db.session.get(Account, data['id'])
        self.assertTrue(acct.check_password(data['generated_password']))

    def test_explicit_password_is_not_echoed_back(self):
        phone = self._phone()
        resp = self.client.post('/v1/admin/accounts', json={
            'display_name': 'Jane Doe', 'phone': phone, 'password': 'MyRealPassword123',
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()['data']
        self.created_account_ids.append(data['id'])
        self.assertNotIn('generated_password', data)

        acct = db.session.get(Account, data['id'])
        self.assertTrue(acct.check_password('MyRealPassword123'))

    def test_requires_display_name(self):
        resp = self.client.post('/v1/admin/accounts', json={'phone': self._phone()}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)

    def test_requires_phone_or_email(self):
        resp = self.client.post('/v1/admin/accounts', json={'display_name': 'No Contact'}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)

    def test_rejects_duplicate_phone(self):
        phone = self._phone()
        r1 = self.client.post('/v1/admin/accounts', json={'display_name': 'A', 'phone': phone}, headers=self.admin_headers)
        self.created_account_ids.append(r1.get_json()['data']['id'])
        r2 = self.client.post('/v1/admin/accounts', json={'display_name': 'B', 'phone': phone}, headers=self.admin_headers)
        self.assertEqual(r2.status_code, 400)

    def test_rejects_duplicate_handle(self):
        suffix = uuid.uuid4().hex[:8]
        handle = f'dup_handle_{suffix}'
        r1 = self.client.post('/v1/admin/accounts', json={
            'display_name': 'A', 'phone': self._phone(), 'handle': handle,
        }, headers=self.admin_headers)
        self.created_account_ids.append(r1.get_json()['data']['id'])
        r2 = self.client.post('/v1/admin/accounts', json={
            'display_name': 'B', 'phone': self._phone(), 'handle': handle,
        }, headers=self.admin_headers)
        self.assertEqual(r2.status_code, 400)

    def test_rejects_invalid_app_id(self):
        resp = self.client.post('/v1/admin/accounts', json={
            'display_name': 'X', 'phone': self._phone(), 'app_id': 'not_a_real_app',
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)

    def test_creates_dating_profile_when_sparks_enabled(self):
        district = Location.query.filter_by(level='district').first()
        resp = self.client.post('/v1/admin/accounts', json={
            'display_name': 'Dating Test', 'phone': self._phone(),
            'modes': {'sparks': True, 'professional': False},
            'dating_profile': {
                'bio': 'Hello world', 'gender': 'female', 'looking_for_gender': 'male',
                'birth_year': 1998, 'relationship_goal': 'long_term',
                'district_id': district.id if district else None,
            },
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 201)
        account_id = resp.get_json()['data']['id']
        self.created_account_ids.append(account_id)

        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        self.assertIsNotNone(dp)
        self.assertEqual(dp.bio, 'Hello world')
        self.assertEqual(dp.gender, 'female')
        self.assertEqual(dp.birth_year, 1998)
        if district:
            self.assertEqual(dp.district_id, district.id)
            if district.parent_id:
                self.assertEqual(dp.region_id, district.parent_id)

    def test_no_dating_profile_when_sparks_disabled(self):
        resp = self.client.post('/v1/admin/accounts', json={
            'display_name': 'No Sparks', 'phone': self._phone(),
            'modes': {'sparks': False, 'professional': True},
            'dating_profile': {'bio': 'Should be ignored'},
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 201)
        account_id = resp.get_json()['data']['id']
        self.created_account_ids.append(account_id)
        self.assertIsNone(DatingProfile.query.filter_by(account_id=account_id).first())

    def test_creates_professional_profile_when_enabled(self):
        resp = self.client.post('/v1/admin/accounts', json={
            'display_name': 'Pro Test', 'phone': self._phone(),
            'modes': {'professional': True, 'sparks': False},
            'professional_profile': {
                'headline': 'Software Engineer', 'seniority': 'senior', 'industry': 'technology',
            },
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 201)
        account_id = resp.get_json()['data']['id']
        self.created_account_ids.append(account_id)

        pp = ProfessionalProfile.query.filter_by(account_id=account_id).first()
        self.assertIsNotNone(pp)
        self.assertEqual(pp.headline, 'Software Engineer')
        self.assertEqual(pp.seniority, 'senior')

    def test_dating_profile_field_whitelist_ignores_unknown_fields(self):
        """Confirms mass-assignment is scoped to the whitelist, not the raw
        request body — an unexpected key must not reach the model."""
        resp = self.client.post('/v1/admin/accounts', json={
            'display_name': 'Whitelist Test', 'phone': self._phone(),
            'modes': {'sparks': True},
            'dating_profile': {'bio': 'ok', 'account_id': 'should-not-be-settable', 'id': 'nope'},
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 201)
        account_id = resp.get_json()['data']['id']
        self.created_account_ids.append(account_id)
        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        self.assertEqual(dp.account_id, account_id)  # untouched by the bogus value
        self.assertNotEqual(dp.id, 'nope')


if __name__ == '__main__':
    unittest.main()
