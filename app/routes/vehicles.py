from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Vehicle
from app.auth import role_required
from app.utils import safe_commit, get_or_404, apply_sorting, sort_url, sort_icon

vehicles_bp = Blueprint("vehicles", __name__)


@vehicles_bp.route("/")
@login_required
def list_vehicles():
    status_filter = request.args.get("status", "")
    type_filter = request.args.get("type", "")
    search = request.args.get("search", "").strip()

    query = Vehicle.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if type_filter:
        query = query.filter_by(vehicle_type=type_filter)
    if search:
        query = query.filter(
            (Vehicle.reg_number.ilike(f"%{search}%"))
            | (Vehicle.model_name.ilike(f"%{search}%"))
        )

    query, sort_col, sort_order = apply_sorting(
        query, Vehicle, "created_at",
        ["reg_number", "model_name", "vehicle_type", "max_load_kg", "odometer", "acquisition_cost", "status", "created_at"],
    )

    vehicles = query.all()
    return render_template(
        "vehicles/list.html",
        vehicles=vehicles,
        sort_col=sort_col,
        sort_order=sort_order,
    )


@vehicles_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("fleet_manager")
def create_vehicle():
    if request.method == "POST":
        reg_number = request.form.get("reg_number", "").strip().upper()
        model_name = request.form.get("model_name", "").strip()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        max_load_kg = request.form.get("max_load_kg", "0")
        odometer = request.form.get("odometer", "0")
        acquisition_cost = request.form.get("acquisition_cost", "0")
        status = request.form.get("status", "Available")

        errors = []
        if not reg_number:
            errors.append("Registration number is required.")
        if Vehicle.query.filter_by(reg_number=reg_number).first():
            errors.append("A vehicle with this registration number already exists.")
        if not model_name:
            errors.append("Model name is required.")
        try:
            max_load_kg = float(max_load_kg)
            if max_load_kg <= 0:
                errors.append("Max load capacity must be greater than 0.")
        except ValueError:
            errors.append("Invalid max load capacity.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("vehicles/create.html")

        vehicle = Vehicle(
            reg_number=reg_number,
            model_name=model_name,
            vehicle_type=vehicle_type,
            max_load_kg=max_load_kg,
            odometer=float(odometer) if odometer else 0.0,
            acquisition_cost=float(acquisition_cost) if acquisition_cost else 0.0,
            status=status,
        )
        db.session.add(vehicle)
        if safe_commit():
            flash(f"Vehicle {reg_number} registered successfully.", "success")
        return redirect(url_for("vehicles.list_vehicles"))

    return render_template("vehicles/create.html")


@vehicles_bp.route("/<int:vehicle_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("fleet_manager")
def edit_vehicle(vehicle_id):
    vehicle = get_or_404(Vehicle, vehicle_id)

    if request.method == "POST":
        vehicle.model_name = request.form.get("model_name", vehicle.model_name).strip()
        vehicle.vehicle_type = request.form.get("vehicle_type", vehicle.vehicle_type)
        try:
            max_load = float(request.form.get("max_load_kg", vehicle.max_load_kg))
            if max_load > 0:
                vehicle.max_load_kg = max_load
            else:
                flash("Max load must be greater than 0.", "warning")
        except (ValueError, TypeError):
            flash("Invalid max load value — using previous.", "warning")
        try:
            vehicle.odometer = float(request.form.get("odometer", vehicle.odometer))
        except (ValueError, TypeError):
            flash("Invalid odometer value — using previous.", "warning")
        try:
            acq = float(request.form.get("acquisition_cost", vehicle.acquisition_cost))
            if acq >= 0:
                vehicle.acquisition_cost = acq
            else:
                flash("Acquisition cost cannot be negative.", "warning")
        except (ValueError, TypeError):
            flash("Invalid acquisition cost — using previous.", "warning")
        vehicle.status = request.form.get("status", vehicle.status)

        if safe_commit():
            flash(f"Vehicle {vehicle.reg_number} updated.", "success")
        return redirect(url_for("vehicles.list_vehicles"))

    return render_template("vehicles/edit.html", vehicle=vehicle)


@vehicles_bp.route("/<int:vehicle_id>/delete", methods=["POST"])
@login_required
@role_required("fleet_manager")
def delete_vehicle(vehicle_id):
    vehicle = get_or_404(Vehicle, vehicle_id)
    if vehicle.trips.count() > 0:
        flash("Cannot delete vehicle with trip history. Retire it instead.", "danger")
    else:
        db.session.delete(vehicle)
        if safe_commit():
            flash("Vehicle deleted.", "success")
    return redirect(url_for("vehicles.list_vehicles"))
