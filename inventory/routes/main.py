from datetime import datetime
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import extract, func

from inventory.extensions import db
from inventory.models import Product, Warehouse, Transaction, Partner

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def index():
    # Dashboard Card Data
    total_products = Product.query.count()
    total_warehouses = Warehouse.query.count()
    total_transactions = Transaction.query.count()
    total_partners = Partner.query.count()

    # Transactions per month (Chart data)
    months = []
    counts = []

    for m in range(1, 13):
        month_name = datetime(2024, m, 1).strftime("%b")
        months.append(month_name)

        monthly_count = db.session.query(func.count(Transaction.id))\
            .filter(extract('month', Transaction.date) == m).scalar() or 0

        counts.append(monthly_count)

    # Product categories (Chart data)
    categories = []
    category_counts = []

    category_data = db.session.query(Product.category, func.count(Product.id))\
        .group_by(Product.category).all()

    for cat, cnt in category_data:
        categories.append(cat or "Unknown")
        category_counts.append(cnt)

    # Render template with data
    return render_template(
        "index.html",
        total_products=total_products,
        total_warehouses=total_warehouses,
        total_transactions=total_transactions,
        total_partners=total_partners,
        transaction_months=months,
        transaction_counts=counts,
        product_categories=categories,
        product_counts=category_counts
    )