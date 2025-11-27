from flask import Flask, render_template, redirect, flash, request
from flask_login import LoginManager, login_required, logout_user, login_user
from config import Config
from models import db, User
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event  # TAMBAHKAN INI
from waitress import serve

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# === AKTIFKAN FOREIGN KEYS DI SQLITE (HARUS DI DALAM app_context!) ===
with app.app_context():
    @event.listens_for(db.engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

login_manager = LoginManager(app)
login_manager.login_view = 'index'
login_manager.login_message = 'Silakan login terlebih dahulu.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(id):
    return db.session.get(User, int(id))

# Import blueprint
from routes.admin_routes import bp as admin_bp
from routes.guru_routes import bp as guru_bp
from routes.siswa_routes import bp as siswa_bp

app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(guru_bp, url_prefix='/guru')
app.register_blueprint(siswa_bp, url_prefix='/siswa')

# ==========================================
# HALAMAN UTAMA + LOGIN SATU PINTU
# ==========================================
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login-unified', methods=['POST'])
def login_unified():
    username = request.form['username'].strip()
    password = request.form['password']
    role = request.form['role']

    user = User.query.filter_by(username=username, role=role).first()

    if user and check_password_hash(user.password, password):
        login_user(user)
        flash(f'Selamat datang, {user.nama or user.username}!', 'success')

        if role == 'admin':
            return redirect('/admin/dashboard')
        elif role == 'guru':
            return redirect('/guru/dashboard')
        elif role == 'siswa':
            return redirect('/siswa/dashboard')

    flash('Username, password, atau role salah!', 'danger')
    return redirect('/')

# ==========================================
# LOGOUT GLOBAL
# ==========================================
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda berhasil logout!', 'success')
    return redirect('/')

# ==========================================
# BUAT DATABASE + ADMIN DEFAULT
# ==========================================
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin', role='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            role='admin',
            nama='Administrator'
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin default dibuat → username: admin | password: admin123")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)