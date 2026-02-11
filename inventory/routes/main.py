# inventory/routes/main.py
from datetime import datetime, timedelta
from flask import Blueprint, render_template, g, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func

from inventory.extensions import db
from inventory.models import Product, Warehouse, Transaction, Partner, TransactionItem, Stock

bp = Blueprint("main", __name__)


def _get_owner_id():
    # тук решавам за коя фирма (owner) работи текущия user
    # developer не е вързан към фирма
    if current_user.role == "Developer":
        return None
    if current_user.role == "Admin / Owner":
        return current_user.id
    return current_user.created_by_id


def _month_start(dt: datetime) -> datetime:
    # правя дата за началото на месеца
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(dt: datetime, months: int) -> datetime:
    # добавям месеци без допълнителни библиотеки
    # винаги връщам 1-во число на месеца 00:00
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    return dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


# --------------------------
# ПУБЛИЧНА LANDING СТРАНИЦА
# --------------------------
@bp.route("/")
def landing():
    # ако е логнат го пращам към правилния dashboard
    if current_user.is_authenticated:
        if (current_user.role or "").strip() == "Developer":
            return redirect(url_for("users.developer_dashboard"))
        return redirect(url_for("main.index"))

    # ако не е логнат показвам landing
    return render_template("landing.html")


# --------------------------
# DASHBOARD СЛЕД LOGIN
# --------------------------
@bp.route("/dashboard")
@login_required
def index():
    # developer си има отделно табло
    if (current_user.role or "").strip() == "Developer":
        return redirect(url_for("users.developer_dashboard"))

    owner_id = _get_owner_id()

    # ако не мога да намеря owner_id най безопасното е logout
    if not owner_id:
        return redirect(url_for("auth.logout"))

    # -------------------- Базови бройки за фирмата -------------------- #
    total_products = Product.query.filter_by(owner_id=owner_id).count()
    total_warehouses = Warehouse.query.filter_by(owner_id=owner_id).count()
    total_partners = Partner.query.filter_by(owner_id=owner_id).count()

    # транзакциите ги смятам през warehouse за да е сигурно org scoping
    total_transactions = (
        Transaction.query
        .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
        .filter(Warehouse.owner_id == owner_id)
        .count()
    )

    # -------------------- Дати за този месец и 12 месеца назад -------------------- #
    now = datetime.utcnow()
    this_month_start = _month_start(now)
    next_month_start = _add_months(this_month_start, 1)

    # последните 12 месеца включително текущия
    start_12 = _add_months(this_month_start, -11)

    # -------------------- Пари и бройки за този месец -------------------- #
    # взимам id-та на транзакциите този месец за тази фирма
    base_txn_ids = (
        db.session.query(Transaction.id)
        .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
        .filter(Warehouse.owner_id == owner_id)
        .filter(Transaction.date >= this_month_start, Transaction.date < next_month_start)
        .subquery()
    )

    # оборот от продажби този месец
    month_sales_total = (
        db.session.query(func.coalesce(func.sum(TransactionItem.total_price), 0.0))
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .filter(Transaction.id.in_(base_txn_ids))
        .filter(Transaction.type == "Sale")
        .scalar()
        or 0.0
    )

    # стойност на покупки този месец
    month_purchases_total = (
        db.session.query(func.coalesce(func.sum(TransactionItem.total_price), 0.0))
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .filter(Transaction.id.in_(base_txn_ids))
        .filter(Transaction.type == "Purchase")
        .scalar()
        or 0.0
    )

    # печалба от продажби този месец
    month_profit = (
        db.session.query(func.coalesce(func.sum(TransactionItem.profit), 0.0))
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .filter(Transaction.id.in_(base_txn_ids))
        .filter(Transaction.type == "Sale")
        .scalar()
        or 0.0
    )

    # брой продажби този месец
    month_sales_count = (
        Transaction.query
        .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
        .filter(Warehouse.owner_id == owner_id)
        .filter(Transaction.type == "Sale")
        .filter(Transaction.date >= this_month_start, Transaction.date < next_month_start)
        .count()
    )

    # брой покупки този месец
    month_purchase_count = (
        Transaction.query
        .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
        .filter(Warehouse.owner_id == owner_id)
        .filter(Transaction.type == "Purchase")
        .filter(Transaction.date >= this_month_start, Transaction.date < next_month_start)
        .count()
    )

    # нетен поток = продажби - покупки
    month_net_flow = float(month_sales_total) - float(month_purchases_total)

    # -------------------- Данни за графиките (последни 12 месеца) -------------------- #
    months = []
    txn_counts = []
    sale_counts = []
    purchase_counts = []

    sale_amounts = []
    purchase_amounts = []
    profit_amounts = []

    for i in range(12):
        m_start = _add_months(start_12, i)
        m_end = _add_months(m_start, 1)

        # показвам само съкращението на месеца Jan Feb Mar
        months.append(m_start.strftime("%b"))

        # база за броя транзакции
        m_txn_q = (
            Transaction.query
            .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
            .filter(Warehouse.owner_id == owner_id)
            .filter(Transaction.date >= m_start, Transaction.date < m_end)
        )

        txn_counts.append(m_txn_q.count())
        sale_counts.append(m_txn_q.filter(Transaction.type == "Sale").count())
        purchase_counts.append(m_txn_q.filter(Transaction.type == "Purchase").count())

        # сума продажби за месеца
        sale_total = (
            db.session.query(func.coalesce(func.sum(TransactionItem.total_price), 0.0))
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
            .filter(Warehouse.owner_id == owner_id)
            .filter(Transaction.type == "Sale")
            .filter(Transaction.date >= m_start, Transaction.date < m_end)
            .scalar()
            or 0.0
        )

        # сума покупки за месеца
        purchase_total = (
            db.session.query(func.coalesce(func.sum(TransactionItem.total_price), 0.0))
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
            .filter(Warehouse.owner_id == owner_id)
            .filter(Transaction.type == "Purchase")
            .filter(Transaction.date >= m_start, Transaction.date < m_end)
            .scalar()
            or 0.0
        )

        # печалба за месеца (само от продажби)
        profit_total = (
            db.session.query(func.coalesce(func.sum(TransactionItem.profit), 0.0))
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
            .filter(Warehouse.owner_id == owner_id)
            .filter(Transaction.type == "Sale")
            .filter(Transaction.date >= m_start, Transaction.date < m_end)
            .scalar()
            or 0.0
        )

        sale_amounts.append(float(sale_total))
        purchase_amounts.append(float(purchase_total))
        profit_amounts.append(float(profit_total))

    # -------------------- Категории за donut chart -------------------- #
    category_data = (
        db.session.query(Product.category, func.count(Product.id))
        .filter(Product.owner_id == owner_id)
        .group_by(Product.category)
        .all()
    )

    product_categories = [(cat or "Unknown") for (cat, _) in category_data]
    product_counts = [int(cnt) for (_, cnt) in category_data]

    # -------------------- Low stock списък -------------------- #
    # по default е 10 ако не е настроено в Settings
    threshold = 10
    try:
        if g.app_config and getattr(g.app_config, "low_stock_threshold", None) is not None:
            threshold = int(g.app_config.low_stock_threshold)
    except Exception:
        threshold = 10

    low_stock = (
        Stock.query
        .join(Warehouse, Stock.warehouse_id == Warehouse.id)
        .filter(Warehouse.owner_id == owner_id)
        .filter(Stock.quantity <= threshold)
        .options(
            db.joinedload(Stock.product),
            db.joinedload(Stock.warehouse),
        )
        .order_by(Stock.quantity.asc())
        .limit(8)
        .all()
    )

    # -------------------- Последни транзакции -------------------- #
    recent_txns = (
        Transaction.query
        .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
        .filter(Warehouse.owner_id == owner_id)
        .options(
            db.joinedload(Transaction.items),
            db.joinedload(Transaction.partner),
            db.joinedload(Transaction.warehouse),
        )
        .order_by(Transaction.date.desc())
        .limit(8)
        .all()
    )

    # -------------------- Топ продукти (последни 30 дни) -------------------- #
    cutoff = now - timedelta(days=30)

    top_products = (
        db.session.query(
            Product.id.label("product_id"),
            Product.name.label("name"),
            Product.sku.label("sku"),
            func.coalesce(func.sum(TransactionItem.quantity), 0).label("qty_sold"),
            func.coalesce(func.sum(TransactionItem.total_price), 0.0).label("revenue"),
            func.coalesce(func.sum(TransactionItem.profit), 0.0).label("profit"),
        )
        .join(TransactionItem, TransactionItem.product_id == Product.id)
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
        .filter(Warehouse.owner_id == owner_id)
        .filter(Transaction.type == "Sale")
        .filter(Transaction.date >= cutoff)
        .group_by(Product.id, Product.name, Product.sku)
        .order_by(func.sum(TransactionItem.quantity).desc())
        .limit(6)
        .all()
    )

    # пращам всичко към dashboard template-а
    return render_template(
        "index.html",
        total_products=total_products,
        total_warehouses=total_warehouses,
        total_transactions=total_transactions,
        total_partners=total_partners,

        # този месец
        month_sales_total=month_sales_total,
        month_purchases_total=month_purchases_total,
        month_profit=month_profit,
        month_net_flow=month_net_flow,
        month_sales_count=month_sales_count,
        month_purchase_count=month_purchase_count,

        # графики
        transaction_months=months,
        transaction_counts=txn_counts,
        sale_counts=sale_counts,
        purchase_counts=purchase_counts,
        sale_amounts=sale_amounts,
        purchase_amounts=purchase_amounts,
        profit_amounts=profit_amounts,

        # donut
        product_categories=product_categories,
        product_counts=product_counts,

        # таблици
        low_stock=low_stock,
        recent_txns=recent_txns,

        # top продукти
        top_products=top_products,
    )
