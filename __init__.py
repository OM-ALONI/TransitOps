from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_bcrypt import Bcrypt
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()

login_manager.login_view = "auth.landing"
login_manager.login_message = "Sign in to continue."
login_manager.login_message_category = "warning"


def create_app(config_class=Config):
    # factory pattern — lets us create multiple app instances for testing
    # shoutout to the Flask docs for this pattern
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.vehicles import vehicles_bp
    from app.routes.drivers import drivers_bp
    from app.routes.trips import trips_bp
    from app.routes.maintenance import maintenance_bp
    from app.routes.fuel_expenses import fuel_bp
    from app.routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(vehicles_bp, url_prefix="/vehicles")
    app.register_blueprint(drivers_bp, url_prefix="/drivers")
    app.register_blueprint(trips_bp, url_prefix="/trips")
    app.register_blueprint(maintenance_bp, url_prefix="/maintenance")
    app.register_blueprint(fuel_bp, url_prefix="/fuel")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    from app.utils import sort_url, sort_icon
    app.jinja_env.globals["sort_url"] = sort_url
    app.jinja_env.globals["sort_icon"] = sort_icon

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    with app.app_context():
        db.create_all()

    return app
