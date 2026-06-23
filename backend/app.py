import os
import socket
import subprocess
import shutil

from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

from backend.config import Config
from backend.models import db

jwt = JWTManager()
socketio = SocketIO()


def _ensure_turn_server():
    """Start coturn (TURN/STUN relay) if it isn't already running.
    Required for WebRTC calls between devices behind NAT or on emulators.
    """
    turnserver = shutil.which('turnserver')
    if not turnserver:
        print('[TURN] coturn not found — skipping TURN server startup', flush=True)
        return

    # Check if already running
    try:
        result = subprocess.run(['pgrep', '-f', 'turnserver'], capture_output=True)
        if result.returncode == 0:
            print('[TURN] coturn already running', flush=True)
            return
    except Exception:
        pass

    turn_user = os.environ.get('TURN_USER', 'linkup')
    turn_pass = os.environ.get('TURN_PASSWORD', 'linkup2026')
    turn_port = os.environ.get('TURN_PORT', '3478')

    cmd = [
        turnserver,
        '--no-tls', '--no-dtls',
        '--fingerprint',
        '--realm', 'linkup.app',
        '--lt-cred-mech',
        f'--user={turn_user}:{turn_pass}',
        f'--listening-port={turn_port}',
        '--log-file=/tmp/coturn.log',
        '--simple-log',
        '--no-cli',
        '--no-stdout-log',
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f'[TURN] coturn started on port {turn_port} '
              f'(user={turn_user})', flush=True)
    except Exception as e:
        print(f'[TURN] Failed to start coturn: {e}', flush=True)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    # Take ownership of unhandled exceptions so the API always returns a JSON
    # envelope instead of a Werkzeug HTML debugger page, even under FLASK_DEBUG
    # (T-API-042). Full tracebacks are still logged via the global handler.
    app.config['PROPAGATE_EXCEPTIONS'] = False

    db.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={
        r"/api/*": {"origins": "*"},
        r"/v1/*": {"origins": "*"},
        r"/socket.io/*": {"origins": "*"},
    })

    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode='threading',  # eventlet is broken on Python 3.14
        ping_timeout=60,
        ping_interval=25,
        logger=False,
        engineio_logger=False,
    )

    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)

    # ─── Legacy blueprints (backward compat — mobile app) ───────────────
    from backend.routes.auth import auth_bp
    from backend.routes.profile import profile_bp
    from backend.routes.wallet import wallet_bp
    from backend.routes.chat import chat_bp
    from backend.routes.admin import admin_bp
    from backend.routes.calls import calls_bp
    from backend.routes.ratings import ratings_bp
    from backend.routes.flutterwave import flutterwave_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(calls_bp)
    app.register_blueprint(ratings_bp)
    app.register_blueprint(flutterwave_bp)

    # ─── LinkUp v1 domain blueprints ───────────────────────────────────
    from backend.domains.identity.routes import identity_bp
    from backend.domains.profile.routes import profile_bp as v1_profile_bp
    from backend.domains.interest.routes import interest_bp
    from backend.domains.links.routes import links_bp
    from backend.domains.sparks.routes import sparks_bp
    from backend.domains.hubs.routes import hubs_bp
    from backend.domains.chat.routes import chat_v1_bp
    from backend.domains.jobs.routes import jobs_bp
    from backend.domains.events.routes import events_bp
    from backend.domains.notifications.routes import notifications_bp
    from backend.domains.safety.routes import safety_bp
    from backend.domains.search.routes import search_bp
    from backend.domains.reference.routes import reference_bp
    from backend.domains.feed.routes import feed_bp
    from backend.domains.wallet.routes import wallet_bp as wallet_v1_bp
    from backend.domains.wallet.gift_routes import gifts_bp
    from backend.domains.endorsements.routes import endorsements_bp
    from backend.domains.admin.routes import admin_v1_bp
    from backend.domains.mentorship.routes import mentorship_bp
    from backend.domains.photos.routes import photos_bp
    from backend.domains.posts.routes import posts_bp

    app.register_blueprint(identity_bp)
    app.register_blueprint(v1_profile_bp)
    app.register_blueprint(interest_bp)
    app.register_blueprint(links_bp)
    app.register_blueprint(sparks_bp)
    app.register_blueprint(hubs_bp)
    app.register_blueprint(chat_v1_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(safety_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(reference_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(wallet_v1_bp)
    app.register_blueprint(gifts_bp)
    app.register_blueprint(endorsements_bp)
    app.register_blueprint(admin_v1_bp)
    app.register_blueprint(mentorship_bp)
    app.register_blueprint(photos_bp)
    app.register_blueprint(posts_bp)

    # Register Socket.IO call signaling events
    from backend.sockets.call_events import register_call_events
    register_call_events(socketio, app)

    # Register realtime chat + presence events (T-API-046/047/048)
    from backend.sockets.chat_events import register_chat_events
    register_chat_events(socketio, app)

    # Ensure TURN server (coturn) is running for WebRTC relay
    _ensure_turn_server()

    from backend.utils.response import error_response

    # ─── Health endpoint ───────────────────────────────────────────────
    @app.route('/v1/health', methods=['GET'])
    def v1_health():
        try:
            db.session.execute(db.text('SELECT 1'))
            db_status = 'ok'
        except Exception as e:
            db_status = f'error: {str(e)}'
        return jsonify({
            'code': 1,
            'message': 'LinkUp API is running.',
            'data': {
                'api': 'ok',
                'database': db_status,
                'version': '1.0.0',
                'phase': 'Phase 0 — Foundation',
                'server': 'Flask 3.0 + MySQL',
            }
        }), 200

    # Deliberate-failure probe (debug only) — verifies the JSON error envelope.
    if os.getenv('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes', 'on'):
        @app.route('/v1/_debug/boom', methods=['GET'])
        def _debug_boom():
            raise RuntimeError('intentional failure for T-API-042 envelope test')

    # ─── OpenAPI spec + route catalog (T-API-037) ──────────────────────
    @app.route('/v1/openapi.json', methods=['GET'])
    def v1_openapi():
        from backend.shared.openapi import generate_spec
        return jsonify(generate_spec(app))

    @app.route('/v1/_catalog', methods=['GET'])
    def v1_catalog():
        from backend.shared.openapi import generate_spec
        spec = generate_spec(app)
        catalog = {}
        for path, item in spec['paths'].items():
            for method in item:
                catalog.setdefault(item[method]['tags'][0], []).append(f'{method.upper()} {path}')
        total = sum(len(v) for v in catalog.values())
        return jsonify({'code': 1, 'message': f'{total} endpoints across {len(catalog)} domains',
                        'data': {k: sorted(v) for k, v in sorted(catalog.items())}})

    @app.errorhandler(404)
    def handle_404(_error):
        if request.path.startswith('/api/') or request.path.startswith('/v1/'):
            return error_response("Endpoint not found.", status_code=404)
        return _error

    @app.errorhandler(405)
    def handle_405(_error):
        if request.path.startswith('/api/') or request.path.startswith('/v1/'):
            return error_response("Method not allowed for this endpoint.", status_code=405)
        return _error

    # ─── Global exception envelope (T-API-042) ─────────────────────────
    # An API must never hand a client a Werkzeug HTML debugger page. We take
    # ownership of unhandled exceptions (PROPAGATE_EXCEPTIONS=False, set in
    # create_app) so this fires even under FLASK_DEBUG; the full traceback is
    # still logged for developers.
    import traceback as _traceback
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(Exception)
    def handle_uncaught(error):
        # Preserve intended HTTP errors (404/405/403/...) and their messages.
        if isinstance(error, HTTPException):
            if request.path.startswith('/api/') or request.path.startswith('/v1/'):
                return error_response(error.description or error.name,
                                      status_code=error.code or 500)
            return error
        # Truly unexpected: log the stack, return a clean JSON envelope for API.
        app.logger.error('Unhandled exception on %s %s\n%s',
                         request.method, request.path, _traceback.format_exc())
        try:
            db.session.rollback()
        except Exception:
            pass
        if request.path.startswith('/api/') or request.path.startswith('/v1/'):
            return error_response("Something went wrong. Please try again.",
                                  status_code=500)
        return error_response("Internal server error.", status_code=500)

    # Serve uploaded files
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route('/storage/<path:filename>')
    def serve_storage(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    admin_build = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'build')

    @app.route('/')
    def serve_admin():
        if os.path.isfile(os.path.join(admin_build, 'index.html')):
            return send_from_directory(admin_build, 'index.html')
        return {'status': 'ok', 'service': 'LinkUp API', 'version': '1.0',
                'note': 'Admin frontend not built yet.'}

    @app.route('/assets/<path:filename>')
    def serve_admin_assets(filename):
        return send_from_directory(os.path.join(admin_build, 'assets'), filename)

    @app.route('/<path:path>')
    def serve_admin_spa(path):
        if path.startswith('api/') or path.startswith('v1/'):
            from flask import abort
            abort(404)
        file_path = os.path.join(admin_build, path)
        if os.path.isfile(file_path):
            return send_from_directory(admin_build, path)
        if os.path.isfile(os.path.join(admin_build, 'index.html')):
            return send_from_directory(admin_build, 'index.html')
        return {'status': 'ok', 'service': 'LinkUp API', 'version': '1.0'}

    return app


app = create_app()


if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()

    port = Config.SERVER_PORT

    print('=' * 70)
    print('[*] LinkUp API Starting...')
    print(f'   Backend API (v1): http://127.0.0.1:{port}/v1')
    print(f'   Health check:     http://127.0.0.1:{port}/v1/health')
    print(f'   Network access:   http://{local_ip}:{port}/v1')
    print(f'   Database:         MySQL (linkup) via MAMP socket')
    print('=' * 70)

    socketio.run(
        app,
        host=Config.SERVER_HOST,
        port=port,
        debug=os.getenv('FLASK_DEBUG', 'true').lower() == 'true',
        allow_unsafe_werkzeug=True,
    )
