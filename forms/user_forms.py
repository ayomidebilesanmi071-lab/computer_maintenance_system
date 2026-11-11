"""Administrator account-management forms."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

from forms.base import FilterFormMixin, role_choices
from models.constants import ROLE_LABELS
from services.user_service import MIN_PASSWORD_LENGTH


class UserForm(FlaskForm):
    """Create or edit an account (administrator only).

    ``editing`` is toggled by the route: when editing, the password fields are
    optional ("leave blank to keep the current password").
    """

    full_name = StringField(
        "Full name",
        validators=[DataRequired(message="Full name is required."), Length(min=2, max=120)],
    )
    email = StringField(
        "Email address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Enter a valid email address."),
            Length(max=255),
        ],
        render_kw={"autocomplete": "off"},
    )
    role = SelectField(
        "Role", choices=role_choices(), validators=[DataRequired()],
        description="Administrators manage the system, ICT officers handle "
                    "equipment and faults, viewers can only read records.",
    )
    password = PasswordField(
        "Password",
        validators=[Optional(), Length(min=MIN_PASSWORD_LENGTH, max=128)],
        render_kw={"autocomplete": "new-password"},
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[Optional(), EqualTo("password", message="The two passwords do not match.")],
        render_kw={"autocomplete": "new-password"},
    )
    submit = SubmitField("Save account")

    def __init__(self, *args, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.editing = editing
        if not editing:
            # A brand-new account must come with a password.
            self.password.validators = [
                DataRequired(message="Password is required."),
                Length(min=MIN_PASSWORD_LENGTH, max=128),
            ]
            self.confirm_password.validators = [
                DataRequired(message="Confirm the password."),
                EqualTo("password", message="The two passwords do not match."),
            ]
        else:
            self.password.render_kw = {"autocomplete": "new-password",
                                       "placeholder": "Leave blank to keep unchanged"}
            self.confirm_password.render_kw = {"autocomplete": "new-password",
                                               "placeholder": "Leave blank to keep unchanged"}

    def load_user(self, user) -> None:
        self.full_name.data = user.full_name
        self.email.data = user.email
        self.role.data = user.role

    def to_data(self) -> dict:
        return {
            "full_name": self.full_name.data,
            "email": self.email.data,
            "role": self.role.data,
            "password": self.password.data or "",
        }

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role.data, self.role.data)


class UserFilterForm(FilterFormMixin, FlaskForm):
    """Filter controls for the account list."""

    search = StringField("Search", render_kw={"placeholder": "Name or email address"})
    role = SelectField(
        "Role", choices=[("", "All roles")] + role_choices(), coerce=str
    )
    status = SelectField(
        "Account status",
        choices=[
            ("", "All accounts"),
            ("active", "Active only"),
            ("inactive", "Deactivated only"),
        ],
        coerce=str,
    )
    submit = SubmitField("Apply filters")
