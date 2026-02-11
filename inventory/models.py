from datetime import datetime
from flask_login import UserMixin
from inventory.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


# ====================== USERS ====================== #
class User(db.Model, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)

    role = db.Column(db.String(50), nullable=False, default="User")
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # бързи данни за последния login
    login_count = db.Column(db.Integer, default=0, nullable=False)
    last_login_ip = db.Column(db.String(64), nullable=True)
    last_login_country = db.Column(db.String(100), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_user_agent = db.Column(db.String(255), nullable=True)

    # флаг за user-и създадени от админ които трябва да сменят парола
    force_password_change = db.Column(db.Boolean, default=False, nullable=False)
    password_changed_at = db.Column(db.DateTime, nullable=True)

    # по желание за брандинг ако решиш да го ползваш
    company_name = db.Column(db.String(150), nullable=True)

    # връзки към други таблици
    created_by = db.relationship("User", remote_side=[id], backref="created_users")
    transactions = db.relationship("Transaction", back_populates="user")

    login_events = db.relationship(
        "LoginEvent",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(LoginEvent.logged_in_at)",
    )

    def set_password(self, raw_password: str) -> None:
        # 1 място за логиката на парола за да не се дублира по route-ове
        self.password = generate_password_hash(raw_password, method="pbkdf2:sha256")
        self.password_changed_at = datetime.utcnow()
        self.force_password_change = False

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password, raw_password)


# ====================== LOGIN HISTORY ====================== #
class LoginEvent(db.Model):
    __tablename__ = "login_event"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    logged_in_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip_address = db.Column(db.String(64), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    # ако решиш да логваш и неуспешни опити остави го така
    success = db.Column(db.Boolean, default=True, nullable=False)

    user = db.relationship("User", back_populates="login_events")


# ====================== WAREHOUSE ====================== #
class Warehouse(db.Model):
    __tablename__ = "warehouse"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(150), nullable=True)

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    products = db.relationship("Product", backref="warehouse")
    stocks = db.relationship("Stock", back_populates="warehouse", cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", back_populates="warehouse")


# ====================== PRODUCT ====================== #
class Product(db.Model):
    __tablename__ = "product"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(100))

    # това е legacy поле вече истината е Stock
    quantity = db.Column(db.Integer, default=0)

    default_purchase_price = db.Column(db.Float, default=0.0)
    default_sell_price = db.Column(db.Float, default=0.0)

    image = db.Column(db.String(200))

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=True)

    stocks = db.relationship("Stock", back_populates="product", cascade="all, delete-orphan")
    items = db.relationship("TransactionItem", back_populates="product")


# ====================== PARTNER ====================== #
class Partner(db.Model):
    __tablename__ = "partner"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(50))  # Customer / Supplier / Both

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    transactions = db.relationship("Transaction", back_populates="partner")


# ====================== TRANSACTIONS ====================== #
class Transaction(db.Model):
    __tablename__ = "transaction"

    id = db.Column(db.Integer, primary_key=True)

    type = db.Column(db.String(20))  # Purchase / Sale
    date = db.Column(db.DateTime, default=datetime.utcnow)

    note = db.Column(db.String(500))
    locked = db.Column(db.Boolean, default=False)

    partner_id = db.Column(db.Integer, db.ForeignKey("partner.id"), nullable=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    items = db.relationship("TransactionItem", back_populates="transaction", cascade="all, delete-orphan")

    partner = db.relationship("Partner", back_populates="transactions")
    user = db.relationship("User", back_populates="transactions")
    warehouse = db.relationship("Warehouse", back_populates="transactions")


class TransactionItem(db.Model):
    __tablename__ = "transaction_item"

    id = db.Column(db.Integer, primary_key=True)

    transaction_id = db.Column(db.Integer, db.ForeignKey("transaction.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)

    # при Sale това се пълни от FIFO логиката
    cost_used = db.Column(db.Float, nullable=True)
    profit = db.Column(db.Float, nullable=True)

    product = db.relationship("Product", back_populates="items")
    transaction = db.relationship("Transaction", back_populates="items")

    purchase_lots = db.relationship("PurchaseLot", back_populates="transaction_item")


# ====================== STOCK ====================== #
class Stock(db.Model):
    __tablename__ = "stock"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)

    quantity = db.Column(db.Integer, default=0)

    # 1 ред за продукт + warehouse
    __table_args__ = (
        db.UniqueConstraint("product_id", "warehouse_id", name="uq_stock_product_warehouse"),
    )

    product = db.relationship("Product", back_populates="stocks")
    warehouse = db.relationship("Warehouse", back_populates="stocks")


# ====================== FIFO PURCHASE LOTS ====================== #
class PurchaseLot(db.Model):
    __tablename__ = "purchase_lot"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)

    quantity_remaining = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)

    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    transaction_item_id = db.Column(db.Integer, db.ForeignKey("transaction_item.id"), nullable=True)

    product = db.relationship("Product", backref="purchase_lots")
    transaction_item = db.relationship("TransactionItem", back_populates="purchase_lots")


# ====================== INVENTORY LEDGER ====================== #
class StockMovement(db.Model):
    __tablename__ = "stock_movement"

    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    transaction_id = db.Column(db.Integer, db.ForeignKey("transaction.id"), nullable=True)
    transaction_item_id = db.Column(db.Integer, db.ForeignKey("transaction_item.id"), nullable=True)

    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)

    direction = db.Column(db.String(10), nullable=False)  # IN / OUT
    quantity = db.Column(db.Integer, nullable=False)      # винаги позитивно
    unit_cost = db.Column(db.Float, nullable=True)
    unit_price = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    note = db.Column(db.String(255), nullable=True)

    transaction = db.relationship("Transaction", backref="stock_movements")
    transaction_item = db.relationship("TransactionItem", backref="stock_movements")
    product = db.relationship("Product", backref="stock_movements")
    warehouse = db.relationship("Warehouse", backref="stock_movements")


# ====================== FIFO LOT ALLOCATIONS ====================== #
class LotAllocation(db.Model):
    __tablename__ = "lot_allocation"

    id = db.Column(db.Integer, primary_key=True)

    transaction_item_id = db.Column(db.Integer, db.ForeignKey("transaction_item.id"), nullable=False)
    purchase_lot_id = db.Column(db.Integer, db.ForeignKey("purchase_lot.id"), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)

    transaction_item = db.relationship("TransactionItem", backref="lot_allocations")
    purchase_lot = db.relationship("PurchaseLot", backref="lot_allocations")

    # за да не се дублира една и съща връзка item->lot
    __table_args__ = (
        db.UniqueConstraint("transaction_item_id", "purchase_lot_id", name="uq_item_lot"),
    )


# ====================== SETTINGS ====================== #
class AppConfig(db.Model):
    __tablename__ = "app_config"

    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)

    company_name = db.Column(db.String(120), default="My Company")
    logo_path = db.Column(db.String(200))
    notifications_enabled = db.Column(db.Boolean, default=True)

    low_stock_threshold = db.Column(db.Integer, default=5)
    default_language = db.Column(db.String(10), default="en")
    currency = db.Column(db.String(10), default="EUR")
