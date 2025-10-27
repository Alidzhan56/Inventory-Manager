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



# --- App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'  # change in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Image Upload Folder ---
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# --- Login Manager ---
login_manager = LoginManager()
login_manager.login_view = 'login'
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
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Sales Agent')
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_users = db.relationship('User', backref=db.backref('creator', remote_side=[id]), lazy='dynamic')

class Warehouse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(150), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    products = db.relationship('Product', backref='warehouse', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    price = db.Column(db.Float, nullable=False, default=0.0)
    sku = db.Column(db.String(50), nullable=False)   # not unique at DB level
    category = db.Column(db.String(100), nullable=True)
    # store only path relative to static: 'uploads/filename.jpg'
    image = db.Column(db.String(200), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'), nullable=True)

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
    type = db.Column(db.String(50), nullable=False)  # e.g. 'Supplier' or 'Customer'
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # use back_populates and choose a name that won't conflict
    transactions = db.relationship('Transaction', back_populates='partner', lazy='dynamic')


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))

    # partner relationship (the other side of Partner.transactions)
    partner = db.relationship('Partner', back_populates='transactions')


class AppConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120), nullable=False, default="My Company")
    logo_path = db.Column(db.String(200), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True)


#COMPANY  LOGO BY ADMIN
@app.route('/settings', methods=['GET', 'POST'])
@login_required
@roles_required('Admin / Owner')
def settings():
    config = AppConfig.query.first()
    if not config:
        config = AppConfig(company_name="My Company")
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
        flash("Settings updated successfully!", "success")
        return redirect(url_for('settings'))

    return render_template('settings.html', config=config)

@app.before_request
def load_company_settings():
    config = AppConfig.query.first()  # use the class defined in app.py
    if not config:
        # create default config if not found
        config = AppConfig(company_name="Inventory Manager", notifications_enabled=True)
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

# Index (shows products and add form)
@app.route('/')
@login_required
def index():
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id
    products = Product.query.filter_by(owner_id=owner_id).all()
    warehouses = Warehouse.query.filter_by(owner_id=owner_id).all()
    return render_template('index.html', products=products, warehouses=warehouses, username=current_user.username)

# Add product
@app.route('/add', methods=['POST'])
@login_required
def add_product():
    redirect_page = request.form.get('redirect_page', 'index')  # default redirect to index
    name = request.form.get('name')
    sku = request.form.get('sku')
    category = request.form.get('category')
    try:
        quantity = int(request.form.get('quantity', 0))
    except ValueError:
        quantity = 0
    try:
        price = float(request.form.get('price', 0))
    except ValueError:
        price = 0.0
    warehouse_id = request.form.get('warehouse_id')

    if not warehouse_id:
        flash("Please select a warehouse.")
        return redirect(url_for(redirect_page))

    try:
        warehouse_id = int(warehouse_id)
    except ValueError:
        flash("Invalid warehouse selected.")
        return redirect(url_for(redirect_page))

    image_file = request.files.get('image')
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id

    # SKU required
    if not sku:
        flash("Please provide SKU.")
        return redirect(url_for(redirect_page))

    # Check existing SKU
    existing = Product.query.filter_by(sku=sku, owner_id=owner_id, warehouse_id=warehouse_id).first()
    if existing:
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
            f'{redirect_page}.html',
            show_merge_modal=True,
            existing_product=existing,
            new_product_data=new_product_data,
            warehouses=warehouses,
            products=products
        )

    # Save image if uploaded
    image_relpath = None
    if image_file and image_file.filename != '':
        filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_relpath = f"uploads/{filename}"

    # Create product
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
    flash(f"Product '{name}' added successfully!")
    return redirect(url_for(redirect_page))



# Merge route (confirmed by user from modal) — increases existing quantity
@app.route('/merge', methods=['POST'])
@login_required
def merge_product():
    existing_id = request.form.get('existing_id')
    try:
        quantity = int(request.form.get('quantity', 0))
    except ValueError:
        quantity = 0
    product = Product.query.get(existing_id)
    if product:
        product.quantity = (product.quantity or 0) + quantity
        db.session.commit()
        flash(f"Product '{product.name}' quantity updated to {product.quantity}.")
    return redirect(url_for('index'))


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
        flash("Invalid quantity.")
        return redirect(url_for('index'))

    if quantity_to_sell > product.quantity:
        flash("Not enough stock to sell that quantity.")
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

    flash(f"Sold {quantity_to_sell} of '{product.name}'. Remaining stock: {product.quantity}.")
    return redirect(url_for('index'))


# Edit product (POST)
@app.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)

    # ensure current user can edit this product
    owner_allowed = (current_user.role == 'Admin / Owner' and product.owner_id == current_user.id) or \
                    (current_user.role != 'Admin / Owner' and product.owner_id == current_user.created_by_id)
    if not owner_allowed:
        abort(403)

    product.name = request.form.get('name')
    try:
        product.quantity = int(request.form.get('quantity', product.quantity))
    except ValueError:
        pass
    try:
        product.price = float(request.form.get('price', product.price))
    except ValueError:
        pass
    new_sku = request.form.get('sku')
    category = request.form.get('category')
    warehouse_id = request.form.get('warehouse_id')

    # check sku conflict in same owner+warehouse
    if new_sku and (new_sku != product.sku):
        owner_id = product.owner_id
        conflict = Product.query.filter_by(sku=new_sku, owner_id=owner_id, warehouse_id=warehouse_id).first()
        if conflict and conflict.id != product.id:
            flash("Another product with same SKU exists in this warehouse.")
            return redirect(url_for('index'))
        product.sku = new_sku

    product.category = category
    try:
        product.warehouse_id = int(warehouse_id) if warehouse_id else None
    except (ValueError, TypeError):
        pass

    # image
    image_file = request.files.get('image')
    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)
        product.image = f"uploads/{filename}"

    db.session.commit()
    flash(f"Product '{product.name}' updated.")
    return redirect(url_for('index'))


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
    flash(f"Product '{product.name}' deleted.")
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
    flash("You do not have permission to access Warehouses.")
    return redirect(url_for('index'))


@app.route('/add_warehouse', methods=['POST'])
@login_required
def add_warehouse():
    # Both Admins and Warehouse Managers can add warehouses
    if current_user.role not in ['Admin / Owner', 'Warehouse Manager']:
        flash("You do not have permission to add warehouses.")
        return redirect(url_for('index'))

    name = request.form.get('name')
    location = request.form.get('location')

    if not name:
        flash("Warehouse name is required.")
        return redirect(url_for('warehouses'))

    # Owner_id always set to the admin who created the warehouse
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else None

    new_w = Warehouse(name=name, location=location, owner_id=owner_id)
    db.session.add(new_w)
    db.session.commit()
    flash("Warehouse added successfully.")
    return redirect(url_for('warehouses'))


@app.route('/delete_warehouse/<int:id>')
@login_required
def delete_warehouse(id):
    # Only Admins can delete
    if current_user.role != 'Admin / Owner':
        flash("Only Admins can delete warehouses.")
        return redirect(url_for('warehouses'))

    w = Warehouse.query.get_or_404(id)
    linked = Product.query.filter_by(warehouse_id=w.id).first()

    if linked:
        flash("Cannot delete a warehouse that contains products. Move or delete products first.")
        return redirect(url_for('warehouses'))

    db.session.delete(w)
    db.session.commit()
    flash("Warehouse deleted successfully.")
    return redirect(url_for('warehouses'))

    # Check if products exist
    linked = Product.query.filter_by(warehouse_id=w.id).first()
    if linked:
        flash("Cannot delete warehouse that contains products. Move or delete products first.")
        return redirect(url_for('warehouses'))

    db.session.delete(w)
    db.session.commit()
    flash("Warehouse deleted.")
    return redirect(url_for('warehouses'))


# --- Partners (Customers / Suppliers) ---
@app.route('/partners', methods=['GET', 'POST'])
@login_required
def partners():
    # Only Admin / Owner can access
    if current_user.role != 'Admin / Owner':
        flash("You do not have permission to access Partners.")
        return redirect(url_for('index'))  # Redirect to home

    if request.method == 'POST':
        name = request.form.get('name')
        ptype = request.form.get('type')
        if not name or not ptype:
            flash('Please provide partner name and type.')
            return redirect(url_for('partners'))
        
        new_p = Partner(name=name, type=ptype, owner_id=current_user.id)
        db.session.add(new_p)
        db.session.commit()
        flash(f'{ptype} "{name}" added.')
        return redirect(url_for('partners'))
    
    partners = Partner.query.filter_by(owner_id=current_user.id).all()
    return render_template('partners.html', partners=partners)



# --- Transactions (Sales / Purchases) ---
@app.route('/transactions', methods=['GET'])
@login_required
def transactions():
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id
    txns = Transaction.query.join(Product).filter(Product.owner_id == owner_id).order_by(Transaction.date.desc()).all()
    products = Product.query.filter_by(owner_id=owner_id).all()
    partners = Partner.query.filter_by(owner_id=owner_id).all()
    warehouses = Warehouse.query.filter_by(owner_id=owner_id).all()
    return render_template('transactions.html', txns=txns, products=products, partners=partners, warehouses=warehouses)


@app.route('/transactions', methods=['POST'])
@login_required
def add_transaction():
    ttype = request.form.get('type')
    product_id = request.form.get('product_id')
    partner_id = request.form.get('partner_id')
    warehouse_id = request.form.get('warehouse_id')
    quantity = int(request.form.get('quantity', 0))

    product = Product.query.get(product_id)
    if not product:
        flash('Product not found.')
        return redirect(url_for('transactions'))

    if ttype == 'Sale':
        if quantity > product.quantity:
            flash('Not enough stock for sale.')
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
        total_price=total_price
    )
    db.session.add(txn)
    db.session.commit()

    flash(f'{ttype} recorded successfully.')
    return redirect(url_for('transactions'))



# --- User management (Admin only) ---
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
        new_user = User(username=username, password=hashed_pw, role=role, created_by_id=current_user.id)
        db.session.add(new_user)
        db.session.commit()
        flash(f'User {username} ({role}) created.')
        return redirect(url_for('users'))
    return render_template('add_user.html')

# --- User management (Admin only) ---
@app.route('/users')
@login_required
def users():
    if current_user.role != 'Admin / Owner':
        flash("You do not have permission to access Users.")
        return redirect(url_for('index'))

    users_list = User.query.filter_by(created_by_id=current_user.id).all()
    return render_template('users.html', users=users_list)

@app.route('/delete_user/<int:id>')
@login_required
@roles_required('Admin / Owner')
def delete_user(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("You cannot delete your own account!")
        return redirect(url_for('users'))
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} deleted.')
    return redirect(url_for('users'))


# --- Registration (optional) ---
@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register_admin'))
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_admin = User(username=username, password=hashed_pw, role='Admin / Owner')
        db.session.add(new_admin)
        db.session.commit()
        flash('Admin account created! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')


# --- Login/logout ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid credentials.')
        return redirect(url_for('login'))
    return render_template('login.html')



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
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
