import time
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User, MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES
from app.utils import safe_commit

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/welcome")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return render_template("landing.html")

# basic rate limiter — stores (count, window) per IP, resets every 2s
# TODO: move to redis if this ever goes to production lol
_rate_limit_store = {}


def _check_rate_limit(ip):
    now = time.time()
    if ip in _rate_limit_store:
        attempts, window_start = _rate_limit_store[ip]
        if now - window_start < 2.0:
            if attempts >= 5:
                return False
            _rate_limit_store[ip] = (attempts + 1, window_start)
        else:
            _rate_limit_store[ip] = (1, now)
    else:
        _rate_limit_store[ip] = (1, now)
    return True


def _render_login(**extra):
    return render_template(
        "auth/login.html",
        max_attempts=MAX_LOGIN_ATTEMPTS,
        lockout_minutes=LOCKOUT_DURATION_MINUTES,
        **extra,
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "danger")
            return _render_login()

        user = User.query.filter_by(email=email).first()

        if user is None:
            if not _check_rate_limit(request.remote_addr):
                flash("Too many login attempts. Please wait a moment.", "warning")
            else:
                flash("Invalid email or password.", "danger")
            return _render_login()

        if user.is_locked:
            remaining = user.lockout_remaining_seconds
            minutes = remaining // 60
            seconds = remaining % 60
            flash(
                f"Account locked after {MAX_LOGIN_ATTEMPTS} failed attempts. "
                f"Try again in {minutes}m {seconds}s.",
                "danger",
            )
            return _render_login()

        if not _check_rate_limit(request.remote_addr):
            flash("Too many login attempts. Please wait a moment.", "warning")
            return _render_login()

        if bcrypt.check_password_hash(user.password_hash, password):
            user.reset_login_attempts()
            safe_commit()
            login_user(user, remember=request.form.get("remember"))
            next_page = request.args.get("next")
            flash(f"Welcome back, {user.full_name}!", "success")
            return redirect(next_page or url_for("dashboard.index"))

        user.register_failed_attempt()
        safe_commit()

        remaining = user.remaining_attempts
        if user.is_locked:
            flash(
                f"Account locked after {MAX_LOGIN_ATTEMPTS} failed attempts. "
                f"Try again in 15 minutes.",
                "danger",
            )
        elif remaining == 1:
            flash(
                f"Invalid password. {remaining} attempt remaining before account lockout.",
                "danger",
            )
        else:
            flash(
                f"Invalid password. {remaining} attempts remaining before account lockout.",
                "warning",
            )

    return _render_login()


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "driver")

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if User.query.filter_by(email=email).first():
            errors.append("Email is already registered.")
        if role not in ("fleet_manager", "driver", "safety_officer", "financial_analyst"):
            errors.append("Invalid role selected.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("auth/register.html")

        hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(full_name=full_name, email=email, password_hash=hashed_pw, role=role)
        db.session.add(user)
        if not safe_commit():
            return render_template("auth/register.html")

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "change_password":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")

            errors = []
            if not bcrypt.check_password_hash(current_user.password_hash, current_pw):
                errors.append("Current password is incorrect.")
            if len(new_pw) < 6:
                errors.append("New password must be at least 6 characters.")
            if new_pw != confirm_pw:
                errors.append("New passwords do not match.")

            if errors:
                for e in errors:
                    flash(e, "danger")
            else:
                current_user.password_hash = bcrypt.generate_password_hash(new_pw).decode("utf-8")
                if safe_commit():
                    flash("Password changed successfully.", "success")

        elif action == "update_profile":
            full_name = request.form.get("full_name", "").strip()
            if full_name:
                current_user.full_name = full_name
                if safe_commit():
                    flash("Profile updated.", "success")
            else:
                flash("Name cannot be empty.", "danger")

        return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html")
