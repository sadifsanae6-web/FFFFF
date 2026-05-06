from flask import Flask, redirect, url_for
from .db import db
from .routes.auth import auth_bp
from .routes.requests import requests_bp
from .routes.procurement import procurement_bp
from .routes.finance import finance_bp
from .routes.dashboard import dashboard_bp
from .routes.pilotage import pilotage_bp
from .services.seed import seed_database
from .utils.view_helpers import display_status, badge_class, format_priority
from .utils.auth_helpers import current_user as get_current_user
import os

SCHEMA_VERSION = '2026-procurement-v11-notes-planb-invoice'


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config['SECRET_KEY'] = 'smartpurchase-dev-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, 'smartpurchase.db')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db_path = os.path.join(app.instance_path, 'smartpurchase.db')
    version_path = os.path.join(app.instance_path, '.schema_version')
    current_version = open(version_path).read().strip() if os.path.exists(version_path) else ''
    if current_version != SCHEMA_VERSION and os.path.exists(db_path):
        os.remove(db_path)

    db.init_app(app)

    with app.app_context():
        from . import models
        db.create_all()
        seed_database()
        with open(version_path, 'w', encoding='utf-8') as fh:
            fh.write(SCHEMA_VERSION)

    app.register_blueprint(auth_bp)
    app.register_blueprint(requests_bp)
    app.register_blueprint(procurement_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pilotage_bp)

    @app.context_processor
    def inject_helpers():
        return dict(display_status=display_status, badge_class=badge_class, format_priority=format_priority, current_user=get_current_user(), session_user=get_current_user())

    @app.route('/')
    def home():
        return redirect(url_for('dashboard.index'))

    return app
