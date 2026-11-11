"""Authentication and self-service account forms."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from services.user_service import MIN_PASSWORD_LENGTH


class LoginForm(FlaskForm):
    """Sign-in form.

    Deliberately free of "does this account exist?" validation: the generic
    error message produced by the route never reveals whether an email address
    is registered.
    """

    email = StringField(
        "Email address",
        validators=[DataRequired(message="Enter your email address."), Length(max=255)],
        render_kw={"autocomplete": "username", "autofocus": True,
                   "placeholder": "you@organisation.local"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Enter your password."), Length(max=128)],
        render_kw={"autocomplete": "current-password"},
    )
    remember = BooleanField("Keep me signed in on this device")
    submit = SubmitField("Sign in")


class ProfileForm(FlaskForm):
    """Edit your own name / email address."""

    full_name = StringField(
        "Full name",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    email = StringField(
        "Email address",
        validators=[DataRequired(), Email(message="Enter a valid email address."),
                    Length(max=255)],
    )
    submit = SubmitField("Save profile")


class ChangePasswordForm(FlaskForm):
    """Change your own password - the current one is always required."""

    current_password = PasswordField(
        "Current password", validators=[DataRequired()],
        render_kw={"autocomplete": "current-password"},
    )
    password = PasswordField(
        "New password",
        validators=[
            DataRequired(),
            Length(
                min=MIN_PASSWORD_LENGTH,
                max=128,
                message=f"Use at least {MIN_PASSWORD_LENGTH} characters.",
            ),
        ],
        render_kw={"autocomplete": "new-password"},
    )
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[
            DataRequired(),
            EqualTo("password", message="The two passwords do not match."),
        ],
        render_kw={"autocomplete": "new-password"},
    )
    submit = SubmitField("Change password")
