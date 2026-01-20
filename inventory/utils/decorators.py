from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

from inventory.utils.permissions import has_permission
from inventory.utils.translations import _


def roles_required(*roles):
    """Simple role-based access (kept for backward compatibility)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if (not current_user.is_authenticated) or (current_user.role not in roles):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(permission: str, *, abort_on_fail: bool = False, redirect_endpoint: str = "main.index"):
    """
    Permission-based access control (recommended).
    - abort_on_fail=True -> abort(403)
    - otherwise flash + redirect
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)

            if not has_permission(current_user, permission):
                if abort_on_fail:
                    abort(403)
                flash(_("You do not have permission to perform this action."), "danger")
                return redirect(url_for(redirect_endpoint))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
