from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models import Driver
from app.auth import role_required
from app.utils import safe_commit, get_or_404, apply_sorting, sort_url, sort_icon

drivers_bp = Blueprint("drivers", __name__)


@drivers_bp.route("/")
@login_required
def list_drivers():
    status_filter = request.args.get("status", "")
    search = request.args.get("search", "").strip()

    query = Driver.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(
            (Driver.name.ilike(f"%{search}%"))
            | (Driver.license_number.ilike(f"%{search}%"))
            | (Driver.contact.ilike(f"%{search}%"))
        )

    query, sort_col, sort_order = apply_sorting(
        query, Driver, "created_at",
        ["name", "license_number", "license_category", "license_expiry", "contact", "safety_score", "status", "created_at"],
    )

    drivers = query.all()
    today = date.today()
    return render_template(
        "drivers/list.html",
        drivers=drivers,
        today=today,
        sort_col=sort_col,
        sort_order=sort_order,
    )


@drivers_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("fleet_manager", "safety_officer")
def create_driver():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        license_number = request.form.get("license_number", "").strip().upper()
        license_category = request.form.get("license_category", "").strip()
        license_expiry_str = request.form.get("license_expiry", "")
        contact = request.form.get("contact", "").strip()
        safety_score = request.form.get("safety_score", "100")
        status = request.form.get("status", "Available")

        errors = []
        if not name:
            errors.append("Driver name is required.")
        if not license_number:
            errors.append("License number is required.")
        if Driver.query.filter_by(license_number=license_number).first():
            errors.append("A driver with this license number already exists.")
        if not license_category:
            errors.append("License category is required.")
        license_expiry = None
        try:
            license_expiry = datetime.strptime(license_expiry_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            errors.append("Valid license expiry date is required.")
        if not contact:
            errors.append("Contact number is required.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("drivers/create.html")

        driver = Driver(
            name=name,
            license_number=license_number,
            license_category=license_category,
            license_expiry=license_expiry,
            contact=contact,
            safety_score=int(safety_score) if safety_score else 100,
            status=status,
        )
        db.session.add(driver)
        if safe_commit():
            flash(f"Driver {name} registered successfully.", "success")
        return redirect(url_for("drivers.list_drivers"))

    return render_template("drivers/create.html")


@drivers_bp.route("/<int:driver_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("fleet_manager", "safety_officer")
def edit_driver(driver_id):
    driver = get_or_404(Driver, driver_id)

    if request.method == "POST":
        driver.name = request.form.get("name", driver.name).strip()
        driver.license_category = request.form.get("license_category", driver.license_category)
        try:
            expiry = datetime.strptime(
                request.form.get("license_expiry", ""), "%Y-%m-%d"
            ).date()
            driver.license_expiry = expiry
        except (ValueError, TypeError):
            flash("Invalid license expiry date — using previous.", "warning")
        driver.contact = request.form.get("contact", driver.contact).strip()
        try:
            driver.safety_score = int(request.form.get("safety_score", driver.safety_score))
        except ValueError:
            flash("Invalid safety score — using previous.", "warning")
        driver.status = request.form.get("status", driver.status)

        if safe_commit():
            flash(f"Driver {driver.name} updated.", "success")
        return redirect(url_for("drivers.list_drivers"))

    return render_template("drivers/edit.html", driver=driver)


@drivers_bp.route("/<int:driver_id>/delete", methods=["POST"])
@login_required
@role_required("fleet_manager")
def delete_driver(driver_id):
    driver = get_or_404(Driver, driver_id)
    if driver.trips.count() > 0:
        flash("Cannot delete driver with trip history. Suspend them instead.", "danger")
    else:
        db.session.delete(driver)
        if safe_commit():
            flash("Driver deleted.", "success")
    return redirect(url_for("drivers.list_drivers"))
