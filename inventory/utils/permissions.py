# inventory/utils/permissions.py

from __future__ import annotations

from typing import Iterable


# Canonical role names used across the app
ROLE_DEVELOPER = "Developer"
ROLE_ADMIN_OWNER = "Admin / Owner"
ROLE_WAREHOUSE = "Warehouse Manager"
ROLE_SALES = "Sales Agent"


def _norm_role(role: str | None) -> str:
    """
    Normalize role strings to avoid mismatches like:
    'Admin/Owner' vs 'Admin / Owner' vs ' Admin / Owner '
    """
    if not role:
        return ""
    r = " ".join(role.strip().split())  # normalize whitespace
    # normalize common variants
    if r.replace(" ", "") in {"Admin/Owner", "Admin/Owner"}:
        return ROLE_ADMIN_OWNER
    if r in {"Admin/Owner"}:
        return ROLE_ADMIN_OWNER
    return r


# Permissions per role
ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_DEVELOPER: {
        # developer-only things (adjust to your needs)
        "users:view",
        "users:delete",
        # Developer should NOT manage org settings by design
    },

    ROLE_ADMIN_OWNER: {
        # users
        "users:view",
        "users:create",
        "users:update_role",
        "users:delete",

        # settings
        "settings:manage",

        # inventory (examples - add your real actions)
        "products:view",
        "products:create",
        "products:update",
        "products:delete",

        "warehouses:view",
        "warehouses:create",
        "warehouses:update",
        "warehouses:delete",

        "partners:view",
        "partners:create",
        "partners:update",
        "partners:delete",

        "transactions:view",
        "transactions:create",
        "reports:view",
    },

    ROLE_WAREHOUSE: {
        "products:view",
        "products:create",
        "products:update",

        "warehouses:view",
        "warehouses:update",

        "transactions:view",
        "transactions:create",
    },

    ROLE_SALES: {
        "products:view",
        "transactions:create",
        "transactions:view",
    },
}


def has_permission(user, permission: str) -> bool:
    """
    Check whether a user has a permission string like 'settings:manage'.
    """
    role = _norm_role(getattr(user, "role", None))
    allowed = ROLE_PERMISSIONS.get(role, set())
    return permission in allowed
