import React, { useEffect, useState } from 'react';
import { adminAPI, dataOf } from '../services/api';
import { Modal, Lightbox } from './adminUi';
import { FiStar, FiImage } from 'react-icons/fi';

/**
 * Full photo gallery for one account — fetched fresh from the backend (not
 * the list-row's cached avatar/count) so it always reflects both photo
 * stores (UserPhoto + DatingProfile.photos, see admin/routes.py's
 * _dating_photo_entries) exactly as the edit form and mobile app see them.
 * Click any thumbnail to open it full-size via Lightbox.
 */
export default function AccountGalleryModal({ accountId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lightboxIndex, setLightboxIndex] = useState(null);

  useEffect(() => {
    if (!accountId) return;
    setLoading(true);
    setData(null);
    adminAPI.accountShow(accountId)
      .then((res) => setData(dataOf(res)))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [accountId]);

  const photos = data?.photos || [];
  const urls = photos.map((p) => p.url);

  return (
    <>
      <Modal open={!!accountId} onClose={onClose} width={640}
        title={data ? `${data.display_name || 'Member'}'s photos (${photos.length})` : 'Photos'}>
        {loading ? (
          <div style={{ color: '#9a9aa3', textAlign: 'center', padding: '30px 0' }}>Loading…</div>
        ) : photos.length === 0 ? (
          <div style={{ color: '#9a9aa3', textAlign: 'center', padding: '30px 0' }}>
            <FiImage size={26} style={{ marginBottom: 8 }} /><br />No photos yet.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 12 }}>
            {photos.map((p, i) => (
              <div key={p.id || i} onClick={() => setLightboxIndex(i)} style={{
                position: 'relative', aspectRatio: '1', borderRadius: 10, overflow: 'hidden',
                cursor: 'pointer', background: `#000 url(${p.url}) center/cover no-repeat`,
                border: '1px solid #ececf1',
              }}>
                {p.is_profile_photo && (
                  <span style={{
                    position: 'absolute', top: 6, left: 6, display: 'inline-flex', alignItems: 'center', gap: 3,
                    background: 'rgba(124,58,237,0.92)', color: '#fff', fontSize: 10, fontWeight: 700,
                    padding: '2px 7px', borderRadius: 5,
                  }}><FiStar size={9} /> Main</span>
                )}
              </div>
            ))}
          </div>
        )}
      </Modal>
      <Lightbox images={urls} index={lightboxIndex} onIndex={setLightboxIndex} onClose={() => setLightboxIndex(null)} />
    </>
  );
}
