"""
RunRush - Improved Flask Application
Main application factory with blueprints, security, and testing support.
"""

from flask import Flask, render_template
from config import get_config
from extensions import csrf, limiter, bcrypt
from db import get_db


def create_app(config_name=None):
    """
    Application factory.
    
    Args:
        config_name: Configuration name ('development', 'testing', 'production')
        
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Load configuration
    if config_name:
        from config import config
        app.config.from_object(config[config_name])
    else:
        app.config.from_object(get_config())
    
    # Initialize extensions
    csrf.init_app(app)
    limiter.init_app(app)
    bcrypt.init_app(app)
    
    # Initialize database
    with app.app_context():
        init_db()
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_commands(app)
    
    return app


def register_blueprints(app):
    """Register Flask blueprints."""
    from blueprints.auth import auth_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.runs import runs_bp
    from blueprints.social import social_bp
    from blueprints.admin import admin_bp
    from blueprints.api.v1 import api_v1_bp
    
    # Authentication routes
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Main app routes
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(runs_bp)
    app.register_blueprint(social_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # API routes
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')
    
    # Root route
    @app.route('/')
    def home():
        """Home page - redirect to dashboard or landing."""
        from flask import session, redirect, url_for
        if 'user_id' in session:
            return redirect(url_for('dashboard.index'))
        return render_template('landing.html')


def register_error_handlers(app):
    """Register error handlers."""
    
    @app.errorhandler(400)
    def bad_request(e):
        """Handle 400 Bad Request."""
        if app.config.get('DEBUG'):
            return str(e), 400
        return render_template('error.html', error='Bad Request', code=400), 400
    
    @app.errorhandler(403)
    def forbidden(e):
        """Handle 403 Forbidden."""
        return render_template('403.html'), 403
    
    @app.errorhandler(404)
    def not_found(e):
        """Handle 404 Not Found."""
        return render_template('error.html', error='Page Not Found', code=404), 404
    
    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        """Handle 429 Rate Limit Exceeded."""
        return render_template('error.html', 
                             error='Too Many Requests - Please try again later', 
                             code=429), 429
    
    @app.errorhandler(500)
    def internal_error(e):
        """Handle 500 Internal Server Error."""
        if app.config.get('DEBUG'):
            raise e
        return render_template('error.html', 
                             error='Internal Server Error', 
                             code=500), 500


def register_commands(app):
    """Register CLI commands."""
    
    @app.cli.command()
    def init_db_cmd():
        """Initialize the database."""
        init_db()
        print('Database initialized.')
    
    @app.cli.command()
    def create_admin():
        """Create an admin user."""
        from services.auth_service import register_user
        from db import get_db
        
        username = input('Admin username: ')
        pin = input('Admin PIN (4+ digits): ')
        
        success, user_id, error = register_user(username, pin)
        
        if not success:
            print(f'Error: {error}')
            return
        
        # Promote to admin
        conn = get_db()
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        print(f'Admin user created: {username} (ID: {user_id})')
    
    @app.cli.command()
    def migrate_pins():
        """Migrate plaintext PINs to hashed PINs."""
        from models.user import User
        from db import get_db
        
        conn = get_db()
        users = conn.execute("SELECT id, username, pin FROM users").fetchall()
        
        migrated = 0
        for user in users:
            pin = user['pin']
            
            # Check if already hashed (bcrypt hashes start with $2)
            if pin and not pin.startswith('$2'):
                # Hash the PIN
                pin_hash = User.hash_pin(pin)
                conn.execute("UPDATE users SET pin = ? WHERE id = ?", (pin_hash, user['id']))
                migrated += 1
                print(f"Migrated user: {user['username']}")
        
        conn.commit()
        conn.close()
        
        print(f'Migrated {migrated} users.')


def init_db():
    """Initialize database schema."""
    from app import init_db as original_init_db
    original_init_db()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
