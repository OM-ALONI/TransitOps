from datetime import datetime, date, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Trip, Vehicle, Driver, FuelExpense
from app.auth import role_required
from app.utils import get_available_vehicles, get_available_drivers, format_date, safe_commit, get_or_404, apply_sorting, sort_url, sort_icon

trips_bp = Blueprint("trips", __name__)


@trips_bp.route("/")
@login_required
def list_trips():
    status_filter = request.args.get("status", "")
    query = Trip.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    query, sort_col, sort_order = apply_sorting(
        query, Trip, "created_at",
        ["id", "vehicle_id", "driver_id", "source", "destination", "cargo_weight_kg", "planned_distance_km", "status", "created_at"],
    )

    trips = query.all()
    return render_template(
        "trips/list.html",
        trips=trips,
        sort_col=sort_col,
        sort_order=sort_order,
    )


@trips_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("fleet_manager", "driver")
def create_trip():
    vehicles = get_available_vehicles()
    drivers = get_available_drivers()

    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", type=int)
        driver_id = request.form.get("driver_id", type=int)
        source = request.form.get("source", "").strip()
        destination = request.form.get("destination", "").strip()
        cargo_weight_kg = request.form.get("cargo_weight_kg", "0")
        planned_distance_km = request.form.get("planned_distance_km", "0")

        errors = []
        vehicle = db.session.get(Vehicle, vehicle_id) if vehicle_id else None
        driver = db.session.get(Driver, driver_id) if driver_id else None

        if not vehicle:
            errors.append("Please select a valid vehicle.")
        elif not vehicle.is_available_for_dispatch:
            errors.append(f"Vehicle {vehicle.reg_number} is not available for dispatch.")

        if not driver:
            errors.append("Please select a valid driver.")
        elif not driver.is_available_for_dispatch:
            if driver.license_expired:
                errors.append(f"Driver {driver.name} has an expired license.")
            elif driver.status == "Suspended":
                errors.append(f"Driver {driver.name} is suspended.")
            else:
                errors.append(f"Driver {driver.name} is not available for dispatch.")

        if vehicle and driver:
            try:
                cargo = float(cargo_weight_kg)
                if cargo <= 0:
                    errors.append("Cargo weight must be greater than 0.")
                elif cargo > vehicle.max_load_kg:
                    errors.append(
                        f"Cargo weight ({cargo} kg) exceeds vehicle max load "
                        f"({vehicle.max_load_kg} kg)."
                    )
            except ValueError:
                errors.append("Invalid cargo weight.")
        else:
            cargo = 0

        if not source:
            errors.append("Source is required.")
        if not destination:
            errors.append("Destination is required.")
        planned_dist = 0
        try:
            planned_dist = float(planned_distance_km)
            if planned_dist <= 0:
                errors.append("Planned distance must be greater than 0.")
        except ValueError:
            errors.append("Invalid planned distance.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "trips/create.html", vehicles=vehicles, drivers=drivers
            )

        trip = Trip(
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            source=source,
            destination=destination,
            cargo_weight_kg=cargo,
            planned_distance_km=planned_dist,
            status="Draft",
        )
        db.session.add(trip)
        if safe_commit():
            flash("Trip created as draft. Dispatch when ready.", "success")
        return redirect(url_for("trips.list_trips"))

    return render_template("trips/create.html", vehicles=vehicles, drivers=drivers)


@trips_bp.route("/<int:trip_id>")
@login_required
def view_trip(trip_id):
    trip = get_or_404(Trip, trip_id)
    return render_template("trips/view.html", trip=trip)


@trips_bp.route("/<int:trip_id>/dispatch", methods=["POST"])
@login_required
@role_required("fleet_manager", "driver")
def dispatch_trip(trip_id):
    trip = get_or_404(Trip, trip_id)

    if trip.status != "Draft":
        flash("Only draft trips can be dispatched.", "warning")
        return redirect(url_for("trips.view_trip", trip_id=trip.id))

    vehicle = db.session.get(Vehicle, trip.vehicle_id)
    driver = db.session.get(Driver, trip.driver_id)

    if not vehicle or not vehicle.is_available_for_dispatch:
        flash(f"Vehicle is no longer available.", "danger")
        return redirect(url_for("trips.view_trip", trip_id=trip.id))
    if not driver or not driver.is_available_for_dispatch:
        flash(f"Driver is no longer available.", "danger")
        return redirect(url_for("trips.view_trip", trip_id=trip.id))

    trip.status = "Dispatched"
    trip.dispatched_at = datetime.now(timezone.utc).replace(tzinfo=None)
    vehicle.status = "On Trip"
    driver.status = "On Trip"

    if safe_commit():
        flash("Trip dispatched. Vehicle and driver are now On Trip.", "success")
    return redirect(url_for("trips.view_trip", trip_id=trip.id))


@trips_bp.route("/<int:trip_id>/complete", methods=["POST"])
@login_required
@role_required("fleet_manager", "driver")
def complete_trip(trip_id):
    trip = get_or_404(Trip, trip_id)

    if trip.status != "Dispatched":
        flash("Only dispatched trips can be completed.", "warning")
        return redirect(url_for("trips.view_trip", trip_id=trip.id))

    try:
        actual_distance = float(request.form.get("actual_distance_km", 0))
        fuel_consumed = float(request.form.get("fuel_consumed_l", 0))
        odometer_reading = float(request.form.get("odometer_reading", 0))
    except ValueError:
        flash("Invalid distance or fuel values.", "danger")
        return redirect(url_for("trips.view_trip", trip_id=trip.id))

    trip.actual_distance_km = actual_distance
    trip.fuel_consumed_l = fuel_consumed
    trip.status = "Completed"
    trip.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    vehicle = db.session.get(Vehicle, trip.vehicle_id)
    driver = db.session.get(Driver, trip.driver_id)

    if vehicle:
        if odometer_reading > vehicle.odometer:
            vehicle.odometer = odometer_reading
        if vehicle.status == "On Trip":
            vehicle.status = "Available"

    if driver:
        if driver.status == "On Trip":
            driver.status = "Available"

    if fuel_consumed > 0:
        # auto-create a fuel expense entry at ₹100/L (diesel price roughly)
        # TODO: let the fleet manager set the fuel price per vehicle
        #       maybe add a settings page? for now this works fine
        fuel_expense = FuelExpense(
            vehicle_id=trip.vehicle_id,
            trip_id=trip.id,
            expense_type="Fuel",
            liters=fuel_consumed,
            cost=fuel_consumed * 100,
            date=date.today(),
            notes=f"Fuel for trip #{trip.id}: {trip.source} → {trip.destination}",
        )
        db.session.add(fuel_expense)

    efficiency = trip.fuel_efficiency
    msg = f"Trip completed. Vehicle and driver are now Available."
    if efficiency:
        msg += f" Fuel efficiency: {efficiency} km/L."

    if safe_commit():
        flash(msg, "success")
    return redirect(url_for("trips.view_trip", trip_id=trip.id))


@trips_bp.route("/<int:trip_id>/cancel", methods=["POST"])
@login_required
@role_required("fleet_manager")
def cancel_trip(trip_id):
    trip = get_or_404(Trip, trip_id)

    if trip.status not in ("Draft", "Dispatched"):
        flash("Only draft or dispatched trips can be cancelled.", "warning")
        return redirect(url_for("trips.view_trip", trip_id=trip.id))

    was_dispatched = trip.status == "Dispatched"
    trip.status = "Cancelled"

    if was_dispatched:
        vehicle = db.session.get(Vehicle, trip.vehicle_id)
        driver = db.session.get(Driver, trip.driver_id)
        if vehicle and vehicle.status == "On Trip":
            vehicle.status = "Available"
        if driver and driver.status == "On Trip":
            driver.status = "Available"

    if safe_commit():
        flash("Trip cancelled. Vehicle and driver restored to Available.", "info")
    return redirect(url_for("trips.view_trip", trip_id=trip.id))


@trips_bp.route("/<int:trip_id>/receipt")
@login_required
def trip_receipt(trip_id):
    trip = get_or_404(Trip, trip_id)
    if trip.status != "Completed":
        flash("Receipts are only available for completed trips.", "warning")
        return redirect(url_for("trips.view_trip", trip_id=trip.id))

    dist = trip.actual_distance_km if trip.actual_distance_km is not None else (trip.planned_distance_km or 0)
    revenue = dist * 150
    fuel_cost = sum(e.cost for e in trip.fuel_expenses if e.expense_type == "Fuel")
    toll_cost = sum(e.cost for e in trip.fuel_expenses if e.expense_type == "Toll")
    total_expense = fuel_cost + toll_cost

    return render_template("trips/receipt.html", trip=trip, revenue=revenue,
                           fuel_cost=fuel_cost, toll_cost=toll_cost, total_expense=total_expense)
