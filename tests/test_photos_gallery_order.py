"""
Tests for the mobile-facing photo endpoints' ordering — GET /v1/photos and
GET /v1/photos/gallery — after fixing PhotoService.upload to actually set
sort_order (it previously left every row at the column default, silently
degenerating "gallery order" to reverse-upload-order wherever sort_order
was the intended tiebreaker).
"""
import io
import unittest
import uuid

from flask_jwt_extended import create_access_token

from backend.app import create_app
from backend.models import db
from backend.domains.identity.models import Account
from backend.domains.photos.models import UserPhoto


class PhotoGalleryOrderTests(unittest.TestCase):
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
        self.account = Account(handle=f'photo_test_{suffix}', display_name='Photo Test')
        db.session.add(self.account)
        db.session.commit()
        self.headers = {'Authorization': f'Bearer {create_access_token(identity=self.account.id)}'}

    def tearDown(self):
        UserPhoto.query.filter_by(account_id=self.account.id).delete(synchronize_session=False)
        Account.query.filter_by(id=self.account.id).delete(synchronize_session=False)
        db.session.commit()

    def _upload(self, color=(10, 20, 30)):
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (20, 20), color=color).save(buf, 'JPEG')
        buf.seek(0)
        resp = self.client.post('/v1/photos', data={'photo': (buf, 'p.jpg')},
                                 content_type='multipart/form-data', headers=self.headers)
        return resp.get_json()['data']

    def test_sort_order_increments_per_upload(self):
        first = self._upload()
        second = self._upload()
        third = self._upload()
        self.assertEqual([first['sort_order'], second['sort_order'], third['sort_order']], [0, 1, 2])

    def test_list_photos_preserves_upload_order(self):
        first = self._upload()
        second = self._upload()
        third = self._upload()

        resp = self.client.get('/v1/photos', headers=self.headers)
        ids = [p['id'] for p in resp.get_json()['data']]
        # first upload is also the profile photo, so it leads regardless;
        # the rest must follow in upload order, not reverse.
        self.assertEqual(ids, [first['id'], second['id'], third['id']])

    def test_gallery_preserves_upload_order_for_gallery_source(self):
        first = self._upload()
        second = self._upload()
        third = self._upload()

        resp = self.client.get('/v1/photos/gallery', headers=self.headers)
        items = resp.get_json()['data']['photos']
        gallery_urls = [i['url'] for i in items if i['source'] == 'gallery']
        # avatar now also equals the profile photo's URL and gets added
        # again under source='avatar' — only checking the 'gallery' slice.
        expected_order = [first['url'], second['url'], third['url']]
        self.assertEqual(gallery_urls, expected_order)

    def test_delete_promotes_earliest_remaining_photo_not_most_recent(self):
        first = self._upload()
        second = self._upload()
        third = self._upload()

        # Delete the current profile photo (the first upload).
        resp = self.client.delete(f"/v1/photos/{first['id']}", headers=self.headers)
        self.assertEqual(resp.status_code, 200)

        promoted = UserPhoto.query.filter_by(account_id=self.account.id, is_profile_photo=True).first()
        self.assertEqual(promoted.id, second['id'])  # earliest remaining, not third (most recent)
        acct = db.session.get(Account, self.account.id)
        self.assertEqual(acct.avatar, second['url'])


if __name__ == '__main__':
    unittest.main()
