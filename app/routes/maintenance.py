from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models import MaintenanceLog, Vehicle
from app.auth import role_required
from app.utils import safe_commit, get_or_404, apply_sorting, sort_url, sort_icon

maintenance_bp = Blueprint("maintenance", __name__)


@maintenance_bp.route("/")
@login_required
def list_maintenance():
    status_filter = request.args.get("status", "")
    query = MaintenanceLog.query

    if status_filter == "active":
        query = query.filter_by(is_active=True)
    elif status_filter == "closed":
        query = query.filter_by(is_active=False)

    query, sort_col, sort_order = apply_sorting(
        query, MaintenanceLog, "created_at",
        ["id", "vehicle_id", "description", "cost", "start_date", "end_date", "is_active", "created_at"],
    )

    logs = query.all()
    return render_template(
        "maintenance/list.html",
        logs=logs,
        sort_col=sort_col,
        sort_order=sort_order,
    )


@maintenance_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("fleet_manager")
def create_maintenance():
    vehicles = Vehicle.query.filter(
        Vehicle.status.in_(["Available", "On Trip"])
    ).order_by(Vehicle.reg_number).all()

    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", type=int)
        description = request.form.get("description", "").strip()
        cost = request.form.get("cost", "0")

        errors = []
        vehicle = db.session.get(Vehicle, vehicle_id) if vehicle_id else None

        if not vehicle:
            errors.append("Please select a vehicle.")
        if not description:
            errors.append("Description is required.")

        try:
            cost = float(cost)
        except ValueError:
            errors.append("Invalid cost value.")
            cost = 0.0

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("maintenance/create.html", vehicles=vehicles)

        if vehicle.status not in ("Retired", "On Trip"):
            vehicle.status = "In Shop"

        log = MaintenanceLog(
            vehicle_id=vehicle.id,
            description=description,
            cost=cost,
            start_date=datetime.now(timezone.utc).replace(tzinfo=None),
            is_active=True,
        )
        db.session.add(log)
        if safe_commit():
            flash(
                f"Maintenance record created. Vehicle {vehicle.reg_number} is now In Shop.",
                "success",
            )
        return redirect(url_for("maintenance.list_maintenance"))

    return render_template("maintenance/create.html", vehicles=vehicles)


@maintenance_bp.route("/<int:log_id>/close", methods=["POST"])
@login_required
@role_required("fleet_manager")
def close_maintenance(log_id):
    log = get_or_404(MaintenanceLog, log_id)

    if not log.is_active:
        flash("This maintenance record is already closed.", "warning")
        return redirect(url_for("maintenance.list_maintenance"))

    log.is_active = False
    log.end_date = datetime.now(timezone.utc).replace(tzinfo=None)

    vehicle = db.session.get(Vehicle, log.vehicle_id)
    if vehicle and vehicle.status == "In Shop":
        vehicle.status = "Available"

    if safe_commit():
        vname = vehicle.reg_number if vehicle else "Unknown"
        flash(
            f"Maintenance closed. Vehicle {vname} is now Available.",
            "success",
        )
    return redirect(url_for("maintenance.list_maintenance"))
