# inventory/transactions/services.py
from inventory.extensions import db
from inventory.models import Product, Transaction
from datetime import datetime


class TransactionService:

    @staticmethod
    def create_transaction(ttype, product_id, partner_id, warehouse_id, quantity, user_id):
        product = Product.query.get(product_id)

        if not product:
            return {"error": "Product not found."}

        # Apply stock movement
        if ttype == "Sale":
            if quantity > product.quantity:
                return {"error": "Not enough stock."}
            product.quantity -= quantity

        elif ttype == "Purchase":
            product.quantity += quantity

        elif ttype == "Transfer":
            return {"error": "Not implemented yet"}  # Later

        # Total price logic
        total_price = (product.price or 0) * quantity

        txn = Transaction(
            type=ttype,
            product_id=product_id,
            partner_id=partner_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            total_price=total_price,
            user_id=user_id,
            date=datetime.utcnow()
        )

        db.session.add(txn)
        db.session.commit()

        return {"success": True, "transaction": txn}
