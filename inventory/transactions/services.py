from __future__ import annotations

from datetime import datetime
from collections import defaultdict

from inventory.extensions import db
from inventory.models import (
    Product, Transaction, TransactionItem, PurchaseLot, Stock,
    StockMovement, LotAllocation
)


class TransactionError(Exception):
    pass


class TransactionService:
    """
    Тук е цялата логика за транзакции на едно място

    покупки правят FIFO lot-ове
    продажби изяждат FIFO lot-овете по ред
    stock-а е по склад
    всичко е атомарно или минава цялото или нищо не се записва
    """

    @staticmethod
    def _get_or_create_stock(product_id: int, warehouse_id: int) -> Stock:
        # гаранция че имаме Stock ред за продукта в този склад
        stock = Stock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id).first()
        if not stock:
            stock = Stock(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
            db.session.add(stock)
            db.session.flush()
        return stock

    @staticmethod
    def _precheck_sale_stock(items: list[dict], warehouse_id: int) -> dict | None:
        # предварително проверявам цялата продажба наведнъж
        # важно е защото може да има 2 реда за един и същ продукт и иначе ще се мине на части
        requested = defaultdict(int)

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

        products = Product.query.filter(Product.id.in_(product_ids)).all()
        product_name = {p.id: (p.name or f"#{p.id}") for p in products}

        stock_rows = (
            Stock.query
            .filter(Stock.warehouse_id == warehouse_id, Stock.product_id.in_(product_ids))
            .all()
        )
        stock_map = {s.product_id: int(s.quantity or 0) for s in stock_rows}

        shortages = []
        for pid, req_qty in requested.items():
            available = stock_map.get(pid, 0)
            if req_qty > available:
                shortages.append((product_name.get(pid, f"#{pid}"), available, req_qty))

        if shortages:
            lines = [f"{name}: available {avail}, requested {req}" for (name, avail, req) in shortages]
            return {"error": "Not enough stock for sale:\n" + "\n".join(lines)}

        return None

    @staticmethod
    def _fifo_consume_with_allocations(
        *, transaction_item_id: int, product_id: int, warehouse_id: int, qty: int, allow_negative: bool
    ) -> float:
        # тук става FIFO реално
        # взимам най старите lot-ове и от всеки взимам колкото трябва
        # и пиша LotAllocation за отчетност кой lot колко е дал
        qty_to_consume = int(qty)
        cost_used = 0.0

        lots = (
            PurchaseLot.query
            .filter_by(product_id=product_id, warehouse_id=warehouse_id)
            .filter(PurchaseLot.quantity_remaining > 0)
            .order_by(PurchaseLot.received_at.asc(), PurchaseLot.id.asc())
            .all()
        )

        for lot in lots:
            if qty_to_consume <= 0:
                break

            take = min(qty_to_consume, int(lot.quantity_remaining))
            lot.quantity_remaining -= take
            qty_to_consume -= take

            unit_cost = float(lot.unit_cost or 0.0)
            cost_used += take * unit_cost

            db.session.add(LotAllocation(
                transaction_item_id=transaction_item_id,
                purchase_lot_id=lot.id,
                quantity=take,
                unit_cost=unit_cost,
            ))

        # ако lot-овете не стигат
        # allow_negative True значи пак продължаваме и смятаме себестойност по последен lot
        # иначе fallback към default_purchase_price
        if qty_to_consume > 0:
            if allow_negative:
                last_lot = (
                    PurchaseLot.query
                    .filter_by(product_id=product_id, warehouse_id=warehouse_id)
                    .order_by(PurchaseLot.received_at.desc(), PurchaseLot.id.desc())
                    .first()
                )
                fallback_cost = float(last_lot.unit_cost or 0.0) if last_lot else 0.0
            else:
                product = Product.query.get(product_id)
                fallback_cost = float(product.default_purchase_price or 0.0) if product else 0.0

            cost_used += qty_to_consume * fallback_cost
            qty_to_consume = 0

        return cost_used

    @staticmethod
    def _create_header(ttype: str, partner_id: int, warehouse_id: int, user_id: int, note: str | None) -> Transaction:
        # header-а е една транзакция а item-ите са редовете
        txn = Transaction(
            type=ttype,
            partner_id=partner_id,
            warehouse_id=warehouse_id,
            user_id=user_id,
            date=datetime.utcnow(),
            note=note,
            locked=True,
        )
        db.session.add(txn)
        db.session.flush()
        return txn

    @staticmethod
    def _purchase_item(txn: Transaction, owner_id: int, product_id: int, qty: int, unit_cost: float) -> TransactionItem:
        product = Product.query.get(product_id)
        if not product:
            raise TransactionError("Product not found.")

        qty = int(qty)
        if qty <= 0:
            raise TransactionError("Quantity must be greater than 0.")

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
        stock.quantity = int(stock.quantity or 0) + qty

        db.session.add(PurchaseLot(
            product_id=product_id,
            warehouse_id=txn.warehouse_id,
            quantity_remaining=qty,
            unit_cost=unit_cost,
            received_at=datetime.utcnow(),
            transaction_item_id=item.id,
        ))

        db.session.add(StockMovement(
            owner_id=owner_id,
            transaction_id=txn.id,
            transaction_item_id=item.id,
            product_id=product_id,
            warehouse_id=txn.warehouse_id,
            direction="IN",
            quantity=qty,
            unit_cost=unit_cost,
            unit_price=None,
            created_by_user_id=txn.user_id,
            note="Purchase",
        ))

        return item

    @staticmethod
    def _sale_item(
        txn: Transaction, owner_id: int, product_id: int, qty: int, sell_price: float, allow_negative: bool
    ) -> TransactionItem:
        product = Product.query.get(product_id)
        if not product:
            raise TransactionError("Product not found.")

        qty = int(qty)
        if qty <= 0:
            raise TransactionError("Quantity must be greater than 0.")

        sell_price = float(sell_price or 0.0)
        total_price = qty * sell_price

        stock = TransactionService._get_or_create_stock(product_id=product_id, warehouse_id=txn.warehouse_id)

        # втори слой защита да не мине продажба без наличност
        if not allow_negative and int(stock.quantity or 0) < qty:
            raise TransactionError(f"Not enough stock for {product.name} in this warehouse (available {stock.quantity}).")

        item = TransactionItem(
            transaction_id=txn.id,
            product_id=product_id,
            quantity=qty,
            unit_price=sell_price,
            total_price=total_price,
        )
        db.session.add(item)
        db.session.flush()

        cost_used = TransactionService._fifo_consume_with_allocations(
            transaction_item_id=item.id,
            product_id=product_id,
            warehouse_id=txn.warehouse_id,
            qty=qty,
            allow_negative=allow_negative,
        )

        stock.quantity = int(stock.quantity or 0) - qty

        item.cost_used = cost_used
        item.profit = total_price - cost_used

        avg_cost = (cost_used / qty) if qty else None
        db.session.add(StockMovement(
            owner_id=owner_id,
            transaction_id=txn.id,
            transaction_item_id=item.id,
            product_id=product_id,
            warehouse_id=txn.warehouse_id,
            direction="OUT",
            quantity=qty,
            unit_cost=avg_cost,
            unit_price=sell_price,
            created_by_user_id=txn.user_id,
            note="Sale",
        ))

        return item

    @staticmethod
    def create_transaction(
        *, ttype: str, partner_id: int, warehouse_id: int, user_id: int,
        items: list[dict], owner_id: int, note: str | None = None, allow_negative: bool = False
    ) -> dict:
        # това е публичния вход който се вика от routes
        # вътре държим db.session.begin за да е атомарно
        if ttype not in {"Purchase", "Sale"}:
            return {"error": "Invalid transaction type."}

        if ttype == "Sale" and not allow_negative:
            pre = TransactionService._precheck_sale_stock(items, int(warehouse_id))
            if pre and pre.get("error"):
                return {"error": pre["error"]}

        try:
            created_items: list[TransactionItem] = []

            with db.session.begin():
                txn = TransactionService._create_header(ttype, partner_id, warehouse_id, user_id, note)

                for row in items:
                    pid = int(row.get("product_id"))
                    qty = int(row.get("quantity", 0))
                    unit_price = float(row.get("unit_price", 0.0))

                    if qty <= 0:
                        raise TransactionError("Quantity must be greater than 0.")

                    if ttype == "Purchase":
                        created_items.append(TransactionService._purchase_item(txn, owner_id, pid, qty, unit_price))
                    else:
                        created_items.append(
                            TransactionService._sale_item(txn, owner_id, pid, qty, unit_price, allow_negative)
                        )

            return {"success": True, "transaction": txn, "items": created_items}

        except TransactionError as e:
            return {"error": str(e)}
        except Exception:
            return {"error": "Failed to create transaction. Please try again."}
