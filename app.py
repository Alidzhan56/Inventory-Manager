from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    UserMixin,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- Config ---
app.config['SECRET_KEY'] = 'supersecretkey'  # change in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Login Manager ---
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# --- Role decorator ---
def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Sales Agent')
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_users = db.relationship('User', backref=db.backref('creator', remote_side=[id]), lazy='dynamic')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- User loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

# Home / inventory
@app.route('/')
@login_required
def index():
    if current_user.role == 'Admin / Owner':
        products = Product.query.filter_by(owner_id=current_user.id).all()
    else:
        products = Product.query.filter_by(owner_id=current_user.created_by_id).all()
    return render_template('index.html', products=products, username=current_user.username)

# Add product
@app.route('/add', methods=['POST'])
@login_required
def add_product():
    name = request.form.get('name')
    quantity = request.form.get('quantity')
    if name and quantity:
        owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id
        new_product = Product(name=name, quantity=int(quantity), owner_id=owner_id)
        db.session.add(new_product)
        db.session.commit()
    return redirect(url_for('index'))

# Delete product
@app.route('/delete/<int:id>')
@login_required
@roles_required('Admin / Owner', 'Warehouse Manager')
def delete_product(id):
    product = Product.query.get(id)
    if product:
        db.session.delete(product)
        db.session.commit()
    return redirect(url_for('index'))

# Admin adds users (any role)
@app.route('/add_user', methods=['GET', 'POST'])
@login_required
@roles_required('Admin / Owner')
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'Sales Agent')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('add_user'))

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(
            username=username,
            password=hashed_pw,
            role=role,
            created_by_id=current_user.id
        )
        db.session.add(new_user)
        db.session.commit()
        flash(f'User {username} ({role}) created successfully.')
        return redirect(url_for('users'))

    return render_template('add_user.html')

# User list (Admin only)
@app.route('/users')
@login_required
@roles_required('Admin / Owner')
def users():
    users_list = User.query.filter_by(created_by_id=current_user.id).all()
    return render_template('users.html', users=users_list)

# Delete user (Admin only)
@app.route('/delete_user/<int:id>')
@login_required
@roles_required('Admin / Owner')
def delete_user(id):
    user = User.query.get(id)
    if user:
        if user.id == current_user.id:
            flash("You cannot delete your own account!")
            return redirect(url_for('users'))
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} deleted.')
    return redirect(url_for('users'))

# Admin self-registration (optional, only if you want public admin creation)
@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register_admin'))

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_admin = User(
            username=username,
            password=hashed_pw,
            role='Admin / Owner',
            created_by_id=None
        )
        db.session.add(new_admin)
        db.session.commit()
        flash('Admin account created! Please log in.')
        return redirect(url_for('login'))

    return render_template('register.html')


# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials.')
            return redirect(url_for('login'))

    return render_template('login.html')

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))

# Financial report (Admin only)
@app.route('/financial-report')
@login_required
@roles_required('Admin / Owner')
def financial_report():
    return render_template('financial.html')

# --- Initialize DB ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Create default Admin if not exists
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                password=generate_password_hash('admin123', method='pbkdf2:sha256'),
                role='Admin / Owner'
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin created: username=admin, password=admin123")

    app.run(debug=True)
