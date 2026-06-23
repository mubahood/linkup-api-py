from flask import Blueprint, request
from backend.shared.auth.decorators import lu_jwt_required
from backend.domains.photos.service import PhotoService

photos_bp = Blueprint('v1_photos', __name__, url_prefix='/v1/photos')


@photos_bp.route('', methods=['POST'])
@lu_jwt_required
def upload_photo(account):
    """Upload a new photo. Multipart: field=photo, plus optional form fields."""
    return PhotoService.upload(account, request)


@photos_bp.route('', methods=['GET'])
@lu_jwt_required
def list_own_photos(account):
    """List all of the authenticated user's photos (including private)."""
    return PhotoService.list_photos(str(account.id), own=True)


@photos_bp.route('/account/<account_id>', methods=['GET'])
@lu_jwt_required
def list_user_photos(account, account_id):
    """List another account's public photos."""
    return PhotoService.list_photos(account_id, own=False)


@photos_bp.route('/gallery', methods=['GET'])
@lu_jwt_required
def my_gallery(account):
    """Every photo the caller has ever shared (uploads + post media + dating)."""
    return PhotoService.list_gallery(str(account.id), str(account.id))


@photos_bp.route('/gallery/<account_id>', methods=['GET'])
@lu_jwt_required
def user_gallery(account, account_id):
    """Every public photo another user has ever shared, newest first."""
    return PhotoService.list_gallery(str(account.id), account_id)


@photos_bp.route('/counts', methods=['GET'])
@lu_jwt_required
def photo_counts(account):
    """Return photo count + has_profile_photo + has_cover_photo for the caller."""
    return PhotoService.get_counts(str(account.id))


@photos_bp.route('/<photo_id>', methods=['PATCH'])
@lu_jwt_required
def update_photo(account, photo_id):
    """Update photo metadata: is_profile_photo, is_cover_photo, is_public, caption."""
    return PhotoService.update_photo(account, photo_id, request.get_json(silent=True))


@photos_bp.route('/<photo_id>', methods=['DELETE'])
@lu_jwt_required
def delete_photo(account, photo_id):
    """Delete a photo."""
    return PhotoService.delete_photo(account, photo_id)
