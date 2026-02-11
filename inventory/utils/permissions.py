from __future__ import annotations


# стандартни имена на ролите които ползвам навсякъде в проекта
ROLE_DEVELOPER = "Developer"
ROLE_ADMIN_OWNER = "Admin / Owner"
ROLE_WAREHOUSE = "Warehouse Manager"
ROLE_SALES = "Sales Agent"


def _norm_role(role: str | None) -> str:
    """
    Нормализирам ролята за да няма проблеми
    примерно Admin/Owner vs Admin / Owner vs с излишни интервали
    """
    if not role:
        return ""

    # махам излишни интервали
    r = " ".join(role.strip().split())

    # ако някъде е записано без интервал между / го оправям
    compact = r.replace(" ", "")
    if compact == "Admin/Owner":
        return ROLE_ADMIN_OWNER

    return r


# тук описвам кой какви права има
# форматът е "module:action"
ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_DEVELOPER: {
        # developer има достъп основно до user management
        "users:view",
        "users:delete",
        "users:update_role",
        # нарочно няма settings:manage
    },

    ROLE_ADMIN_OWNER: {
        # users
        "users:view",
        "users:create",
        "users:update_role",
        "users:delete",

        # settings
        "settings:manage",

        # products
        "products:view",
        "products:create",
        "products:update",
        "products:delete",

        # warehouses
        "warehouses:view",
        "warehouses:create",
        "warehouses:update",
        "warehouses:delete",

        # partners
        "partners:view",
        "partners:create",
        "partners:update",
        "partners:delete",

        # transactions
        "transactions:view",
        "transactions:create",
        "transactions:create_sale",
        "transactions:create_purchase",

        # reports
        "reports:view",
    },

    ROLE_WAREHOUSE: {
        # складов служител
        "products:view",
        "products:create",
        "products:update",

        "warehouses:view",
        "warehouses:update",

        "transactions:view",
        "transactions:create",
        "transactions:create_purchase",
    },

    ROLE_SALES: {
        # търговец
        "products:view",

        "transactions:view",
        "transactions:create",
        "transactions:create_sale",
    },
}


def has_permission(user, permission: str) -> bool:
    """
    Проверявам дали даден user има конкретно право
    например settings:manage или products:create
    """
    role = _norm_role(getattr(user, "role", None))
    allowed = ROLE_PERMISSIONS.get(role, set())
    return permission in allowed
