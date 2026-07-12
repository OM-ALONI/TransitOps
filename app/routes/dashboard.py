from datetime import date, timedelta
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from app.models import Vehicle, Driver, Trip, MaintenanceLog, FuelExpense
from app.auth import role_required
from app.utils import get_kpi_data

dashboard_bp = Blueprint("dashboard", __name__)

INDIAN_STATES = {
    "MH": "Maharashtra", "KA": "Karnataka", "DL": "Delhi", "TN": "Tamil Nadu",
    "GJ": "Gujarat", "UP": "Uttar Pradesh", "RJ": "Rajasthan", "HR": "Haryana",
    "TS": "Telangana", "WB": "West Bengal", "KL": "Kerala", "MP": "Madhya Pradesh",
    "AP": "Andhra Pradesh", "PB": "Punjab", "BR": "Bihar", "OR": "Odisha",
}


def _region_filter(query, region):
    if region:
        query = query.filter(Vehicle.reg_number.like(f"{region}-%"))
    return query


@dashboard_bp.route("/")
@login_required
def index():
    kpis = get_kpi_data()
    expiring_drivers = Driver.query.filter(
        Driver.license_expiry <= date.today() + timedelta(days=30),
        Driver.license_expiry > date.today(),
        Driver.status != "Suspended",
    ).order_by(Driver.license_expiry).limit(5).all()

    expired_drivers = Driver.query.filter(
        Driver.license_expiry <= date.today(),
        Driver.status != "Suspended",
    ).order_by(Driver.license_expiry).limit(5).all()

    return render_template(
        "dashboard.html",
        kpis=kpis,
        expiring_drivers=expiring_drivers,
        expired_drivers=expired_drivers,
        states=INDIAN_STATES,
    )


@dashboard_bp.route("/api/kpis")
@login_required
def api_kpis():
    region = request.args.get("region", "")
    base_vehicle_q = _region_filter(Vehicle.query, region)
    active_vehicles = base_vehicle_q.filter_by(status="Available").count()
    return jsonify({
        "active_vehicles": active_vehicles,
        "on_trip_vehicles": base_vehicle_q.filter_by(status="On Trip").count(),
        "in_shop_vehicles": base_vehicle_q.filter_by(status="In Shop").count(),
        "retired_vehicles": base_vehicle_q.filter_by(status="Retired").count(),
        "fleet_utilization": round(
            (base_vehicle_q.filter_by(status="On Trip").count() /
             max(base_vehicle_q.filter(Vehicle.status != "Retired").count(), 1)) * 100, 1
        ),
    })


@dashboard_bp.route("/api/charts/vehicle-status")
@login_required
def chart_vehicle_status():
    region = request.args.get("region", "")
    q = _region_filter(Vehicle.query, region)
    return jsonify({
        "labels": ["Available", "On Trip", "In Shop", "Retired"],
        "values": [
            q.filter_by(status="Available").count(),
            q.filter_by(status="On Trip").count(),
            q.filter_by(status="In Shop").count(),
            q.filter_by(status="Retired").count(),
        ],
    })


@dashboard_bp.route("/api/charts/trip-trends")
@login_required
def chart_trip_trends():
    today = date.today()
    labels, dispatched_vals, completed_vals = [], [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime("%a"))
        dispatched_vals.append(Trip.query.filter(
            Trip.dispatched_at >= day, Trip.dispatched_at < day + timedelta(days=1)).count())
        completed_vals.append(Trip.query.filter(
            Trip.completed_at >= day, Trip.completed_at < day + timedelta(days=1)).count())
    return jsonify({
        "labels": labels,
        "datasets": [
            {"label": "Dispatched", "values": dispatched_vals},
            {"label": "Completed", "values": completed_vals},
        ],
    })


@dashboard_bp.route("/api/charts/fleet-utilization")
@login_required
def chart_fleet_utilization():
    region = request.args.get("region", "")
    q = _region_filter(Vehicle.query, region)
    return jsonify({
        "labels": ["Available", "On Trip", "In Shop"],
        "values": [
            q.filter_by(status="Available").count(),
            q.filter_by(status="On Trip").count(),
            q.filter_by(status="In Shop").count(),
        ],
    })
