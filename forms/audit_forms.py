"""Filter form for the read-only audit trail."""

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, SubmitField
from wtforms.validators import Optional

from forms.base import FilterFormMixin, user_choices

#: Every action string the audit service can write.
AUDIT_ACTIONS = (
    "create",
    "update",
    "status_change",
    "assign",
    "retire",
    "login",
    "logout",
    "login_failed",
    "login_blocked",
    "deactivate",
    "activate",
)

#: Entity labels used by the audit service.
AUDIT_ENTITIES = (
    "equipment",
    "fault_report",
    "maintenance_record",
    "maintenance_schedule",
    "department",
    "equipment_category",
    "user",
)


class AuditFilterForm(FilterFormMixin, FlaskForm):
    """Search and filter the audit trail (read-only, so CSRF is off)."""

    search = StringField(
        "Search", render_kw={"placeholder": "Text in the description"}
    )
    action = SelectField(
        "Action",
        choices=[("", "All actions")]
        + [(action, action.replace("_", " ").title()) for action in AUDIT_ACTIONS],
        coerce=str,
    )
    entity_type = SelectField(
        "Entity",
        choices=[("", "All entities")]
        + [(entity, entity.replace("_", " ").title()) for entity in AUDIT_ENTITIES],
        coerce=str,
    )
    user_id = SelectField("User", coerce=int)
    date_from = DateField("From", validators=[Optional()])
    date_to = DateField("To", validators=[Optional()])
    submit = SubmitField("Apply filters")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id.choices = [(0, "Any user")] + [
            (user_id, name) for user_id, name in user_choices()
        ]
