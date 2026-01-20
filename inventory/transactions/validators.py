def validate_transaction_form_data(ttype, partner_id, warehouse_id, items):
    errors = []
    if not ttype:
        errors.append("Transaction type required.")
    if not partner_id:
        errors.append("Partner required.")
    if not warehouse_id:
        errors.append("Warehouse required.")
    if not items or len(items) == 0:
        errors.append("At least one product is required.")
    for idx, row in enumerate(items, start=1):
        try:
            qty = int(row.get('quantity', 0))
            if qty <= 0:
                errors.append(f"Row {idx}: quantity must be > 0.")
        except Exception:
            errors.append(f"Row {idx}: invalid quantity.")
        try:
            price = float(row.get('unit_price', 0.0))
            if price < 0:
                errors.append(f"Row {idx}: unit price cannot be negative.")
        except Exception:
            errors.append(f"Row {idx}: invalid unit price.")
    return errors
