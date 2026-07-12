"""seed the db with demo data so we don't start with empty tables
   run this once before first launch — `python seed.py`
   all passwords are 'admin123' for easy testing"""

from datetime import date, datetime, timedelta, timezone
from app import create_app, db, bcrypt
from app.models import User, Vehicle, Driver, Trip, MaintenanceLog, FuelExpense

app = create_app()

_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)

with app.app_context():
    db.drop_all()
    db.create_all()

    # ----------  4 users (one for each role)  ----------
    users = [
        User(
            full_name="Rahul Sharma",
            email="rahul@transitops.com",
            password_hash=bcrypt.generate_password_hash("admin123").decode("utf-8"),
            role="fleet_manager",
        ),
        User(
            full_name="Priya Patel",
            email="priya@transitops.com",
            password_hash=bcrypt.generate_password_hash("admin123").decode("utf-8"),
            role="driver",
        ),
        User(
            full_name="Amit Singh",
            email="amit@transitops.com",
            password_hash=bcrypt.generate_password_hash("admin123").decode("utf-8"),
            role="safety_officer",
        ),
        User(
            full_name="Neha Gupta",
            email="neha@transitops.com",
            password_hash=bcrypt.generate_password_hash("admin123").decode("utf-8"),
            role="financial_analyst",
        ),
    ]
    db.session.add_all(users)
    db.session.commit()
    print(f"Seeded {len(users)} users.")

    # ── Vehicles ──
    vehicles = [
        Vehicle(reg_number="MH-12-AB-2024", model_name="Tata Ace Gold", vehicle_type="Van",
                max_load_kg=500, odometer=45315, acquisition_cost=420000, status="Available"),
        Vehicle(reg_number="MH-04-CD-7890", model_name="Ashok Leyland Partner 6W", vehicle_type="Truck",
                max_load_kg=18000, odometer=120815, acquisition_cost=1850000, status="Available"),
        Vehicle(reg_number="KA-05-EF-3456", model_name="Mahindra Bolero Pik-Up", vehicle_type="Pickup",
                max_load_kg=1000, odometer=38150, acquisition_cost=780000, status="On Trip"),
        Vehicle(reg_number="DL-01-GH-9012", model_name="Tata Signa 4018.S", vehicle_type="Trailer",
                max_load_kg=25000, odometer=62000, acquisition_cost=2400000, status="In Shop"),
        Vehicle(reg_number="TN-09-IJ-5678", model_name="Force Traveller 26", vehicle_type="Bus",
                max_load_kg=3500, odometer=89000, acquisition_cost=1450000, status="Available"),
        Vehicle(reg_number="GJ-06-KL-1234", model_name="BharatBenz 2623R", vehicle_type="Truck",
                max_load_kg=16000, odometer=210000, acquisition_cost=2200000, status="Retired"),
        Vehicle(reg_number="MH-14-MN-8901", model_name="Tata Yodha 2.0", vehicle_type="Pickup",
                max_load_kg=1200, odometer=15200, acquisition_cost=850000, status="Available"),
        Vehicle(reg_number="UP-32-OP-4567", model_name="Ashok Leyland Dost+", vehicle_type="Van",
                max_load_kg=750, odometer=62180, acquisition_cost=550000, status="Available"),
        Vehicle(reg_number="RJ-19-QR-7890", model_name="Eicher Pro 3015", vehicle_type="Truck",
                max_load_kg=9500, odometer=98000, acquisition_cost=1500000, status="Available"),
        Vehicle(reg_number="HR-26-ST-2345", model_name="Mahindra Jeeto Strong", vehicle_type="Van",
                max_load_kg=400, odometer=32500, acquisition_cost=320000, status="Available"),
    ]
    db.session.add_all(vehicles)
    db.session.commit()
    # print(f'Debug: vehicle IDs = {[v.id for v in vehicles]}')
    print(f"Seeded {len(vehicles)} vehicles.")

    # ── Drivers ──
    drivers = [
        Driver(name="Ramesh Kumar", license_number="MH-2024-07890", license_category="C",
               license_expiry=date.today() + timedelta(days=365), contact="+91 98765 40101",
               safety_score=95, status="Available"),
        Driver(name="Sneha Patil", license_number="KA-2024-04521", license_category="CE",
               license_expiry=date.today() + timedelta(days=180), contact="+91 87654 30102",
               safety_score=88, status="Available"),
        Driver(name="Vikram Singh", license_number="DL-2024-03310", license_category="C",
               license_expiry=date.today() + timedelta(days=20), contact="+91 76543 20103",
               safety_score=72, status="On Trip"),
        Driver(name="Ananya Sharma", license_number="RJ-2024-09901", license_category="D",
               license_expiry=date.today() - timedelta(days=10), contact="+91 65432 10104",
               safety_score=60, status="Suspended"),
        Driver(name="Arjun Reddy", license_number="TS-2024-05566", license_category="C",
               license_expiry=date.today() + timedelta(days=500), contact="+91 54321 00105",
               safety_score=90, status="Off Duty"),
    ]
    db.session.add_all(drivers)
    db.session.commit()
    # print(f'Debug: driver IDs = {[d.id for d in drivers]}')
    print(f"Seeded {len(drivers)} drivers.")

    # ── Trips ──
    van = Vehicle.query.filter_by(reg_number="MH-12-AB-2024").first()
    truck = Vehicle.query.filter_by(reg_number="MH-04-CD-7890").first()
    pickup = Vehicle.query.filter_by(reg_number="KA-05-EF-3456").first()
    alex = Driver.query.filter_by(license_number="MH-2024-07890").first()
    maria = Driver.query.filter_by(license_number="KA-2024-04521").first()
    james = Driver.query.filter_by(license_number="DL-2024-03310").first()

    trips = [
        Trip(vehicle_id=van.id, driver_id=alex.id, source="Mumbai Central Warehouse",
             destination="Pune IT Park", cargo_weight_kg=450, planned_distance_km=150,
             actual_distance_km=148, fuel_consumed_l=14.2, status="Completed",
             dispatched_at=_now() - timedelta(days=3),
             completed_at=_now() - timedelta(days=3, hours=-4),
             created_at=_now() - timedelta(days=3, hours=-1)),
        Trip(vehicle_id=truck.id, driver_id=maria.id, source="Delhi NCR Depot",
             destination="Jaipur Distribution Hub", cargo_weight_kg=15000,
             planned_distance_km=280, actual_distance_km=275, fuel_consumed_l=95.5,
             status="Completed",
             dispatched_at=_now() - timedelta(days=1),
             completed_at=_now() - timedelta(days=1, hours=-6),
             created_at=_now() - timedelta(days=1, hours=-2)),
        Trip(vehicle_id=pickup.id, driver_id=james.id, source="Bengaluru Local Yard",
             destination="Electronic City Phase 2", cargo_weight_kg=800,
             planned_distance_km=25, status="Dispatched",
             dispatched_at=_now() - timedelta(hours=2),
             created_at=_now() - timedelta(hours=3)),
        Trip(vehicle_id=van.id, driver_id=alex.id, source="Mumbai Central Warehouse",
             destination="Thane Industrial Estate", cargo_weight_kg=300,
             planned_distance_km=35, status="Draft",
             created_at=_now() - timedelta(hours=5)),
    ]
    db.session.add_all(trips)
    db.session.commit()
    print(f"Seeded {len(trips)} trips.")

    # ── Maintenance Logs ──
    trailer = Vehicle.query.filter_by(reg_number="DL-01-GH-9012").first()
    maintenance_logs = [
        MaintenanceLog(vehicle_id=trailer.id, description="Hydraulic brake system overhaul",
                       cost=2800, start_date=_now() - timedelta(days=15),
                       is_active=True),
        MaintenanceLog(vehicle_id=van.id, description="Oil change & filter replacement",
                       cost=120, start_date=_now() - timedelta(days=30),
                       end_date=_now() - timedelta(days=29), is_active=False),
        MaintenanceLog(vehicle_id=truck.id, description="Tire rotation & alignment",
                       cost=450, start_date=_now() - timedelta(days=45),
                       end_date=_now() - timedelta(days=44), is_active=False),
    ]
    db.session.add_all(maintenance_logs)
    db.session.commit()
    print(f"Seeded {len(maintenance_logs)} maintenance logs.")

    # ── Fuel & Expenses ──
    fuel_expenses = [
        FuelExpense(vehicle_id=van.id, trip_id=1, expense_type="Fuel", liters=14.2,
                    cost=1500, date=date.today() - timedelta(days=3),
                    notes="Fuel for Mumbai-Pune trip"),
        FuelExpense(vehicle_id=truck.id, trip_id=2, expense_type="Fuel", liters=95.5,
                    cost=9500, date=date.today() - timedelta(days=1),
                    notes="Diesel refill at Delhi-Jaipur highway"),
        FuelExpense(vehicle_id=van.id, expense_type="Toll", liters=None,
                    cost=320, date=date.today() - timedelta(days=3),
                    notes="Mumbai-Pune Expressway toll"),
        FuelExpense(vehicle_id=truck.id, expense_type="Toll", liters=None,
                    cost=850, date=date.today() - timedelta(days=1),
                    notes="Delhi-Jaipur Highway toll"),
        FuelExpense(vehicle_id=trailer.id, expense_type="Maintenance", liters=None,
                    cost=2800, date=date.today() - timedelta(days=15),
                    notes="Brake system — attached to maintenance log"),
        FuelExpense(vehicle_id=pickup.id, expense_type="Fuel", liters=28.0,
                    cost=2600, date=date.today() - timedelta(days=5),
                    notes="Weekly diesel top-up — Bengaluru"),
    ]
    db.session.add_all(fuel_expenses)
    db.session.commit()
    print(f"Seeded {len(fuel_expenses)} fuel/expense records.")

    print("\n--- Seed Complete ---")
    print("Login credentials (all passwords: admin123):")
    print("  Fleet Manager:     rahul@transitops.com")
    print("  Driver:            priya@transitops.com")
    print("  Safety Officer:    amit@transitops.com")
    print("  Financial Analyst: neha@transitops.com")
