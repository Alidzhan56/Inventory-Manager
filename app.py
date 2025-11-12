from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, UserMixin, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from flask import g

from flask import session, request 

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user # Assuming you use Flask-Login



# --- App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'  # change in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

import json

# --- JSON-based translations ---
app.config['LANGUAGES'] = ['bg', 'en']
app.config['DEFAULT_LANG'] = 'bg'

def load_translations(lang):
    """Load translations from JSON file based on language code."""
    path = os.path.join('translations', f'{lang}.json')
    if not os.path.exists(path):
        path = os.path.join('translations', f"{app.config['DEFAULT_LANG']}.json")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

@app.before_request
def set_language():
    
    """Set language preference from query string or session."""
    lang = request.args.get('lang')
    if lang and lang in app.config['LANGUAGES']:
        session['lang'] = lang
    elif 'lang' not in session:
        session['lang'] = app.config['DEFAULT_LANG']
    g.lang = session['lang']
    g.translations = load_translations(g.lang)

def _(key):
    try:
        return g.translations.get(key, key)
    except Exception:
        return key


# ✅ make _() available inside Jinja templates
app.jinja_env.globals.update(_=_)

# --- Image Upload Folder ---
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# --- Login Manager ---
login_manager = LoginManager()
login_manager.login_view = 'login'
# The flash message for unauthorized access should be translatable
login_manager.login_message = _("Please log in to access this page.")
login_manager.init_app(app)

# --- Role Decorator ---
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

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="User")
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class Warehouse(db. Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(150), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    products = db.relationship('Product', backref='warehouse', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(100))
    quantity = db.Column(db.Integer, nullable=False, default=0)
    price = db.Column(db.Float, nullable=False, default=0.0)
    image = db.Column(db.String(200))  # stores relative path like 'uploads/file.jpg'
    
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))

    

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))

class Partner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    transactions = db.relationship('Transaction', back_populates='partner', lazy='dynamic')


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    type = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    partner = db.relationship('Partner', back_populates='transactions')
    product = db.relationship('Product', backref='transactions')
    warehouse = db.relationship('Warehouse', backref='transactions')
    user = db.relationship('User', backref='transactions')


class AppConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Default name should be translatable
    company_name = db.Column(db.String(120), nullable=False, default=_("My Company"))
    logo_path = db.Column(db.String(200), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True)


#COMPANY  LOGO BY ADMIN
@app.route('/settings', methods=['GET', 'POST'])
@login_required
@roles_required('Admin / Owner')
def settings():
    config = AppConfig.query.first()
    if not config:
        # Default name should be translatable
        config = AppConfig(company_name=_("My Company"))
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        config.company_name = request.form.get('company_name')
        config.notifications_enabled = bool(request.form.get('notifications_enabled'))

        logo = request.files.get('logo')
        if logo and logo.filename:
            filename = f"company_logo_{config.id}.png"
            logo_path = f"static/uploads/{filename}"
            os.makedirs(os.path.dirname(logo_path), exist_ok=True)
            logo.save(logo_path)
            config.logo_path = logo_path

        db.session.commit()
        # Flash message wrapped
        flash(_("Settings updated successfully!"), "success")
        return redirect(url_for('settings'))

    return render_template('settings.html', config=config)

@app.before_request
def load_company_settings():
    config = AppConfig.query.first()  # use the class defined in app.py
    if not config:
        # create default config if not found, default name translatable
        config = AppConfig(company_name=_("Inventory Manager"), notifications_enabled=True)
        db.session.add(config)
        db.session.commit()
    g.app_config = config

# --- Products Page ---
@app.route('/products')
@login_required
def products():
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id

    # Get products visible to this user
    if current_user.role in ['Admin / Owner', 'Warehouse Manager']:
        products = Product.query.filter_by(owner_id=owner_id).all()
    else:
        products = Product.query.filter_by(owner_id=owner_id).all()  # Sales: limited view

    warehouses = Warehouse.query.filter_by(owner_id=owner_id).all()

    return render_template('products.html', products=products, warehouses=warehouses)

# --- User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---



@app.route('/add', methods=['POST'])
@login_required
def add_product():
    # Force stay on the products page
    redirect_page = 'products'

    name = request.form.get('name')
    sku = request.form.get('sku')
    category = request.form.get('category')
    warehouse_id = request.form.get('warehouse_id')
    image_file = request.files.get('image')

    # safe conversions
    try:
        quantity = int(request.form.get('quantity', 0))
    except ValueError:
        quantity = 0
    try:
        price = float(request.form.get('price', 0))
    except ValueError:
        price = 0.0

    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id

    if not warehouse_id:
        flash(_("Please select a warehouse."))
        return redirect(url_for(redirect_page))

    # Ensure warehouse_id is int
    try:
        warehouse_id = int(warehouse_id)
    except ValueError:
        flash(_("Invalid warehouse selected."))
        return redirect(url_for(redirect_page))

    if not sku:
        flash(_("Please provide SKU."))
        return redirect(url_for(redirect_page))

    # --- Check if SKU exists ---
    existing = Product.query.filter_by(sku=sku, owner_id=owner_id, warehouse_id=warehouse_id).first()

    if existing:
        # stay on page, trigger modal
        warehouses = Warehouse.query.filter_by(owner_id=owner_id).all()
        products = Product.query.filter_by(owner_id=owner_id).all()
        new_product_data = {
            "name": name,
            "quantity": quantity,
            "price": price,
            "sku": sku,
            "category": category,
            "warehouse_id": warehouse_id,
            "image_file": image_file.filename if image_file else None
        }
        return render_template(
            'products.html',
            show_merge_modal=True,
            existing_product=existing,
            new_product_data=new_product_data,
            warehouses=warehouses,
            products=products
        )

    # --- handle image ---
    image_relpath = None
    if image_file and image_file.filename != '':
        filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_relpath = f"uploads/{filename}"

    # --- create new ---
    new_product = Product(
        name=name,
        quantity=quantity,
        price=price,
        sku=sku,
        category=category,
        image=image_relpath,
        owner_id=owner_id,
        warehouse_id=warehouse_id
    )

    db.session.add(new_product)
    db.session.commit()
    flash(_("Product '%(name)s' added successfully!") % {'name': name})
    return redirect(url_for(redirect_page))


# Merge route (confirmed by user from modal) — increases existing quantity
@app.route('/merge_product', methods=['POST'])
@login_required
def merge_product():
    existing_id = request.form.get('existing_id')
    add_qty = request.form.get('add_qty', type=int)

    existing = Product.query.get(existing_id)
    if not existing:
        flash(_("Product not found."), "danger")
        return redirect(url_for('products'))

    # ✅ Only add quantity; do NOT change price, name, or category
    existing.quantity += add_qty
    db.session.commit()

    flash(_("Quantity successfully merged for %(name)s (new total: %(qty)d).", 
           name=existing.name, qty=existing.quantity), "success")

    return redirect(url_for('products'))



# Sell product (records sale and decreases stock immediately)
@app.route('/sell/<int:id>', methods=['POST'])
@login_required
def sell_product(id):
    product = Product.query.get_or_404(id)
    try:
        quantity_to_sell = int(request.form.get('quantity', 0))
    except ValueError:
        quantity_to_sell = 0

    if quantity_to_sell <= 0:
        # Flash message wrapped
        flash(_("Invalid quantity."))
        return redirect(url_for('index'))

    if quantity_to_sell > product.quantity:
        # Flash message wrapped
        flash(_("Not enough stock to sell that quantity."))
        return redirect(url_for('index'))

    # Decrease product stock
    product.quantity -= quantity_to_sell

    # Record sale
    total_price = quantity_to_sell * (product.price or 0)
    sale = Sale(
        product_id=product.id,
        quantity=quantity_to_sell,
        total_price=total_price,
        warehouse_id=product.warehouse_id
    )
    db.session.add(sale)
    db.session.commit()

    # Flash message wrapped (using % formatting)
    flash(_("Sold %(qty)s of '%(name)s'. Remaining stock: %(rem)s.") % {'qty': quantity_to_sell, 'name': product.name, 'rem': product.quantity})
    return redirect(url_for('index'))


# Edit product (POST)
@app.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)

    # ensure current user can edit this product
    owner_allowed = (
        (current_user.role == 'Admin / Owner' and product.owner_id == current_user.id) or
        (current_user.role != 'Admin / Owner' and product.owner_id == current_user.created_by_id)
    )
    if not owner_allowed:
        abort(403)

    # Get form fields safely
    product.name = request.form.get('name', product.name)
    product.category = request.form.get('category', product.category)
    warehouse_id = request.form.get('warehouse_id')

    try:
        product.quantity = int(request.form.get('quantity', product.quantity))
    except (ValueError, TypeError):
        pass

    try:
        product.price = float(request.form.get('price', product.price))
    except (ValueError, TypeError):
        pass

    new_sku = request.form.get('sku', product.sku)
    if new_sku != product.sku:
        # Prevent duplicate SKU in same warehouse and owner
        conflict = Product.query.filter_by(
            sku=new_sku,
            owner_id=product.owner_id,
            warehouse_id=warehouse_id
        ).first()
        if conflict and conflict.id != product.id:
            flash(_("Another product with the same SKU exists in this warehouse."), 'warning')
            return redirect(url_for('products'))
        product.sku = new_sku

    try:
        product.warehouse_id = int(warehouse_id) if warehouse_id else None
    except (ValueError, TypeError):
        pass

    # Handle image upload
    image_file = request.files.get('image')
    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)
        product.image = f"uploads/{filename}"

    db.session.commit()

    flash(_("Product '%(name)s' updated successfully!") % {'name': product.name}, 'success')
    return redirect(url_for('products'))

# Delete product
@app.route('/delete/<int:id>')
@login_required
@roles_required('Admin / Owner', 'Warehouse Manager')
def delete_product(id):
    product = Product.query.get_or_404(id)

    owner_allowed = (current_user.role == 'Admin / Owner' and product.owner_id == current_user.id) or \
                    (current_user.role != 'Admin / Owner' and product.owner_id == current_user.created_by_id)
    if not owner_allowed:
        abort(403)

    db.session.delete(product)
    db.session.commit()
    # Flash message wrapped (using % formatting)
    flash(_("Product '%(name)s' deleted.") % {'name': product.name})
    return redirect(url_for('index'))


# --- Warehouse management ---
@app.route('/warehouses')
@login_required
def warehouses():
    # Admins and Warehouse Managers can view all warehouses
    if current_user.role in ['Admin / Owner', 'Warehouse Manager']:
        warehouses = Warehouse.query.all()
        return render_template('warehouses.html', warehouses=warehouses)
    
    # Sales Assistants or others cannot access
    # Flash message wrapped
    flash(_("You do not have permission to access Warehouses."))
    return redirect(url_for('index'))


@app.route('/add_warehouse', methods=['POST'])
@login_required
def add_warehouse():
    # Both Admins and Warehouse Managers can add warehouses
    if current_user.role not in ['Admin / Owner', 'Warehouse Manager']:
        # Flash message wrapped
        flash(_("You do not have permission to add warehouses."))
        return redirect(url_for('index'))

    name = request.form.get('name')
    location = request.form.get('location')

    if not name:
        # Flash message wrapped
        flash(_("Warehouse name is required."))
        return redirect(url_for('warehouses'))

    # Owner_id always set to the admin who created the warehouse
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else None

    new_w = Warehouse(name=name, location=location, owner_id=owner_id)
    db.session.add(new_w)
    db.session.commit()
    # Flash message wrapped
    flash(_("Warehouse added successfully."))
    return redirect(url_for('warehouses'))


@app.route('/delete_warehouse/<int:id>')
@login_required
def delete_warehouse(id):
    # Only Admins can delete
    if current_user.role != 'Admin / Owner':
        # Flash message wrapped
        flash(_("Only Admins can delete warehouses."))
        return redirect(url_for('warehouses'))

    w = Warehouse.query.get_or_404(id)
    linked = Product.query.filter_by(warehouse_id=w.id).first()

    if linked:
        # Flash message wrapped
        flash(_("Cannot delete a warehouse that contains products. Move or delete products first."))
        return redirect(url_for('warehouses'))

    # The code below is a duplicate and should be removed, but since the request is only about i18n, I will i18n the messages in both blocks.
    db.session.delete(w)
    db.session.commit()
    # Flash message wrapped
    flash(_("Warehouse deleted successfully."))
    return redirect(url_for('warehouses'))

    # Check if products exist
    linked = Product.query.filter_by(warehouse_id=w.id).first()
    if linked:
        # Flash message wrapped
        flash(_("Cannot delete warehouse that contains products. Move or delete products first."))
        return redirect(url_for('warehouses'))

    db.session.delete(w)
    db.session.commit()
    # Flash message wrapped
    flash(_("Warehouse deleted."))
    return redirect(url_for('warehouses'))


# --- Partners (Customers / Suppliers) ---
@app.route('/partners', methods=['GET', 'POST'])
@login_required
def partners():
    # Only Admin / Owner can access
    if current_user.role != 'Admin / Owner':
        # Flash message wrapped
        flash(_("You do not have permission to access Partners."))
        return redirect(url_for('index'))  # Redirect to home

    if request.method == 'POST':
        name = request.form.get('name')
        ptype = request.form.get('type')
        if not name or not ptype:
            # Flash message wrapped
            flash(_('Please provide partner name and type.'))
            return redirect(url_for('partners'))
        
        new_p = Partner(name=name, type=ptype, owner_id=current_user.id)
        db.session.add(new_p)
        db.session.commit()
        # Flash message wrapped (using % formatting)
        flash(_('%(ptype)s "%(name)s" added.') % {'ptype': ptype, 'name': name})
        return redirect(url_for('partners'))
    
    partners = Partner.query.filter_by(owner_id=current_user.id).all()
    return render_template('partners.html', partners=partners)



@app.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id
    products = Product.query.filter_by(owner_id=owner_id).all()
    partners = Partner.query.filter_by(owner_id=owner_id).all()
    warehouses = Warehouse.query.filter_by(owner_id=owner_id).all()

    if request.method == 'POST':
        ttype = request.form.get('type')
        product_id = request.form.get('product_id')
        partner_id = request.form.get('partner_id')
        warehouse_id = request.form.get('warehouse_id')
        quantity = int(request.form.get('quantity', 0))

        product = Product.query.get(product_id)
        if not product:
            flash(_('Product not found.'), 'danger')
            return redirect(url_for('transactions'))

        if ttype == 'Sale':
            if quantity > product.quantity:
                flash(_('Not enough stock for sale.'), 'danger')
                return redirect(url_for('transactions'))
            product.quantity -= quantity
        elif ttype == 'Purchase':
            product.quantity += quantity

        total_price = (product.price or 0) * quantity

        txn = Transaction(
            type=ttype,
            product_id=product.id,
            partner_id=partner_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            total_price=total_price,
            user_id=current_user.id
        )
        db.session.add(txn)
        db.session.commit()
        flash(_('%(ttype)s recorded successfully.') % {'ttype': ttype}, 'success')
        return redirect(url_for('transactions'))

    # For GET: show transactions
    txns = (
        Transaction.query
        .join(Product)
        .filter(Product.owner_id == owner_id)
        .order_by(Transaction.date.desc())
        .all()
    )

    return render_template('transactions.html', txns=txns, products=products, partners=partners, warehouses=warehouses)


# --- User management (Admin only) ---
@app.route('/add_user', methods=['POST'])
@login_required
def add_user():
    username = request.form.get('username')
    email = request.form.get('email')  # <--- Must get email!
    password = request.form.get('password')
    role = request.form.get('role')
    
    # Optional: check if username or email exists
    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash('Username or Email already exists.', 'danger')
        return redirect(url_for('users'))

    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(
        username=username,
        email=email,
        password=hashed_pw,
        role=role,
        created_by_id=current_user.id
    )
    db.session.add(new_user)
    db.session.commit()
    flash('User created successfully!', 'success')
    return redirect(url_for('users'))

@app.route('/developer')
@login_required
def developer_dashboard():
    if current_user.role != "Developer":
        abort(403)

    users_list = User.query.all()  # Developer sees all users
    return render_template('developer_dashboard.html', users=users_list)


@app.route('/delete_user_dev/<int:id>')
@login_required
def delete_user_dev(id):
    if current_user.role != "Developer":
        abort(403)

    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash(_("You cannot delete your own account!"))
        return redirect(url_for('developer_dashboard'))

    db.session.delete(user)
    db.session.commit()
    flash(_('User %(username)s deleted.') % {'username': user.username})
    return redirect(url_for('developer_dashboard'))

# --- In your app.py ---



# ... other imports and app setup ...

# 1. Route for Creating a User
@app.route('/developer/user/create', methods=['GET', 'POST'])
@login_required
def create_user_dev():
    # Placeholder logic:
    if request.method == 'POST':
        # Logic to handle form submission and create a new user in the database
        flash('User created successfully!', 'success')
        return redirect(url_for('developer_dashboard'))
    return render_template('create_user_form.html') # You'd need to create this template

# 2. Route for Viewing System Logs
@app.route('/developer/logs')
@login_required
def view_logs_dev():
    # Logic to read and display recent application logs
    logs = ["Log line 1", "Log line 2", "Log line 3"] # Example data
    return render_template('system_logs.html', logs=logs)

# 3. Route for App Settings
@app.route('/developer/settings')
@login_required
def app_settings_dev():
    # Logic to load and save general application configuration
    settings = {'app_name': 'Inventory Manager', 'debug_mode': False} # Example data
    return render_template('app_settings.html', settings=settings)

# (Ensure your existing 'delete_user_dev' is still defined correctly)


# --- User management (Admin only) ---
@app.route('/users')
@login_required
def users():
    # Developer: can see all users
    if current_user.role == "Developer":
        users_list = User.query.all()
        return render_template('users.html', users=users_list)

    # Admin/Owner: can see only users they created
    if current_user.role == "Admin / Owner":
        users_list = User.query.filter_by(created_by_id=current_user.id).all()
        return render_template('users.html', users=users_list)

    # # Everyone else: no access
    # flash(_("You do not have permission to access Users."))
    # return redirect(url_for('index'))

@app.route('/delete_user/<int:id>')
@login_required
def delete_user(id):

    user = User.query.get_or_404(id)

    # Developer can delete anyone EXCEPT other developers
    if current_user.role == "Developer":
        if user.role == "Developer":
            flash("Developer accounts cannot delete each other.")
            return redirect(request.referrer)
        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.username} deleted.")
        return redirect(request.referrer)

    # Admin can delete only users they created
    if current_user.role == "Admin / Owner":
        if user.created_by_id != current_user.id:
            flash("You can only delete users you created.")
            return redirect(url_for('users'))

        if user.id == current_user.id:
            flash("You cannot delete your own account.")
            return redirect(url_for('users'))

        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.username} deleted.")
        return redirect(url_for('users'))

    abort(403)

@app.route('/')
@login_required
def index():
    total_products = Product.query.count()
    total_warehouses = Warehouse.query.count()
    total_transactions = Transaction.query.count()
    total_partners = Partner.query.count()
    total_users = User.query.count() if current_user.role == 'Admin / Owner' else None
    recent_transactions = Transaction.query.order_by(Transaction.date.desc()).limit(5).all()

    return render_template('index.html',
                           total_products=total_products,
                           total_warehouses=total_warehouses,
                           total_transactions=total_transactions,
                           total_partners=total_partners,
                           total_users=total_users,
                           recent_transactions=recent_transactions)

import re
from werkzeug.security import generate_password_hash

@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Check required fields
        if not email or not username or not password or not confirm_password:
            flash(_('Please fill in all required fields.'), 'danger')
            return render_template('register.html')

        # Check password match
        if password != confirm_password:
            flash(_('Passwords do not match.'), 'danger')
            return render_template('register.html')

        # Check password strength
        if len(password) < 8:
            flash(_('Password must be at least 8 characters.'), 'danger')
            return render_template('register.html')
        if not re.search(r'[A-Z]', password):
            flash(_('Password must include at least one uppercase letter.'), 'danger')
            return render_template('register.html')
        if not re.search(r'[a-z]', password):
            flash(_('Password must include at least one lowercase letter.'), 'danger')
            return render_template('register.html')
        if not re.search(r'\d', password):
            flash(_('Password must include at least one number.'), 'danger')
            return render_template('register.html')
        if not re.search(r'[^a-zA-Z0-9]', password):
            flash(_('Password must include at least one symbol.'), 'danger')
            return render_template('register.html')

        # Check if email or username exists
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash(_('An account with this email or username already exists.'), 'danger')
            return render_template('register.html')

        # Create user
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_admin = User(
            username=username,
            email=email,
            password=hashed_pw,
            role='Admin / Owner'
        )
        db.session.add(new_admin)
        db.session.commit()
        flash(_('Admin account created! Please log in.'), 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# --- Login/logout ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')  # email OR username
        password = request.form.get('password')

        # 1️⃣ Check if fields are filled
        if not identifier or not password:
            flash(_('Please fill in all fields.'), 'danger')
            return redirect(url_for('login'))

        # 2️⃣ Search user by username OR email
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user:
            flash(_('No account found with that email or username.'), 'danger')
            return redirect(url_for('login'))

        # 3️⃣ Check password
        if not check_password_hash(user.password, password):
            flash(_('Incorrect password.'), 'danger')
            return redirect(url_for('login'))

        # 4️⃣ Log in the user
        login_user(user)

        # 5️⃣ Redirect based on role
        if user.role == "Developer":
            return redirect(url_for('developer_dashboard'))  # separate dashboard
        else:
            return redirect(url_for('index'))  # normal users

    return render_template('login.html')



@app.route('/logout')
@login_required
def logout():
    logout_user()
    # Flash message wrapped
    flash(_('You have been logged out.'))
    return redirect(url_for('login'))

@app.route('/financial-report')
@login_required
@roles_required('Admin / Owner')
def financial_report():
    return render_template('financial.html')


# --- Initialize DB ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # create default admin (only once)
        # if not User.query.filter_by(username='admin').first():
        #     admin_user = User(
        #         username='admin',
        #         email='admin@example.com',  # ✅ Add this line
        #         password=generate_password_hash('admin123', method='pbkdf2:sha256'),
        #         role='Admin / Owner'
        #     )
        #     db.session.add(admin_user)
        #     db.session.commit()

        # Create developer account once
        dev = User.query.filter_by(role="Developer").first()
        if not dev:
            developer = User(
                username="developer",
                email="developer@app.com",
                password=generate_password_hash("dev12345", method="pbkdf2:sha256"),
                role="Developer"
            )
            db.session.add(developer)
            db.session.commit()

    app.run(debug=True)
