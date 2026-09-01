"""
Tests for backend/shared/storage/url_fetch.py — the SSRF-safe image fetcher
powering "drag an image from another website" in the admin console.

DNS resolution and the actual HTTP GET are mocked throughout so these run
with no real network access and no dependency on any external host being
reachable — the logic under test is the *validation*, not connectivity.
"""
import io
import unittest
from unittest.mock import patch, MagicMock

from backend.shared.storage.url_fetch import fetch_image_from_url, ImageFetchError, MAX_IMAGE_BYTES


def _fake_jpeg_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (10, 10), color='red').save(buf, format='JPEG')
    return buf.getvalue()


def _public_dns(*_a, **_kw):
    return [(2, 1, 6, '', ('93.184.216.34', 0))]


class UrlFetchSsrfGuardTests(unittest.TestCase):
    def test_rejects_empty_url(self):
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('')

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('file:///etc/passwd')
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('gopher://example.com/x')

    def test_rejects_localhost_hostname(self):
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://localhost/image.jpg')

    def test_rejects_loopback_ip(self):
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://127.0.0.1/image.jpg')

    def test_rejects_cloud_metadata_ip(self):
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://169.254.169.254/latest/meta-data/')

    def test_rejects_private_ip_ranges(self):
        for url in ('http://10.0.0.5/x.jpg', 'http://192.168.1.1/x.jpg', 'http://172.16.0.1/x.jpg'):
            with self.assertRaises(ImageFetchError):
                fetch_image_from_url(url)

    def test_rejects_unresolvable_host(self):
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://this-host-should-not-exist.invalid/x.jpg')


class UrlFetchHappyPathTests(unittest.TestCase):
    @patch('backend.shared.storage.url_fetch.socket.getaddrinfo', side_effect=_public_dns)
    @patch('backend.shared.storage.url_fetch.requests.get')
    def test_successful_fetch_returns_bytes_and_ext(self, mock_get, _mock_dns):
        jpeg = _fake_jpeg_bytes()
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {'Content-Type': 'image/jpeg', 'Content-Length': str(len(jpeg))}
        resp.iter_content.return_value = [jpeg]
        mock_get.return_value = resp

        data, ext = fetch_image_from_url('http://example.com/photo.jpg')
        self.assertEqual(ext, 'jpg')
        self.assertEqual(data, jpeg)

    @patch('backend.shared.storage.url_fetch.socket.getaddrinfo', side_effect=_public_dns)
    @patch('backend.shared.storage.url_fetch.requests.get')
    def test_follows_redirect_and_revalidates_each_hop(self, mock_get, mock_dns):
        jpeg = _fake_jpeg_bytes()
        redirect_resp = MagicMock(status_code=302, headers={'Location': 'http://cdn.example.com/photo.jpg'})
        final_resp = MagicMock(status_code=200,
                                headers={'Content-Type': 'image/jpeg', 'Content-Length': str(len(jpeg))})
        final_resp.iter_content.return_value = [jpeg]
        mock_get.side_effect = [redirect_resp, final_resp]

        data, ext = fetch_image_from_url('http://example.com/redirect')
        self.assertEqual(ext, 'jpg')
        self.assertEqual(mock_dns.call_count, 2)  # both the original host and the redirect target

    @patch('backend.shared.storage.url_fetch.socket.getaddrinfo')
    @patch('backend.shared.storage.url_fetch.requests.get')
    def test_redirect_to_private_ip_is_blocked(self, mock_get, mock_dns):
        def dns_side_effect(host, *_a, **_kw):
            if host == 'evil.example.com':
                return [(2, 1, 6, '', ('127.0.0.1', 0))]
            return _public_dns()
        mock_dns.side_effect = dns_side_effect
        mock_get.return_value = MagicMock(status_code=302, headers={'Location': 'http://evil.example.com/x.jpg'})

        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://example.com/redirect')

    @patch('backend.shared.storage.url_fetch.socket.getaddrinfo', side_effect=_public_dns)
    @patch('backend.shared.storage.url_fetch.requests.get')
    def test_too_many_redirects_raises(self, mock_get, _mock_dns):
        mock_get.return_value = MagicMock(status_code=302, headers={'Location': 'http://example.com/next'})
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://example.com/loop')

    @patch('backend.shared.storage.url_fetch.socket.getaddrinfo', side_effect=_public_dns)
    @patch('backend.shared.storage.url_fetch.requests.get')
    def test_rejects_oversized_declared_content_length(self, mock_get, _mock_dns):
        mock_get.return_value = MagicMock(
            status_code=200,
            headers={'Content-Type': 'image/jpeg', 'Content-Length': str(MAX_IMAGE_BYTES + 1)},
        )
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://example.com/huge.jpg')

    @patch('backend.shared.storage.url_fetch.socket.getaddrinfo', side_effect=_public_dns)
    @patch('backend.shared.storage.url_fetch.requests.get')
    def test_rejects_oversized_actual_stream_without_content_length_header(self, mock_get, _mock_dns):
        resp = MagicMock(status_code=200, headers={'Content-Type': 'image/jpeg'})
        chunk = b'a' * 70_000
        resp.iter_content.return_value = [chunk] * ((MAX_IMAGE_BYTES // 70_000) + 2)
        mock_get.return_value = resp
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://example.com/huge.jpg')

    @patch('backend.shared.storage.url_fetch.socket.getaddrinfo', side_effect=_public_dns)
    @patch('backend.shared.storage.url_fetch.requests.get')
    def test_rejects_non_image_content_type(self, mock_get, _mock_dns):
        mock_get.return_value = MagicMock(status_code=200, headers={'Content-Type': 'text/html'})
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://example.com/page.html')

    @patch('backend.shared.storage.url_fetch.socket.getaddrinfo', side_effect=_public_dns)
    @patch('backend.shared.storage.url_fetch.requests.get')
    def test_rejects_fake_bytes_despite_image_content_type(self, mock_get, _mock_dns):
        resp = MagicMock(status_code=200, headers={'Content-Type': 'image/jpeg'})
        resp.iter_content.return_value = [b'not-actually-a-jpeg-just-text-pretending']
        mock_get.return_value = resp
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://example.com/fake.jpg')

    @patch('backend.shared.storage.url_fetch.socket.getaddrinfo', side_effect=_public_dns)
    @patch('backend.shared.storage.url_fetch.requests.get')
    def test_non_200_status_raises(self, mock_get, _mock_dns):
        mock_get.return_value = MagicMock(status_code=404, headers={})
        with self.assertRaises(ImageFetchError):
            fetch_image_from_url('http://example.com/missing.jpg')


if __name__ == '__main__':
    unittest.main()
