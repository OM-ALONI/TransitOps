from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models import FuelExpense, Vehicle, Trip
from app.auth import role_required
from app.utils import safe_commit, get_or_404, apply_sorting, sort_url, sort_icon

fuel_bp = Blueprint("fuel", __name__)


@fuel_bp.route("/")
@login_required
def list_expenses():
    type_filter = request.args.get("type", "")
    vehicle_filter = request.args.get("vehicle_id", "")

    query = FuelExpense.query

    if type_filter:
        query = query.filter_by(expense_type=type_filter)
    if vehicle_filter:
        query = query.filter_by(vehicle_id=int(vehicle_filter))

    query, sort_col, sort_order = apply_sorting(
        query, FuelExpense, "date",
        ["id", "vehicle_id", "expense_type", "liters", "cost", "date", "trip_id"],
    )

    expenses = query.all()
    vehicles = Vehicle.query.order_by(Vehicle.reg_number).all()
    return render_template(
        "fuel/list.html",
        expenses=expenses,
        vehicles=vehicles,
        sort_col=sort_col,
        sort_order=sort_order,
    )


@fuel_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("fleet_manager", "financial_analyst", "driver")
def create_expense():
    vehicles = Vehicle.query.order_by(Vehicle.reg_number).all()
    trips = Trip.query.filter_by(status="Completed").order_by(Trip.completed_at.desc()).all()

    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", type=int)
        trip_id = request.form.get("trip_id", type=int) or None
        expense_type = request.form.get("expense_type", "Fuel")
        liters = request.form.get("liters", "0")
        cost = request.form.get("cost", "0")
        expense_date = request.form.get("date", date.today().isoformat())
        notes = request.form.get("notes", "").strip()

        errors = []
        vehicle = db.session.get(Vehicle, vehicle_id) if vehicle_id else None

        if not vehicle:
            errors.append("Please select a vehicle.")
        if expense_type not in ("Fuel", "Toll", "Maintenance", "Other"):
            errors.append("Invalid expense type.")
        try:
            cost_val = float(cost)
            if cost_val < 0:
                errors.append("Cost cannot be negative.")
        except ValueError:
            errors.append("Invalid cost amount.")
            cost_val = 0.0
        try:
            parsed_date = datetime.strptime(expense_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            errors.append("Invalid date.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "fuel/create.html", vehicles=vehicles, trips=trips, today=date.today()
            )

        expense = FuelExpense(
            vehicle_id=vehicle.id,
            trip_id=trip_id,
            expense_type=expense_type,
            liters=float(liters) if liters else None,
            cost=cost_val,
            date=parsed_date,
            notes=notes,
        )
        db.session.add(expense)
        if safe_commit():
            flash(f"{expense_type} expense of ₹{cost_val:.2f} recorded.", "success")
        return redirect(url_for("fuel.list_expenses"))

    return render_template("fuel/create.html", vehicles=vehicles, trips=trips, today=date.today())
