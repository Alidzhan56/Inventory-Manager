# inventory/utils/permissions.py

# Central Role -> Permission mapping
ROLE_PERMISSIONS = {
    "Admin / Owner": {
        "dashboard:view",
        "products:view", "products:create", "products:edit", "products:delete",
        "warehouses:view", "warehouses:create", "warehouses:delete",
        "partners:view", "partners:create", "partners:edit", "partners:delete",
        "transactions:view", "transactions:create_purchase", "transactions:create_sale",
        "users:view", "users:create", "users:update_role", "users:delete",
        "settings:view", "settings:update",
    },

    "Warehouse Manager": {
        "dashboard:view",
        "products:view", "products:create", "products:edit",
        "warehouses:view", "warehouses:create",
        "partners:view",  # can select partner on transactions
        "transactions:view", "transactions:create_purchase", "transactions:create_sale",
    },

    "Sales Agent": {
        "dashboard:view",
        "products:view",
        "warehouses:view",
        "partners:view",  # IMPORTANT: can SEE partners but not create/edit/delete
        "transactions:view", "transactions:create_sale",
    },

    # Developer: superuser style for maintenance
    "Developer": {
        "dashboard:view",
        "products:view", "products:create", "products:edit", "products:delete",
        "warehouses:view", "warehouses:create", "warehouses:delete",
        "partners:view", "partners:create", "partners:edit", "partners:delete",
        "transactions:view", "transactions:create_purchase", "transactions:create_sale",
        "users:view", "users:create", "users:update_role", "users:delete",
        "settings:view", "settings:update",
    },
}


def has_permission(user, permission: str) -> bool:
    """
    Returns True if user has a permission by role mapping.
    If role missing/unknown -> False.
    """
    role = (getattr(user, "role", "") or "").strip()
    perms = ROLE_PERMISSIONS.get(role, set())
    return permission in perms
