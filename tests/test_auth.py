"""Authentication tests: login, logout, hashing, inactive accounts, sessions."""

from extensions import db
from models.audit import AuditLog
from models.user import User
from tests.conftest import PASSWORDS, login, login_as


def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Sign in" in response.data


def test_administrator_can_log_in(client, admin_user):
    response = login(client, "admin@test.local", PASSWORDS["admin"])
    assert response.status_code == 200
    assert b"Administrator dashboard" in response.data
    # The session is established - a protected page is now reachable.
    assert client.get("/equipment/").status_code == 200


def test_ict_officer_can_log_in(client, officer_user):
    response = login(client, "officer1@test.local", PASSWORDS["officer"])
    assert response.status_code == 200
    assert b"ICT Officer dashboard" in response.data


def test_viewer_can_log_in(client, viewer_user):
    response = login(client, "viewer@test.local", PASSWORDS["viewer"])
    assert response.status_code == 200
    assert b"Inventory overview" in response.data


def test_invalid_credentials_are_rejected(client, admin_user):
    response = login(client, "admin@test.local", "wrong-password")
    assert b"Invalid email address or password" in response.data
    # Still anonymous: a protected page redirects to the login form.
    assert client.get("/equipment/").status_code == 302


def test_unknown_email_gets_the_same_message(client):
    response = login(client, "nobody@test.local", "whatever-123")
    assert b"Invalid email address or password" in response.data


def test_password_is_hashed_and_verified(app, admin_user):
    stored = db.session.get(User, admin_user.id)
    assert stored.password_hash != PASSWORDS["admin"]
    assert PASSWORDS["admin"] not in stored.password_hash
    assert stored.password_hash.startswith(("scrypt:", "pbkdf2:"))
    assert stored.check_password(PASSWORDS["admin"]) is True
    assert stored.check_password("not-the-password") is False


def test_logout_ends_the_session(client, admin_user):
    login_as(client, "admin")
    assert client.get("/equipment/").status_code == 200

    response = client.post("/logout", follow_redirects=True)
    assert b"You have been signed out" in response.data
    assert client.get("/equipment/").status_code == 302


def test_inactive_account_cannot_log_in(client, officer_user):
    officer_user.is_active = False
    db.session.commit()

    response = login(client, "officer1@test.local", PASSWORDS["officer"])
    assert b"deactivated" in response.data
    # No session was created.
    assert client.get("/faults/").status_code == 302


def test_login_form_validation(client):
    response = client.post("/login", data={"email": "", "password": ""})
    assert response.status_code == 200
    assert b"Enter your email address" in response.data


def test_successful_and_failed_logins_are_audited(app, client, admin_user):
    login(client, "admin@test.local", "wrong-password")
    login(client, "admin@test.local", PASSWORDS["admin"])

    actions = {row.action for row in db.session.query(AuditLog).all()}
    assert "login_failed" in actions
    assert "login" in actions
    # The audit description never contains the password.
    for row in db.session.query(AuditLog).all():
        assert "wrong-password" not in row.description
        assert PASSWORDS["admin"] not in row.description


def test_profile_page_shows_the_signed_in_user(client, officer_user):
    login_as(client, "officer")
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"officer1@test.local" in response.data


def test_user_can_change_own_password(client, officer_user):
    login_as(client, "officer")
    response = client.post(
        "/profile",
        data={
            "password-current_password": PASSWORDS["officer"],
            "password-password": "BrandNew@2026",
            "password-confirm_password": "BrandNew@2026",
            "password-submit": "Change password",
        },
        follow_redirects=True,
    )
    assert b"password has been changed" in response.data

    stored = db.session.get(User, officer_user.id)
    assert stored.check_password("BrandNew@2026")


def test_password_change_requires_the_current_password(client, officer_user):
    login_as(client, "officer")
    response = client.post(
        "/profile",
        data={
            "password-current_password": "not-my-password",
            "password-password": "BrandNew@2026",
            "password-confirm_password": "BrandNew@2026",
            "password-submit": "Change password",
        },
        follow_redirects=True,
    )
    assert b"current password is not correct" in response.data

    stored = db.session.get(User, officer_user.id)
    assert stored.check_password(PASSWORDS["officer"])


def test_short_password_is_rejected_by_form(client, officer_user):
    login_as(client, "officer")
    response = client.post(
        "/profile",
        data={
            "password-current_password": PASSWORDS["officer"],
            "password-password": "short1",
            "password-confirm_password": "short1",
            "password-submit": "Change password",
        },
        follow_redirects=True,
    )
    assert b"at least 8 characters" in response.data
