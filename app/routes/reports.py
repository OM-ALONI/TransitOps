import csv
import io
from datetime import date, datetime
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from sqlalchemy import func
from app import db
from app.models import Vehicle, Trip, FuelExpense, MaintenanceLog
from app.auth import role_required

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

reports_bp = Blueprint("reports", __name__)

# shared helper — computes all the numbers for one vehicle
# used by the reports page, csv export, and pdf export so we don't repeat ourselves
# probably should use a single SQL query instead of per-vehicle queries
# but the dataset is small enough that it doesn't matter for now
def _compute_vehicle_stats(vehicle):
    completed = Trip.query.filter_by(vehicle_id=vehicle.id, status="Completed").all()
    revenue = sum(((t.actual_distance_km or t.planned_distance_km or 0)) * 150 for t in completed)
    fuel_cost = db.session.query(func.coalesce(func.sum(FuelExpense.cost), 0)).filter(
        FuelExpense.vehicle_id == vehicle.id, FuelExpense.expense_type == "Fuel").scalar()
    maint_cost = db.session.query(func.coalesce(func.sum(MaintenanceLog.cost), 0)).filter(
        MaintenanceLog.vehicle_id == vehicle.id).scalar()
    other_cost = db.session.query(func.coalesce(func.sum(FuelExpense.cost), 0)).filter(
        FuelExpense.vehicle_id == vehicle.id, FuelExpense.expense_type.in_(["Toll", "Other"])).scalar()
    op_cost = fuel_cost + maint_cost + other_cost
    total_dist = sum(((t.actual_distance_km if t.actual_distance_km is not None else t.planned_distance_km) or 0) for t in completed)
    total_fuel = sum((t.fuel_consumed_l or 0) for t in completed)
    eff = round(total_dist / total_fuel, 2) if total_fuel > 0 else 0
    roi = round(((revenue - op_cost) / (vehicle.acquisition_cost or 1)) * 100, 2)
    return {
        "vehicle": vehicle, "total_trips": len(completed), "total_distance": round(total_dist, 1),
        "total_fuel": round(total_fuel, 1), "fuel_efficiency": eff, "total_revenue": revenue,
        "fuel_cost": fuel_cost, "maintenance_cost": maint_cost, "other_cost": other_cost,
        "operational_cost": op_cost, "roi": roi,
    }


@reports_bp.route("/")
@login_required
@role_required("fleet_manager", "financial_analyst", "safety_officer")
def index():
    vehicles = Vehicle.query.order_by(Vehicle.reg_number).all()
    report_data = [_compute_vehicle_stats(v) for v in vehicles]
    return render_template("reports/index.html", report_data=report_data)


@reports_bp.route("/export/csv")
@login_required
@role_required("fleet_manager", "financial_analyst")
def export_csv():
    vehicles = Vehicle.query.order_by(Vehicle.reg_number).all()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["Registration", "Model", "Type", "Status", "Max Load (kg)", "Odometer",
                      "Total Trips", "Total Distance (km)", "Total Fuel (L)", "Fuel Efficiency (km/L)",
                      "Revenue", "Fuel Cost", "Maintenance Cost", "Other Cost", "Operational Cost", "ROI (%)"])
    for v in vehicles:
        s = _compute_vehicle_stats(v)
        writer.writerow([v.reg_number, v.model_name, v.vehicle_type, v.status,
                          f"{v.max_load_kg:.0f}", f"{v.odometer:.0f}", s["total_trips"],
                          s["total_distance"], s["total_fuel"], s["fuel_efficiency"],
                          f"\u20b9{s['total_revenue']:,.0f}", f"\u20b9{s['fuel_cost']:,.0f}",
                          f"\u20b9{s['maintenance_cost']:,.0f}", f"\u20b9{s['other_cost']:,.0f}",
                          f"\u20b9{s['operational_cost']:,.0f}", f"{s['roi']}%"])
    output.seek(0)
    return Response(output.getvalue().encode('utf-8-sig'), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=transitops_report_{date.today()}.csv"})


@reports_bp.route("/export/pdf")
@login_required
@role_required("fleet_manager", "financial_analyst")
def export_pdf():
    vehicles = Vehicle.query.order_by(Vehicle.reg_number).all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=15*mm, bottomMargin=10*mm,
                            leftMargin=8*mm, rightMargin=8*mm)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=16, spaceAfter=10,
                                  textColor=colors.HexColor('#0F172A'))
    elements.append(Paragraph(f'TransitOps Fleet Report ({date.today()})', title_style))
    elements.append(Spacer(1, 4*mm))

    header = ['Reg No', 'Model', 'Type', 'Status', 'Max kg', 'Odo', 'Trips', 'Dist km',
              'Fuel L', 'Eff', 'Revenue', 'Fuel Cost', 'Maint', 'Other', 'Op Cost', 'ROI']
    data = [header]
    for v in vehicles:
        s = _compute_vehicle_stats(v)
        data.append([v.reg_number, v.model_name, v.vehicle_type, v.status,
                      f"{v.max_load_kg:.0f}", f"{v.odometer:.0f}", str(s["total_trips"]),
                      f"{s['total_distance']:.0f}", f"{s['total_fuel']:.1f}",
                      f"{s['fuel_efficiency']}", f"₹{s['total_revenue']:,.0f}",
                      f"₹{s['fuel_cost']:,.0f}", f"₹{s['maintenance_cost']:,.0f}",
                      f"₹{s['other_cost']:,.0f}", f"₹{s['operational_cost']:,.0f}", f"{s['roi']}%"])

    col_widths = [52, 70, 38, 38, 35, 35, 28, 38, 35, 28, 48, 48, 40, 40, 48, 38]
    table = Table(data, colWidths=[w*mm for w in col_widths], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment;filename=transitops_report_{date.today()}.pdf'})
