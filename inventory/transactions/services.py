# inventory/transactions/services.py

from __future__ import annotations

from datetime import datetime
from collections import defaultdict

from inventory.extensions import db
from inventory.models import Product, Transaction, TransactionItem, PurchaseLot, Stock


class TransactionService:
    """
    Transaction logic in one place.

    - Stock is per warehouse
    - Purchases create FIFO lots
    - Sales consume FIFO lots
    - If FIFO lots are missing but stock exists, we fallback to default_purchase_price
      (this usually happens with old/manual stock).
    """

    # -------------------- helpers -------------------- #

    @staticmethod
    def _get_or_create_stock(product_id: int, warehouse_id: int) -> Stock:
        stock = Stock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id).first()
        if not stock:
            stock = Stock(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
            db.session.add(stock)
            db.session.flush()
        return stock

    @staticmethod
    def _fifo_consume(product_id: int, warehouse_id: int, qty: int, allow_negative: bool = False) -> float:
        qty_to_consume = int(qty)
        cost_used = 0.0

        lots = (
            PurchaseLot.query
            .filter_by(product_id=product_id, warehouse_id=warehouse_id)
            .filter(PurchaseLot.quantity_remaining > 0)
            .order_by(PurchaseLot.received_at.asc())
            .all()
        )

        for lot in lots:
            if qty_to_consume <= 0:
                break

            take = min(qty_to_consume, int(lot.quantity_remaining))
            cost_used += take * float(lot.unit_cost or 0.0)
            lot.quantity_remaining -= take
            qty_to_consume -= take

        # If we still have qty to cover, it means FIFO lots are missing/incomplete
        if qty_to_consume > 0:
            if allow_negative:
                # If we allow negative, estimate cost from last known lot (or 0)
                last_lot = (
                    PurchaseLot.query
                    .filter_by(product_id=product_id, warehouse_id=warehouse_id)
                    .order_by(PurchaseLot.received_at.desc())
                    .first()
                )
                fallback_cost = float(last_lot.unit_cost or 0.0) if last_lot else 0.0
                cost_used += qty_to_consume * fallback_cost
                qty_to_consume = 0
            else:
                # Most common: manual stock exists but there are no lots for it
                product = Product.query.get(product_id)
                fallback_cost = float(product.default_purchase_price or 0.0) if product else 0.0
                cost_used += qty_to_consume * fallback_cost
                qty_to_consume = 0

        return cost_used

    @staticmethod
    def _precheck_sale_stock(items: list[dict], warehouse_id: int) -> dict | None:
        """
        Pre-check sale stock for the entire request (handles duplicate product rows).
        Returns {"error": "..."} if not enough stock, else None.
        """
        requested = defaultdict(int)

        # Build requested qty per product
        for row in items:
            try:
                pid = int(row.get("product_id"))
                qty = int(row.get("quantity", 0))
            except Exception:
                return {"error": "Invalid product or quantity."}

            if qty <= 0:
                return {"error": "Quantity must be greater than 0."}

            requested[pid] += qty

        if not requested:
            return {"error": "No items provided."}

        product_ids = list(requested.keys())

        # Load products (for nice names)
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        product_name = {p.id: (p.name or f"#{p.id}") for p in products}

        # Load stock rows for this warehouse
        stock_rows = (
            Stock.query
            .filter(Stock.warehouse_id == warehouse_id, Stock.product_id.in_(product_ids))
            .all()
        )
        stock_map = {s.product_id: int(s.quantity or 0) for s in stock_rows}

        shortages = []
        for pid, req_qty in requested.items():
            available = stock_map.get(pid, 0)  # if no stock row -> 0
            if req_qty > available:
                shortages.append((product_name.get(pid, f"#{pid}"), available, req_qty))

        if shortages:
            lines = [f"{name}: available {avail}, requested {req}" for (name, avail, req) in shortages]
            return {"error": "Not enough stock for sale:\n" + "\n".join(lines)}

        return None

    # -------------------- create pieces -------------------- #

    @staticmethod
    def create_transaction_header(ttype, partner_id, warehouse_id, user_id, note=None) -> Transaction:
        txn = Transaction(
            type=ttype,
            partner_id=partner_id,
            warehouse_id=warehouse_id,
            user_id=user_id,
            date=datetime.utcnow(),
            note=note,
        )
        db.session.add(txn)
        db.session.flush()
        return txn

    @staticmethod
    def create_purchase_item(txn: Transaction, product_id: int, qty: int, unit_cost: float):
        product = Product.query.get(product_id)
        if not product:
            return {"error": "Product not found."}

        qty = int(qty)
        unit_cost = float(unit_cost or 0.0)
        total_price = qty * unit_cost

        item = TransactionItem(
            transaction_id=txn.id,
            product_id=product_id,
            quantity=qty,
            unit_price=unit_cost,
            total_price=total_price,
            cost_used=None,
            profit=None,
        )
        db.session.add(item)
        db.session.flush()

        stock = TransactionService._get_or_create_stock(product_id=product_id, warehouse_id=txn.warehouse_id)
        stock.quantity = (stock.quantity or 0) + qty

        lot = PurchaseLot(
            product_id=product_id,
            warehouse_id=txn.warehouse_id,
            quantity_remaining=qty,
            unit_cost=unit_cost,
            received_at=datetime.utcnow(),
            transaction_item_id=item.id,
        )
        db.session.add(lot)

        # keep legacy field in sync for now
        product.quantity = (product.quantity or 0) + qty

        return {"success": True, "item": item}

    @staticmethod
    def create_sale_item(txn: Transaction, product_id: int, qty: int, sell_price: float, allow_negative: bool = False):
        product = Product.query.get(product_id)
        if not product:
            return {"error": "Product not found."}

        qty = int(qty)
        sell_price = float(sell_price or 0.0)
        total_price = qty * sell_price

        stock = TransactionService._get_or_create_stock(product_id=product_id, warehouse_id=txn.warehouse_id)

        # Safety check (kept as a second line of defense)
        if not allow_negative and (stock.quantity or 0) < qty:
            return {"error": f"Not enough stock for {product.name} in this warehouse (available {stock.quantity})."}

        cost_used = TransactionService._fifo_consume(
            product_id=product_id,
            warehouse_id=txn.warehouse_id,
            qty=qty,
            allow_negative=allow_negative,
        )

        stock.quantity = (stock.quantity or 0) - qty
        product.quantity = (product.quantity or 0) - qty  # legacy sync

        profit = total_price - cost_used

        item = TransactionItem(
            transaction_id=txn.id,
            product_id=product_id,
            quantity=qty,
            unit_price=sell_price,
            total_price=total_price,
            cost_used=cost_used,
            profit=profit,
        )
        db.session.add(item)

        return {"success": True, "item": item}

    # -------------------- main entry -------------------- #

    @staticmethod
    def create_transaction(ttype, partner_id, warehouse_id, user_id, items, note=None, allow_negative=False):
        """
        items: [{product_id, quantity, unit_price}, ...]
        """
        try:
            # PRE-CHECK: block negative stock on sales (whole-sale validation)
            if ttype == "Sale" and not allow_negative:
                pre = TransactionService._precheck_sale_stock(items, int(warehouse_id))
                if pre and pre.get("error"):
                    db.session.rollback()
                    return {"error": pre["error"]}

            txn = TransactionService.create_transaction_header(ttype, partner_id, warehouse_id, user_id, note)
            created_items = []

            for row in items:
                pid = int(row.get("product_id"))
                qty = int(row.get("quantity", 0))
                unit_price = float(row.get("unit_price", 0.0))

                if qty <= 0:
                    db.session.rollback()
                    return {"error": "Quantity must be greater than 0."}

                if ttype == "Purchase":
                    res = TransactionService.create_purchase_item(txn, pid, qty, unit_price)
                else:
                    res = TransactionService.create_sale_item(txn, pid, qty, unit_price, allow_negative=allow_negative)

                if res.get("error"):
                    db.session.rollback()
                    return {"error": res["error"]}

                created_items.append(res.get("item"))

            db.session.commit()
            return {"success": True, "transaction": txn, "items": created_items}

        except Exception:
            db.session.rollback()
            return {"error": "Failed to create transaction. Please try again."}
