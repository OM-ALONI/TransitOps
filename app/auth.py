from functools import wraps
from flask import abort
from flask_login import current_user


ROLE_PERMISSIONS = {
    "fleet_manager": {"fleet_manager", "driver", "safety_officer", "financial_analyst"},
    "safety_officer": {"safety_officer"},
    "financial_analyst": {"financial_analyst"},
    "driver": {"driver"},
}

FEATURE_ACCESS = {
    "vehicles": ["fleet_manager"],
    "drivers": ["fleet_manager", "safety_officer"],
    "trips": ["fleet_manager", "driver"],
    "maintenance": ["fleet_manager"],
    "fuel_expenses": ["fleet_manager", "financial_analyst", "driver"],
    "reports": ["fleet_manager", "financial_analyst", "safety_officer"],
    "dashboard": ["fleet_manager", "driver", "safety_officer", "financial_analyst"],
}


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            user_roles = ROLE_PERMISSIONS.get(current_user.role, {current_user.role})
            if not user_roles.intersection(roles):
                abort(403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def can_access_feature(feature_name):
    if not current_user.is_authenticated:
        return False
    allowed_roles = FEATURE_ACCESS.get(feature_name, [])
    return current_user.role in allowed_roles
