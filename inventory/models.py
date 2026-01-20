from datetime import datetime
from flask_login import UserMixin
from inventory.extensions import db

# ====================== USERS ====================== #
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)

    role = db.Column(db.String(50), nullable=False, default="User")
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Quick "org branding" field (later we can move it to a Company table)
    company_name = db.Column(db.String(150))

    transactions = db.relationship("Transaction", back_populates="user")


# ====================== WAREHOUSE ====================== #
class Warehouse(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(150), nullable=True)

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Legacy relationship (product.warehouse_id). Keep it for now so old pages don't break.
    products = db.relationship("Product", backref="warehouse")

    # Real inventory lives here (product + warehouse + quantity)
    stocks = db.relationship("Stock", back_populates="warehouse", cascade="all, delete-orphan")

    # Useful later if you need warehouse-based queries fast
    transactions = db.relationship("Transaction", back_populates="warehouse")


# ====================== PRODUCT ====================== #
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(100))

    # Keep this for backward compatibility.
    # Once the UI is fully switched to Stock, we can stop using Product.quantity.
    quantity = db.Column(db.Integer, default=0)

    default_purchase_price = db.Column(db.Float, default=0.0)
    default_sell_price = db.Column(db.Float, default=0.0)

    image = db.Column(db.String(200))

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Legacy: product "belongs" to one warehouse (old design). Keep until full migration.
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=True)

    # New design: product can exist in many warehouses via Stock
    stocks = db.relationship("Stock", back_populates="product", cascade="all, delete-orphan")

    # Transaction lines
    items = db.relationship("TransactionItem", back_populates="product")


# ====================== PARTNER ====================== #
class Partner(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(50))  # customer / supplier / both

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    transactions = db.relationship("Transaction", back_populates="partner")


# ====================== TRANSACTIONS ====================== #
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    type = db.Column(db.String(20))  # Purchase / Sale
    date = db.Column(db.DateTime, default=datetime.utcnow)

    note = db.Column(db.String(500))
    locked = db.Column(db.Boolean, default=False)

    partner_id = db.Column(db.Integer, db.ForeignKey("partner.id"), nullable=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Lines
    items = db.relationship(
        "TransactionItem",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    # Relationships for easy template access
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

    # Sales only (filled for Sale lines)
    cost_used = db.Column(db.Float, nullable=True)
    profit = db.Column(db.Float, nullable=True)

    product = db.relationship("Product", back_populates="items")
    transaction = db.relationship("Transaction", back_populates="items")

    # Optional backref for FIFO lots created from purchase lines
    purchase_lots = db.relationship("PurchaseLot", back_populates="transaction_item")


# ====================== STOCK (Product in Warehouse) ====================== #
class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)

    quantity = db.Column(db.Integer, default=0)

    # One row per product per warehouse. Keeps the DB sane.
    __table_args__ = (
        db.UniqueConstraint("product_id", "warehouse_id", name="uq_stock_product_warehouse"),
    )

    product = db.relationship("Product", back_populates="stocks")
    warehouse = db.relationship("Warehouse", back_populates="stocks")


# ====================== FIFO PURCHASE LOTS ====================== #
class PurchaseLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)

    quantity_remaining = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)

    received_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Trace which purchase line created the lot (super helpful for audits/debugging)
    transaction_item_id = db.Column(db.Integer, db.ForeignKey("transaction_item.id"), nullable=True)

    product = db.relationship("Product", backref="purchase_lots")
    transaction_item = db.relationship("TransactionItem", back_populates="purchase_lots")


# ====================== SETTINGS ====================== #
class AppConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # who this config belongs to (one config per organization owner)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

    company_name = db.Column(db.String(120), default="My Company")
    logo_path = db.Column(db.String(200))
    notifications_enabled = db.Column(db.Boolean, default=True)

    # new settings
    low_stock_threshold = db.Column(db.Integer, default=5)
    default_language = db.Column(db.String(10), default="en")  # 'bg' or 'en'
    currency = db.Column(db.String(10), default="EUR")
