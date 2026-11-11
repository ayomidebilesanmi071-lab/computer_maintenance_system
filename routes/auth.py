"""Authentication routes: login, logout and self-service profile."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from forms import ChangePasswordForm, LoginForm, ProfileForm
from services import audit_service
from services.errors import ServiceError
from services.user_service import UserService

auth_bp = Blueprint("auth", __name__)

# Deliberately vague: never reveal whether an address is registered.
INVALID_CREDENTIALS = "Invalid email address or password."


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate a user and start a session."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = UserService.find_by_email(email)

        if user is None or not user.check_password(form.password.data):
            # Record the attempt for the audit trail (never the password).
            audit_service.AuditService.log(
                None,
                "login_failed",
                "user",
                user.id if user else None,
                f"Failed sign-in attempt for {email}.",
            )
            db.session.commit()
            flash(INVALID_CREDENTIALS, "error")
        elif not user.is_active:
            audit_service.AuditService.log(
                user,
                "login_blocked",
                "user",
                user.id,
                f"Sign-in blocked for deactivated account {user.email}.",
            )
            db.session.commit()
            flash(
                "This account has been deactivated. Please contact an "
                "administrator.",
                "error",
            )
        else:
            login_user(user, remember=bool(form.remember.data))
            audit_service.AuditService.log_login(user)
            db.session.commit()
            flash(f"Welcome back, {user.full_name}.", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """End the session (POST only, so the CSRF token is required)."""
    user = current_user
    audit_service.AuditService.log_logout(user)
    db.session.commit()
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """View your own account details and credentials."""
    profile_form = ProfileForm(prefix="profile")
    password_form = ChangePasswordForm(prefix="password")

    if profile_form.submit.data and profile_form.validate_on_submit():
        data = UserService.find_by_email(profile_form.email.data)
        if data is not None and data.id != current_user.id:
            flash("Another account already uses that email address.", "error")
        else:
            current_user.full_name = profile_form.full_name.data.strip()
            current_user.email = profile_form.email.data.strip().lower()
            audit_service.AuditService.log(
                current_user,
                audit_service.ACTION_UPDATE,
                "user",
                current_user.id,
                f"{current_user.full_name} updated their own profile.",
            )
            db.session.commit()
            flash("Your profile has been updated.", "success")
            return redirect(url_for("auth.profile"))

    elif password_form.submit.data and password_form.validate_on_submit():
        try:
            UserService.change_own_password(
                current_user,
                password_form.current_password.data,
                password_form.password.data,
            )
            db.session.commit()
            flash("Your password has been changed.", "success")
            return redirect(url_for("auth.profile"))
        except ServiceError as error:
            db.session.rollback()
            flash(str(error), "error")

    if profile_form.submit.data and not profile_form.validate_on_submit():
        flash("Please correct the highlighted profile fields.", "error")
    if password_form.submit.data and not password_form.validate_on_submit():
        flash("Please correct the highlighted password fields.", "error")

    return render_template(
        "auth/profile.html",
        profile_form=profile_form,
        password_form=password_form,
        audit_entries=audit_service.AuditService.history("user", current_user.id, limit=10),
    )
