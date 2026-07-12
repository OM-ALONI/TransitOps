import logging
from datetime import date, datetime
from functools import wraps
from flask import flash, redirect, url_for, request, current_app, abort
from flask_login import current_user
from app import db
from app.models import Vehicle, Driver

logger = logging.getLogger(__name__)


def safe_commit():
    """commit and rollback if something goes wrong
    learned this the hard way after corrupting the db twice
    the rollback is important — without it the session gets stuck in a bad state"""
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database commit failed: {e}")
        flash("An unexpected error occurred. Please try again.", "danger")
        return False


def get_or_404(model, object_id):
    """fetch object or raise 404 — saves writing the same check everywhere"""
    obj = db.session.get(model, object_id)
    if obj is None:
        abort(404)
    return obj


def get_kpi_data():
    total_vehicles = Vehicle.query.count()
    active_vehicles = Vehicle.query.filter_by(status="Available").count()
    on_trip_vehicles = Vehicle.query.filter_by(status="On Trip").count()
    in_shop_vehicles = Vehicle.query.filter_by(status="In Shop").count()
    retired_vehicles = Vehicle.query.filter_by(status="Retired").count()

    total_drivers = Driver.query.count()
    available_drivers = Driver.query.filter_by(status="Available").count()
    on_duty_drivers = Driver.query.filter_by(status="On Trip").count()
    off_duty_drivers = Driver.query.filter_by(status="Off Duty").count()
    suspended_drivers = Driver.query.filter_by(status="Suspended").count()

    from app.models import Trip
    active_trips = Trip.query.filter_by(status="Dispatched").count()
    pending_trips = Trip.query.filter_by(status="Draft").count()
    completed_trips = Trip.query.filter(
        Trip.status.in_(["Completed", "Cancelled"])
    ).count()

    fleet_utilization = 0
    operational_fleet = active_vehicles + on_trip_vehicles
    if operational_fleet > 0:
        fleet_utilization = round((on_trip_vehicles / operational_fleet) * 100, 1)

    drivers_with_expiring_licenses = Driver.query.filter(
        Driver.license_expiry <= date.today(),
        Driver.status != "Suspended",
    ).count()

    return {
        "total_vehicles": total_vehicles,
        "active_vehicles": active_vehicles,
        "on_trip_vehicles": on_trip_vehicles,
        "in_shop_vehicles": in_shop_vehicles,
        "retired_vehicles": retired_vehicles,
        "total_drivers": total_drivers,
        "available_drivers": available_drivers,
        "on_duty_drivers": on_duty_drivers,
        "off_duty_drivers": off_duty_drivers,
        "suspended_drivers": suspended_drivers,
        "active_trips": active_trips,
        "pending_trips": pending_trips,
        "completed_trips": completed_trips,
        "fleet_utilization": fleet_utilization,
        "expiring_licenses": drivers_with_expiring_licenses,
    }


def format_currency(amount):
    if amount is None:
        return "₹0.00"
    return f"₹{amount:,.2f}"


def format_date(dt):
    if dt is None:
        return "—"
    if isinstance(dt, datetime):
        return dt.strftime("%d %b %Y, %H:%M")
    return dt.strftime("%d %b %Y")


def clean_string(value, max_length=200):
    if not value:
        return ""
    return str(value).strip()[:max_length]


def parse_float(value, default=None):
    try:
        result = float(value)
        return result
    except (ValueError, TypeError):
        return default


def parse_int(value, default=None):
    try:
        result = int(value)
        return result
    except (ValueError, TypeError):
        return default


def parse_date(value, fmt="%Y-%m-%d"):
    try:
        return datetime.strptime(value, fmt).date()
    except (ValueError, TypeError):
        return None


def apply_sorting(query, model, default_column, allowed_columns):
    sort_col = request.args.get("sort", default_column)
    order = request.args.get("order", "asc")

    if sort_col not in allowed_columns:
        sort_col = default_column
    if order not in ("asc", "desc"):
        order = "asc"

    column = getattr(model, sort_col, None)
    if column is None:
        column = getattr(model, default_column)

    if order == "desc":
        query = query.order_by(column.desc())
    else:
        query = query.order_by(column.asc())

    return query, sort_col, order


def sort_url(col, current_sort, current_order):
    if col == current_sort:
        new_order = "desc" if current_order == "asc" else "asc"
    else:
        new_order = "asc"
    params = dict(request.args)
    params["sort"] = col
    params["order"] = new_order
    return "&".join(f"{k}={v}" for k, v in params.items())


def sort_icon(col, current_sort, current_order):
    if col != current_sort:
        return "bi bi-arrow-down-up text-muted"
    return "bi bi-caret-up-fill" if current_order == "asc" else "bi bi-caret-down-fill"


def get_available_vehicles():
    return Vehicle.query.filter(
        Vehicle.status == "Available"
    ).order_by(Vehicle.reg_number).all()


def get_available_drivers():
    today = date.today()
    return Driver.query.filter(
        Driver.status == "Available",
        Driver.license_expiry > today,
    ).order_by(Driver.name).all()
