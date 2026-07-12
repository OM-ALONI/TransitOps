from datetime import datetime, date, timedelta, timezone
from app import db, login_manager
from flask_login import UserMixin

# 5 attempts and you're out for 15 mins
# we learned this pattern from a cybersecurity elective lol
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# helper to get current UTC time without timezone info
# flask asked for naive datetimes so here we are
_utcnow = lambda: datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model, UserMixin):
    """user table - handles login + role based access
    roles: fleet_manager (boss), driver, safety_officer, financial_analyst"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(
        db.Enum("fleet_manager", "driver", "safety_officer", "financial_analyst",
                name="user_role_enum"),
        nullable=False,
    )
    full_name = db.Column(db.String(100), nullable=False)
    # lockout stuff — added after realizing brute force was possible
    failed_login_attempts = db.Column(db.Integer, default=0)
    account_locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    @property
    def is_locked(self):
        """check if this guy is locked out"""
        if self.account_locked_until and self.account_locked_until > _utcnow():
            return True
        if self.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            return True
        return False

    @property
    def lockout_remaining_seconds(self):
        """how many seconds till they can try again"""
        if not self.account_locked_until:
            return 0
        remaining = (self.account_locked_until - _utcnow()).total_seconds()
        return max(0, int(remaining))

    @property
    def remaining_attempts(self):
        return max(0, MAX_LOGIN_ATTEMPTS - self.failed_login_attempts)

    def register_failed_attempt(self):
        """add one to the fail counter, lock if needed"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            self.account_locked_until = _utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)

    def reset_login_attempts(self):
        """clear everything on successful login"""
        self.failed_login_attempts = 0
        self.account_locked_until = None

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Vehicle(db.Model):
    """each row is one vehicle in the fleet
    statuses: Available -> On Trip -> In Shop -> Retired (end of life)
    the status gets auto-changed by trip dispatch and maintenance workflow"""

    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    reg_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    model_name = db.Column(db.String(100), nullable=False)
    vehicle_type = db.Column(
        # using enum for type so we can filter by type on the vehicles page
        # could've used a separate table but this is simpler
        db.Enum("Truck", "Van", "Pickup", "Trailer", "Bus", name="vehicle_type_enum"),
        nullable=False,
    )
    max_load_kg = db.Column(db.Float, nullable=False)
    odometer = db.Column(db.Float, default=0.0)
    acquisition_cost = db.Column(db.Float, default=0.0)
    status = db.Column(
        db.Enum("Available", "On Trip", "In Shop", "Retired", name="vehicle_status_enum"),
        nullable=False,
        default="Available",
    )
    created_at = db.Column(db.DateTime, default=_utcnow)

    trips = db.relationship("Trip", backref="vehicle", lazy="dynamic")
    maintenance_logs = db.relationship("MaintenanceLog", backref="vehicle", lazy="dynamic")
    fuel_expenses = db.relationship("FuelExpense", backref="vehicle", lazy="dynamic")

    @property
    def is_available_for_dispatch(self):
        return self.status == "Available"

    @property
    def is_active(self):
        return self.status not in ("Retired",)

    def __repr__(self):
        return f"<Vehicle {self.reg_number} ({self.status})>"


class Driver(db.Model):
    """driver profiles — need valid license to be assigned to trips
    statuses: Available -> On Trip -> Off Duty -> Suspended"""

    __tablename__ = "drivers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    license_category = db.Column(db.String(10), nullable=False)
    license_expiry = db.Column(db.Date, nullable=False)
    contact = db.Column(db.String(20), nullable=False)
    safety_score = db.Column(db.Integer, default=100)
    status = db.Column(
        db.Enum("Available", "On Trip", "Off Duty", "Suspended",
                name="driver_status_enum"),
        nullable=False,
        default="Available",
    )
    created_at = db.Column(db.DateTime, default=_utcnow)

    trips = db.relationship("Trip", backref="driver", lazy="dynamic")

    @property
    def is_available_for_dispatch(self):
        """driver can only be assigned if: available, not suspended, license valid"""
        return (
            self.status == "Available"
            and self.status != "Suspended"
            and self.license_expiry > date.today()
        )

    @property
    def license_expired(self):
        return self.license_expiry <= date.today()

    @property
    def days_until_license_expiry(self):
        return (self.license_expiry - date.today()).days

    def __repr__(self):
        return f"<Driver {self.name} ({self.status})>"


class Trip(db.Model):
    """main workflow table — Draft -> Dispatched -> Completed / Cancelled
    contains all the business rules for cargo validation and status transitions"""

    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False)
    source = db.Column(db.String(200), nullable=False)
    destination = db.Column(db.String(200), nullable=False)
    cargo_weight_kg = db.Column(db.Float, nullable=False)
    planned_distance_km = db.Column(db.Float, nullable=False)
    actual_distance_km = db.Column(db.Float, nullable=True)
    fuel_consumed_l = db.Column(db.Float, nullable=True)  # filled when trip completes
    status = db.Column(
        db.Enum("Draft", "Dispatched", "Completed", "Cancelled", name="trip_status_enum"),
        nullable=False,
        default="Draft",
    )
    created_at = db.Column(db.DateTime, default=_utcnow)
    dispatched_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    fuel_expenses = db.relationship("FuelExpense", backref="trip", lazy="dynamic")

    @property
    def fuel_efficiency(self):
        """km per litre — only makes sense if we have both numbers"""
        if self.fuel_consumed_l and self.actual_distance_km and self.fuel_consumed_l > 0:
            return round(self.actual_distance_km / self.fuel_consumed_l, 2)
        return None

    def __repr__(self):
        return f"<Trip {self.id}: {self.source} → {self.destination} ({self.status})>"


class MaintenanceLog(db.Model):
    """maintenance events — creating one auto-switches vehicle to 'In Shop'
    closing it puts the vehicle back to 'Available' (unless it's retired)"""

    __tablename__ = "maintenance_logs"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    cost = db.Column(db.Float, default=0.0)
    start_date = db.Column(db.DateTime, default=_utcnow)
    end_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def __repr__(self):
        return f"<MaintenanceLog {self.id}: {self.description[:30]}...>"


class FuelExpense(db.Model):
    """fuel logs + tolls + misc expenses per vehicle
    optionally linked to a trip for better tracking"""

    __tablename__ = "fuel_expenses"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=True)
    expense_type = db.Column(
        db.Enum("Fuel", "Toll", "Maintenance", "Other", name="expense_type_enum"),
        nullable=False,
        default="Fuel",
    )
    liters = db.Column(db.Float, nullable=True)
    cost = db.Column(db.Float, nullable=False, default=0.0)
    date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def __repr__(self):
        return f"<FuelExpense {self.id}: {self.expense_type} ${self.cost:.2f}>"
