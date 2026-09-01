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

    def test_account_status_can_be_set_via_edit(self):
        account_id = self._create_account()
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'account_status': 'inactive'}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['data']['account_status'], 'inactive')
        acct = db.session.get(Account, account_id)
        self.assertEqual(acct.account_status, 'inactive')
        self.assertIsNone(acct.deleted_at)

    def test_account_status_closed_sets_deleted_at(self):
        account_id = self._create_account()
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'account_status': 'closed'}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        acct = db.session.get(Account, account_id)
        self.assertEqual(acct.account_status, 'closed')
        self.assertIsNotNone(acct.deleted_at)

    def test_account_status_rejects_invalid_value(self):
        account_id = self._create_account()
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'account_status': 'bogus'}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)

    def test_account_status_reactivating_from_closed_clears_deleted_at(self):
        account_id = self._create_account()
        self.client.put(f'/v1/admin/accounts/{account_id}', json={'account_status': 'closed'}, headers=self.admin_headers)
        resp = self.client.put(f'/v1/admin/accounts/{account_id}', json={'account_status': 'active'}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        acct = db.session.get(Account, account_id)
        self.assertIsNone(acct.deleted_at)

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
        # A genuine (if tiny) JPEG — PhotoService.upload decodes uploads via
        # Pillow (see image_compress.py) rather than trusting the filename
        # extension, so placeholder text bytes would be rejected.
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (20, 20), color=(120, 140, 160)).save(buf, 'JPEG')
        buf.seek(0)
        resp = self.client.post(
            f'/v1/admin/accounts/{account_id}/photos',
            data={'photo': (buf, 'p.jpg'), **({'is_profile_photo': 'true'} if is_profile else {})},
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

    # ── Dating-profile-only photos (the Sparks mobile upload path) ──────────
    # DatingProfile.photos is written directly by sparks/routes.py, never by
    # the admin create/update endpoints (it isn't in _DATING_PROFILE_FIELDS),
    # so these tests set it straight on the model — same as a real mobile
    # dating-photo upload would leave it.

    def _set_dating_photos(self, account_id, urls):
        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        if not dp:
            dp = DatingProfile(account_id=account_id)
            db.session.add(dp)
        dp.photos = [{'url': u, 'caption': None} for u in urls]
        db.session.commit()

    def test_list_accounts_falls_back_to_dating_photo_for_avatar_and_count(self):
        account_id = self._create_account(modes={'sparks': True, 'professional': False})
        self._set_dating_photos(account_id, ['https://cdn.example.com/dating1.jpg', 'https://cdn.example.com/dating2.jpg'])

        resp = self.client.get('/v1/admin/accounts', query_string={'q': 'Edit Target', 'per_page': 50}, headers=self.admin_headers)
        row = next(r for r in resp.get_json()['data']['data'] if r['id'] == account_id)
        self.assertEqual(row['avatar'], 'https://cdn.example.com/dating1.jpg')
        self.assertEqual(row['photo_count'], 2)

    def test_list_accounts_prefers_real_avatar_over_dating_photo(self):
        account_id = self._create_account(modes={'sparks': True, 'professional': False})
        self._set_dating_photos(account_id, ['https://cdn.example.com/dating1.jpg'])
        acct = db.session.get(Account, account_id)
        acct.avatar = 'https://cdn.example.com/real-avatar.jpg'
        db.session.commit()

        resp = self.client.get('/v1/admin/accounts', query_string={'q': 'Edit Target', 'per_page': 50}, headers=self.admin_headers)
        row = next(r for r in resp.get_json()['data']['data'] if r['id'] == account_id)
        self.assertEqual(row['avatar'], 'https://cdn.example.com/real-avatar.jpg')

    def test_get_account_merges_dating_photos_with_dating_prefixed_ids(self):
        account_id = self._create_account(modes={'sparks': True, 'professional': False})
        # Dating photos set up first (the realistic order — onboarding wizard
        # runs before an admin adds an extra gallery photo later): the
        # gallery upload then correctly sees an existing primary photo and
        # doesn't self-promote (see PhotoService.upload's first-photo rule).
        self._set_dating_photos(account_id, ['https://cdn.example.com/dating1.jpg', 'https://cdn.example.com/dating2.jpg'])
        self._upload_photo(account_id)

        resp = self.client.get(f'/v1/admin/accounts/{account_id}', headers=self.admin_headers)
        data = resp.get_json()['data']
        self.assertEqual(data['photo_count'], 3)
        dating_ids = sorted(p['id'] for p in data['photos'] if p['id'].startswith('dating:'))
        self.assertEqual(dating_ids, ['dating:0', 'dating:1'])
        # account.avatar was never set (no is_profile_photo upload), so the
        # resolved avatar falls back to the first dating photo.
        self.assertEqual(data['avatar'], 'https://cdn.example.com/dating1.jpg')

    def test_delete_dating_photo_removes_it_by_index(self):
        account_id = self._create_account(modes={'sparks': True, 'professional': False})
        self._set_dating_photos(account_id, ['https://cdn.example.com/dating1.jpg', 'https://cdn.example.com/dating2.jpg'])

        resp = self.client.delete(f'/v1/admin/accounts/{account_id}/photos/dating:0', headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        self.assertEqual(len(dp.photos), 1)
        self.assertEqual(dp.photos[0]['url'], 'https://cdn.example.com/dating2.jpg')

    def test_delete_dating_photo_unknown_index_404s(self):
        account_id = self._create_account(modes={'sparks': True, 'professional': False})
        self._set_dating_photos(account_id, ['https://cdn.example.com/dating1.jpg'])

        resp = self.client.delete(f'/v1/admin/accounts/{account_id}/photos/dating:5', headers=self.admin_headers)
        self.assertEqual(resp.status_code, 404)

    def test_delete_dating_photo_malformed_index_404s(self):
        account_id = self._create_account(modes={'sparks': True, 'professional': False})
        self._set_dating_photos(account_id, ['https://cdn.example.com/dating1.jpg'])

        resp = self.client.delete(f'/v1/admin/accounts/{account_id}/photos/dating:not-a-number', headers=self.admin_headers)
        self.assertEqual(resp.status_code, 404)

    def test_list_accounts_gender_filter(self):
        f_id = self._create_account(modes={'sparks': True, 'professional': False},
                                     dating_profile={'gender': 'female'})
        m_id = self._create_account(modes={'sparks': True, 'professional': False},
                                     dating_profile={'gender': 'male'})
        resp = self.client.get('/v1/admin/accounts', query_string={'gender': 'female', 'per_page': 100}, headers=self.admin_headers)
        ids = {r['id'] for r in resp.get_json()['data']['data']}
        self.assertIn(f_id, ids)
        self.assertNotIn(m_id, ids)

    def test_delete_real_photo_still_works_when_dating_photos_also_exist(self):
        account_id = self._create_account(modes={'sparks': True, 'professional': False})
        photo_id = self._upload_photo(account_id)
        self._set_dating_photos(account_id, ['https://cdn.example.com/dating1.jpg'])

        resp = self.client.delete(f'/v1/admin/accounts/{account_id}/photos/{photo_id}', headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(db.session.get(UserPhoto, photo_id))
        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        self.assertEqual(len(dp.photos), 1)  # untouched


if __name__ == '__main__':
    unittest.main()
