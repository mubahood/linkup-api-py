"""
App version routes: /v1/app/version — force-update check.
No auth required: this must be reachable before login, from the splash screen.
"""
from flask import Blueprint, request
from backend.domains.app_version.models import AppVersion
from backend.shared.app_brand import resolve_app_id
from backend.shared.utils.response import success_response, error_response

app_version_bp = Blueprint('v1_app_version', __name__, url_prefix='/v1/app')


@app_version_bp.route('/version', methods=['GET'])
def check_version():
    """
    ?platform=android|ios (required)
    ?build=<int>          (required — the app's own real installed build number)
    X-App header selects which app's config row to use; defaults to 'linkup'.
    """
    platform = (request.args.get('platform') or '').strip().lower()
    build = request.args.get('build', type=int)
    if platform not in ('android', 'ios'):
        return error_response('platform must be android or ios.')
    if build is None or build < 0:
        return error_response('build is required and must be a non-negative integer.')

    app_id = resolve_app_id()

    row = AppVersion.query.filter_by(app_id=app_id, platform=platform).first()
    if not row:
        # No config for this app/platform yet — never block on missing config.
        return success_response('No version config set.', {
            'latest_build': build,
            'latest_version_name': '',
            'min_supported_build': 0,
            'update_available': False,
            'force_update': False,
            'update_notes': '',
            'android_url': None,
            'ios_url': None,
        })

    return success_response('Version check complete.', row.to_dict(build))
