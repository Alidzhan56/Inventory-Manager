# inventory/transactions/validators.py

def validate_transaction_form(form):
    errors = []

    if not form.get("type"):
        errors.append("Transaction type is required.")

    if not form.get("product_id"):
        errors.append("Product is required.")

    try:
        quantity = int(form.get("quantity", 0))
        if quantity <= 0:
            errors.append("Quantity must be greater than 0.")
    except ValueError:
        errors.append("Invalid quantity format.")

    return errors
