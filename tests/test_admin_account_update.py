"""
Tests for PUT /v1/admin/accounts/<id> (the edit-mode counterpart of account
creation) and DELETE /v1/admin/accounts/<id>/photos/<photo_id>.
"""
import io
import unittest
import uuid

from flask_jwt_extended import create_access_token

from backend.app import create_app
from backend.models import db
from backend.domains.identity.models import Account
from backend.domains.profile.models import DatingProfile, ProfessionalProfile
from backend.domains.photos.models import UserPhoto


class AdminAccountUpdateTests(unittest.TestCase):
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
            UserPhoto.query.filter(UserPhoto.account_id.in_(self.created_account_ids)).delete(synchronize_session=False)
            DatingProfile.query.filter(DatingProfile.account_id.in_(self.created_account_ids)).delete(synchronize_session=False)
            ProfessionalProfile.query.filter(ProfessionalProfile.account_id.in_(self.created_account_ids)).delete(synchronize_session=False)
            Account.query.filter(Account.id.in_(self.created_account_ids)).delete(synchronize_session=False)
        Account.query.filter(Account.id.in_([self.admin.id, self.plain_user.id])).delete(synchronize_session=False)
        db.session.commit()

    def _phone(self):
        return f'+2567{uuid.uuid4().int % 10**8:08d}'

    def _create_account(self, **overrides):
        payload = {'display_name': 'Edit Target', 'phone': self._phone()}
        payload.update(overrides)
        resp = self.client.post('/v1/admin/accounts', json=payload, headers=self.admin_headers)
        account_id = resp.get_json()['data']['id']
        self.created_account_ids.append(account_id)
        return account_id

    def test_requires_authentication(self):
        account_id = self._create_account()
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'display_name': 'X'})
        self.assertEqual(resp.status_code, 401)

    def test_rejects_non_admin(self):
        account_id = self._create_account()
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'display_name': 'X'}, headers=self.plain_headers)
        self.assertEqual(resp.status_code, 403)

    def test_unknown_account_404s(self):
        resp = self.client.put(f'/v1/admin/accounts/{uuid.uuid4()}', json={'display_name': 'X'}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 404)

    def test_updates_basic_fields(self):
        account_id = self._create_account()
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={
            'display_name': 'Renamed User', 'is_premium': True,
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['data']
        self.assertEqual(data['display_name'], 'Renamed User')
        self.assertTrue(data['is_premium'])

    def test_rejects_duplicate_phone_from_another_account(self):
        other_phone = self._phone()
        self._create_account(phone=other_phone)
        account_id = self._create_account()
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'phone': other_phone}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)

    def test_keeping_own_phone_is_not_a_conflict(self):
        phone = self._phone()
        account_id = self._create_account(phone=phone)
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={
            'phone': phone, 'display_name': 'Still Me',
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

    def test_cannot_clear_both_phone_and_email(self):
        account_id = self._create_account()  # phone-only
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'phone': ''}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)

    def test_password_change_takes_effect(self):
        account_id = self._create_account()
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'password': 'BrandNewPassword1'}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        acct = db.session.get(Account, account_id)
        self.assertTrue(acct.check_password('BrandNewPassword1'))

    def test_blank_password_leaves_existing_password_untouched(self):
        account_id = self._create_account(password='OriginalPassword1')
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'password': '', 'display_name': 'No password change'}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        acct = db.session.get(Account, account_id)
        self.assertTrue(acct.check_password('OriginalPassword1'))

    def test_creates_dating_profile_on_edit_when_none_existed(self):
        account_id = self._create_account(modes={'sparks': True, 'professional': False})
        self.assertIsNone(DatingProfile.query.filter_by(account_id=account_id).first())
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={
            'modes': {'sparks': True}, 'dating_profile': {'bio': 'Added on edit', 'gender': 'male'},
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        self.assertIsNotNone(dp)
        self.assertEqual(dp.bio, 'Added on edit')

    def test_updates_existing_dating_profile_fields(self):
        account_id = self._create_account(
            modes={'sparks': True, 'professional': False},
            dating_profile={'bio': 'Original bio', 'gender': 'female'},
        )
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={
            'modes': {'sparks': True}, 'dating_profile': {'bio': 'Updated bio'},
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        self.assertEqual(dp.bio, 'Updated bio')
        self.assertEqual(dp.gender, 'female')  # untouched field survives a partial update

    def test_disabling_a_mode_does_not_delete_its_profile_data(self):
        account_id = self._create_account(
            modes={'sparks': True, 'professional': False},
            dating_profile={'bio': 'Should survive'},
        )
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={
            'modes': {'sparks': False},
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()['data']['modes_enabled']['sparks'])
        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        self.assertIsNotNone(dp)
        self.assertEqual(dp.bio, 'Should survive')

    # ── Photo deletion ──────────────────────────────────────────────────────

    def _upload_photo(self, account_id, is_profile=False):
        resp = self.client.post(
            f'/v1/admin/accounts/{account_id}/photos',
            data={'photo': (io.BytesIO(b'test-bytes'), 'p.jpg'), **({'is_profile_photo': 'true'} if is_profile else {})},
            content_type='multipart/form-data', headers=self.admin_headers,
        )
        return resp.get_json()['data']['id']

    def test_delete_photo_requires_admin(self):
        account_id = self._create_account()
        photo_id = self._upload_photo(account_id)
        resp = self.client.delete(f'/v1/admin/accounts/{account_id}/photos/{photo_id}')
        self.assertEqual(resp.status_code, 401)

    def test_delete_unknown_photo_404s(self):
        account_id = self._create_account()
        resp = self.client.delete(f'/v1/admin/accounts/{account_id}/photos/{uuid.uuid4()}', headers=self.admin_headers)
        self.assertEqual(resp.status_code, 404)

    def test_delete_photo_removes_it(self):
        account_id = self._create_account()
        photo_id = self._upload_photo(account_id)
        resp = self.client.delete(f'/v1/admin/accounts/{account_id}/photos/{photo_id}', headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(db.session.get(UserPhoto, photo_id))

    def test_delete_profile_photo_promotes_next_one(self):
        account_id = self._create_account()
        first_id = self._upload_photo(account_id, is_profile=True)
        second_id = self._upload_photo(account_id)

        resp = self.client.delete(f'/v1/admin/accounts/{account_id}/photos/{first_id}', headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

        second = db.session.get(UserPhoto, second_id)
        self.assertTrue(second.is_profile_photo)
        acct = db.session.get(Account, account_id)
        self.assertEqual(acct.avatar, second.url)

    # ── Enriched list/detail ─────────────────────────────────────────────────

    def test_list_accounts_includes_dating_summary_and_photo_count(self):
        account_id = self._create_account(
            modes={'sparks': True, 'professional': False},
            dating_profile={'bio': 'List me', 'gender': 'male', 'birth_year': 1995},
        )
        self._upload_photo(account_id)

        resp = self.client.get('/v1/admin/accounts', query_string={'q': 'Edit Target', 'per_page': 50}, headers=self.admin_headers)
        row = next(r for r in resp.get_json()['data']['data'] if r['id'] == account_id)
        self.assertEqual(row['photo_count'], 1)
        self.assertIsNotNone(row['dating_profile_summary'])
        self.assertEqual(row['dating_profile_summary']['bio'], 'List me')
        self.assertIsInstance(row['dating_profile_summary']['age'], int)

    def test_get_account_includes_full_photo_list(self):
        account_id = self._create_account()
        self._upload_photo(account_id, is_profile=True)
        self._upload_photo(account_id)

        resp = self.client.get(f'/v1/admin/accounts/{account_id}', headers=self.admin_headers)
        data = resp.get_json()['data']
        self.assertEqual(len(data['photos']), 2)
        self.assertEqual(data['photo_count'], 2)


if __name__ == '__main__':
    unittest.main()
