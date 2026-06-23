from backend.models import db
from backend.domains.photos.models import UserPhoto
from backend.shared.storage.r2 import save_upload
from backend.shared.utils.response import success_response, error_response


class PhotoService:

    # ── Upload ────────────────────────────────────────────────────────────────

    @staticmethod
    def upload(account, flask_request):
        file = flask_request.files.get('photo')
        if not file:
            return error_response('No photo file provided.')

        url = save_upload(file, folder='gallery')
        if not url:
            return error_response('Upload failed. Use JPG, PNG, or WebP images.')

        form = flask_request.form
        is_profile = form.get('is_profile_photo', 'false').lower() == 'true'
        is_cover   = form.get('is_cover_photo',   'false').lower() == 'true'
        is_public  = form.get('is_public',         'true').lower() == 'true'
        caption    = (form.get('caption') or '').strip()[:300] or None

        account_id = str(account.id)

        # Un-set previous profile / cover so there is always at most one
        if is_profile:
            UserPhoto.query.filter_by(
                account_id=account_id, is_profile_photo=True
            ).update({'is_profile_photo': False}, synchronize_session=False)
            account.avatar = url

        if is_cover:
            UserPhoto.query.filter_by(
                account_id=account_id, is_cover_photo=True
            ).update({'is_cover_photo': False}, synchronize_session=False)
            account.cover_photo = url

        photo = UserPhoto(
            account_id=account_id,
            url=url,
            is_profile_photo=is_profile,
            is_cover_photo=is_cover,
            is_public=is_public,
            caption=caption,
        )
        db.session.add(photo)
        db.session.commit()

        return success_response('Photo uploaded.', photo.to_dict(), status_code=201)

    # ── List ──────────────────────────────────────────────────────────────────

    @staticmethod
    def list_photos(account_id, own=False):
        q = UserPhoto.query.filter_by(account_id=account_id)
        if not own:
            q = q.filter_by(is_public=True)
        photos = q.order_by(
            UserPhoto.is_profile_photo.desc(),
            UserPhoto.is_cover_photo.desc(),
            UserPhoto.sort_order.asc(),
            UserPhoto.created_at.desc(),
        ).all()
        return success_response('Photos loaded.', [p.to_dict() for p in photos])

    # ── Unified gallery (dedicated photos + post media + dating + avatar) ───────

    @staticmethod
    def list_gallery(viewer_id, account_id):
        """Every photo a user has ever shared, newest first, de-duplicated.

        Aggregates four sources into one chronological grid:
          1. Dedicated gallery uploads (UserPhoto)
          2. Image media attached to their posts
          3. Dating-profile photos
          4. Current avatar / cover (so the grid is never empty)

        Visibility: the owner sees everything; other viewers see only public
        gallery photos and public posts. Dating photos and avatar/cover are
        already public-facing.
        """
        # Lazy imports keep this module free of cross-domain import cycles.
        from backend.domains.posts.models import Post
        from backend.domains.profile.models import DatingProfile
        from backend.domains.identity.models import Account

        own = str(viewer_id) == str(account_id)
        items = []
        seen = set()

        def add(url, *, caption=None, source='gallery', post_id=None, created_at=None):
            if not isinstance(url, str):
                return
            u = url.strip()
            if not u or u in seen:
                return
            seen.add(u)
            items.append({
                'url': u,
                'caption': caption,
                'source': source,
                'post_id': post_id,
                'created_at': created_at,
            })

        # 1) Dedicated gallery uploads
        pq = UserPhoto.query.filter_by(account_id=account_id)
        if not own:
            pq = pq.filter_by(is_public=True)
        for p in pq.order_by(UserPhoto.created_at.desc()).all():
            add(p.url, caption=p.caption, source='gallery',
                created_at=p.created_at.isoformat() if p.created_at else None)

        # 2) Image media from the user's posts
        postq = Post.query.filter(
            Post.author_id == account_id,
            Post.deleted_at.is_(None),
            Post.moderation_status == 'approved',
        )
        if not own:
            postq = postq.filter(Post.audience == 'public')
        for post in postq.order_by(Post.created_at.desc()).all():
            ts = post.created_at.isoformat() if post.created_at else None
            for m in (post.media or []):
                if isinstance(m, str):
                    add(m, source='post', post_id=post.id, created_at=ts)
                elif isinstance(m, dict):
                    mtype = (m.get('type') or '').lower()
                    if mtype and mtype not in ('image', 'photo'):
                        continue  # skip videos / other media
                    add(m.get('url'), caption=m.get('caption'),
                        source='post', post_id=post.id, created_at=ts)

        # 3) Dating-profile photos
        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        for ph in (dp.photos if dp and dp.photos else []):
            if isinstance(ph, str):
                add(ph, source='dating')
            elif isinstance(ph, dict):
                add(ph.get('url'), caption=ph.get('caption'), source='dating')

        # 4) Avatar / cover fallback
        acct = Account.query.filter_by(id=account_id).first()
        if acct:
            add(getattr(acct, 'avatar', None), source='avatar')
            add(getattr(acct, 'cover_photo', None), source='cover')

        return success_response('Gallery loaded.', {
            'account_id': account_id,
            'total': len(items),
            'photos': items,
        })

    # ── Update ────────────────────────────────────────────────────────────────

    @staticmethod
    def update_photo(account, photo_id, data):
        if not data:
            return error_response('No data provided.')

        photo = UserPhoto.query.filter_by(
            id=photo_id, account_id=str(account.id)
        ).first()
        if not photo:
            return error_response('Photo not found.', status_code=404)

        account_id = str(account.id)

        if 'is_profile_photo' in data:
            if data['is_profile_photo']:
                UserPhoto.query.filter_by(
                    account_id=account_id, is_profile_photo=True
                ).update({'is_profile_photo': False}, synchronize_session=False)
                photo.is_profile_photo = True
                account.avatar = photo.url
            else:
                photo.is_profile_photo = False

        if 'is_cover_photo' in data:
            if data['is_cover_photo']:
                UserPhoto.query.filter_by(
                    account_id=account_id, is_cover_photo=True
                ).update({'is_cover_photo': False}, synchronize_session=False)
                photo.is_cover_photo = True
                account.cover_photo = photo.url
            else:
                photo.is_cover_photo = False

        if 'is_public' in data:
            photo.is_public = bool(data['is_public'])

        if 'caption' in data:
            photo.caption = (str(data['caption']).strip()[:300] or None) if data['caption'] else None

        if 'sort_order' in data:
            try:
                photo.sort_order = int(data['sort_order'])
            except (ValueError, TypeError):
                pass

        db.session.commit()
        return success_response('Photo updated.', photo.to_dict())

    # ── Delete ────────────────────────────────────────────────────────────────

    @staticmethod
    def delete_photo(account, photo_id):
        photo = UserPhoto.query.filter_by(
            id=photo_id, account_id=str(account.id)
        ).first()
        if not photo:
            return error_response('Photo not found.', status_code=404)

        was_profile = photo.is_profile_photo
        was_cover   = photo.is_cover_photo
        account_id  = str(account.id)

        db.session.delete(photo)
        db.session.flush()

        # Auto-promote the most-recent remaining photo as profile/cover
        if was_profile:
            nxt = UserPhoto.query.filter_by(account_id=account_id)\
                .order_by(UserPhoto.created_at.desc()).first()
            if nxt:
                nxt.is_profile_photo = True
                account.avatar = nxt.url
            else:
                account.avatar = None

        if was_cover:
            nxt = UserPhoto.query.filter_by(account_id=account_id)\
                .order_by(UserPhoto.created_at.desc()).first()
            if nxt and not nxt.is_cover_photo:
                nxt.is_cover_photo = True
                account.cover_photo = nxt.url
            elif not nxt:
                account.cover_photo = None

        db.session.commit()
        return success_response('Photo deleted.')

    # ── Count (used by onboarding validation) ─────────────────────────────────

    @staticmethod
    def get_counts(account_id):
        total    = UserPhoto.query.filter_by(account_id=account_id).count()
        has_prof = UserPhoto.query.filter_by(
            account_id=account_id, is_profile_photo=True).count() > 0
        has_cov  = UserPhoto.query.filter_by(
            account_id=account_id, is_cover_photo=True).count() > 0
        return success_response('Counts loaded.', {
            'total': total,
            'has_profile_photo': has_prof,
            'has_cover_photo': has_cov,
        })
