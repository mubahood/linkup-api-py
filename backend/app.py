import os
import socket

from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

from backend.config import Config
from backend.models import db

jwt = JWTManager()
socketio = SocketIO()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

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
        async_mode='eventlet',
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
    from backend.routes.webhooks import webhooks_bp
    from backend.routes.admin import admin_bp
    from backend.routes.calls import calls_bp
    from backend.routes.ratings import ratings_bp
    from backend.routes.flutterwave import flutterwave_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(webhooks_bp)
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

    # Register Socket.IO call signaling events
    from backend.sockets.call_events import register_call_events
    register_call_events(socketio, app)

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
