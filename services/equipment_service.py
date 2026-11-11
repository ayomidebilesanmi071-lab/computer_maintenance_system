"""Equipment inventory business logic.

All equipment mutations go through :class:`EquipmentService` so that:

* uniqueness of asset tag / serial number is enforced server-side (not just by
  the HTML form),
* status changes always write an ``EquipmentStatusHistory`` row,
* an audit entry is written in the same transaction,
* retirement never deletes rows - assets are only ever marked ``Retired``.
"""

from datetime import datetime

from sqlalchemy import func, or_, select

from extensions import db
from models.constants import CONDITIONS, OPERATIONAL_STATUSES, STATUS_RETIRED
from models.department import Department
from models.equipment import Equipment, EquipmentCategory, EquipmentStatusHistory
from models.user import User
from services import audit_service
from services.errors import DuplicateError, NotFoundError, ValidationError


class EquipmentService:
    """Domain service for the equipment inventory."""

    # ----------------------------------------------------------- retrieval
    @staticmethod
    def get(equipment_id: int) -> Equipment:
        """Fetch an asset or raise :class:`NotFoundError`."""
        equipment = db.session.get(Equipment, equipment_id)
        if equipment is None:
            raise NotFoundError("Equipment not found.")
        return equipment

    @classmethod
    def get_or_none(cls, equipment_id: int):
        try:
            return cls.get(equipment_id)
        except NotFoundError:
            return None

    @staticmethod
    def find_by_asset_tag(asset_tag: str):
        stmt = select(Equipment).where(
            func.upper(Equipment.asset_tag) == asset_tag.strip().upper()
        )
        return db.session.scalars(stmt).first()

    @staticmethod
    def find_by_serial(serial_number: str):
        if not serial_number or not serial_number.strip():
            return None
        stmt = select(Equipment).where(
            func.upper(Equipment.serial_number) == serial_number.strip().upper()
        )
        return db.session.scalars(stmt).first()

    # ------------------------------------------------------------- create
    @classmethod
    def create(cls, data: dict, actor: User) -> Equipment:
        """Validate and insert a new asset.

        ``data`` is a dict of already form-validated field values.  Business
        rules (duplicate tag/serial, unknown department) are re-checked here
        because the service - not the form - is the security boundary.
        """
        asset_tag = (data.get("asset_tag") or "").strip()
        serial_number = (data.get("serial_number") or "").strip()

        if not asset_tag:
            raise ValidationError("Asset tag is required.", {"asset_tag": "Asset tag is required."})

        existing = cls.find_by_asset_tag(asset_tag)
        if existing is not None:
            raise DuplicateError(
                f"Asset tag '{asset_tag}' is already registered "
                f"({existing.equipment_name})."
            )

        if serial_number:
            dup = cls.find_by_serial(serial_number)
            if dup is not None:
                raise DuplicateError(
                    f"Serial number '{serial_number}' already belongs to {dup.asset_tag}."
                )

        department = db.session.get(Department, data.get("department_id"))
        if department is None:
            raise ValidationError("Please select a valid department.",
                                  {"department_id": "Unknown department."})

        equipment = Equipment(
            asset_tag=asset_tag,
            equipment_name=data["equipment_name"].strip(),
            equipment_type=data["equipment_type"],
            manufacturer=(data.get("manufacturer") or "").strip() or None,
            model=(data.get("model") or "").strip() or None,
            serial_number=serial_number or None,
            department=department,
            location=(data.get("location") or "").strip() or None,
            purchase_date=data.get("purchase_date"),
            warranty_expiry_date=data.get("warranty_expiry_date"),
            assigned_user_id=data.get("assigned_user_id") or None,
            condition=data.get("condition") or "Good",
            operational_status=data.get("operational_status") or "In Use",
            description=(data.get("description") or "").strip() or None,
            registered_by=actor.id,
        )
        _validate_dates(equipment)
        db.session.add(equipment)
        db.session.flush()  # assigns equipment.id

        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_CREATE,
            "equipment",
            equipment.id,
            f"{actor.role_label} registered equipment {equipment.asset_tag} "
            f"({equipment.equipment_name}).",
        )
        return equipment

    # -------------------------------------------------------------- update
    @classmethod
    def update(cls, equipment: Equipment, data: dict, actor: User) -> Equipment:
        """Apply edited fields to an existing asset (with re-validation)."""
        new_tag = (data.get("asset_tag") or "").strip()
        if new_tag:
            clash = cls.find_by_asset_tag(new_tag)
            if clash is not None and clash.id != equipment.id:
                raise DuplicateError(f"Asset tag '{new_tag}' is already in use.")

        new_serial = (data.get("serial_number") or "").strip()
        if new_serial:
            clash = cls.find_by_serial(new_serial)
            if clash is not None and clash.id != equipment.id:
                raise DuplicateError(
                    f"Serial number '{new_serial}' already belongs to {clash.asset_tag}."
                )

        department = db.session.get(Department, data.get("department_id"))
        if department is None:
            raise ValidationError("Please select a valid department.")

        before_status = equipment.operational_status
        before_condition = equipment.condition

        equipment.asset_tag = new_tag or equipment.asset_tag
        equipment.equipment_name = data["equipment_name"].strip()
        equipment.equipment_type = data["equipment_type"]
        equipment.manufacturer = (data.get("manufacturer") or "").strip() or None
        equipment.model = (data.get("model") or "").strip() or None
        equipment.serial_number = new_serial or None
        equipment.department = department
        equipment.location = (data.get("location") or "").strip() or None
        equipment.purchase_date = data.get("purchase_date")
        equipment.warranty_expiry_date = data.get("warranty_expiry_date")
        equipment.assigned_user_id = data.get("assigned_user_id") or None
        equipment.condition = data.get("condition") or equipment.condition
        equipment.operational_status = (
            data.get("operational_status") or equipment.operational_status
        )
        equipment.description = (data.get("description") or "").strip() or None
        _validate_dates(equipment)

        # Any condition/status edit made through the form still leaves a trail.
        if (before_status, before_condition) != (
            equipment.operational_status,
            equipment.condition,
        ):
            cls._record_history(
                equipment,
                before_condition,
                equipment.condition,
                before_status,
                equipment.operational_status,
                actor,
                "Updated while editing the equipment record.",
            )

        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_UPDATE,
            "equipment",
            equipment.id,
            f"{actor.role_label} updated equipment {equipment.asset_tag}.",
        )
        return equipment

    # ------------------------------------------------- status / retirement
    @classmethod
    def change_condition(cls, equipment: Equipment, new_condition: str, actor: User,
                         notes: str = "") -> Equipment:
        if new_condition not in CONDITIONS:
            raise ValidationError(f"Invalid condition: {new_condition!r}")
        before = equipment.condition
        if not equipment.update_condition(new_condition):
            return equipment  # no change -> no history noise
        cls._record_history(
            equipment, before, new_condition, None, None, actor,
            notes or f"Condition changed from {before} to {new_condition}.",
        )
        audit_service.AuditService.log(
            actor, audit_service.ACTION_UPDATE, "equipment", equipment.id,
            f"{actor.role_label} changed condition of {equipment.asset_tag} "
            f"from {before} to {new_condition}.",
        )
        return equipment

    @classmethod
    def change_status(cls, equipment: Equipment, new_status: str, actor: User,
                      notes: str = "") -> Equipment:
        if new_status not in OPERATIONAL_STATUSES:
            raise ValidationError(f"Invalid operational status: {new_status!r}")
        before = equipment.operational_status
        if not equipment.update_status(new_status):
            return equipment
        cls._record_history(
            equipment, None, None, before, new_status, actor,
            notes or f"Status changed from {before} to {new_status}.",
        )
        audit_service.AuditService.log(
            actor, audit_service.ACTION_UPDATE, "equipment", equipment.id,
            f"{actor.role_label} changed status of {equipment.asset_tag} "
            f"from {before} to {new_status}.",
        )
        return equipment

    @classmethod
    def retire(cls, equipment: Equipment, actor: User, notes: str = "") -> Equipment:
        """Mark an asset retired - records are kept forever."""
        if equipment.is_retired:
            raise ValidationError("This equipment is already retired.")
        before = equipment.operational_status
        equipment.operational_status = STATUS_RETIRED
        cls._record_history(
            equipment, None, None, before, STATUS_RETIRED, actor,
            notes or "Equipment retired from service.",
        )
        audit_service.AuditService.log(
            actor, audit_service.ACTION_RETIRE, "equipment", equipment.id,
            f"{actor.role_label} retired equipment {equipment.asset_tag}.",
        )
        return equipment

    # ------------------------------------------------------------ queries
    @classmethod
    def search_statement(cls, **filters):
        """Build a parameterised SQLAlchemy statement from UI filters.

        Uses ORM/SQLAlchemy expressions exclusively - values are always bound
        parameters, never string-concatenated SQL.
        """
        stmt = select(Equipment).join(Equipment.department, isouter=True)

        search = (filters.get("search") or "").strip()
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Equipment.asset_tag.ilike(pattern),
                    Equipment.equipment_name.ilike(pattern),
                    Equipment.serial_number.ilike(pattern),
                    Equipment.manufacturer.ilike(pattern),
                    Equipment.model.ilike(pattern),
                )
            )

        for column, key in (
            (Equipment.equipment_type, "equipment_type"),
            (Equipment.condition, "condition"),
            (Equipment.operational_status, "operational_status"),
        ):
            value = filters.get(key)
            if value:
                stmt = stmt.where(column == value)

        department_id = filters.get("department_id")
        if department_id:
            stmt = stmt.where(Equipment.department_id == int(department_id))

        location = (filters.get("location") or "").strip()
        if location:
            stmt = stmt.where(Equipment.location.ilike(f"%{location}%"))

        date_from = filters.get("date_from")
        if date_from:
            stmt = stmt.where(Equipment.purchase_date >= date_from)
        date_to = filters.get("date_to")
        if date_to:
            stmt = stmt.where(Equipment.purchase_date <= date_to)

        warranty = filters.get("warranty")
        if warranty == "active":
            stmt = stmt.where(
                Equipment.warranty_expiry_date.isnot(None),
                Equipment.warranty_expiry_date >= datetime.today().date(),
            )
        elif warranty == "expired":
            stmt = stmt.where(
                Equipment.warranty_expiry_date.isnot(None),
                Equipment.warranty_expiry_date < datetime.today().date(),
            )
        elif warranty == "missing":
            stmt = stmt.where(Equipment.warranty_expiry_date.is_(None))

        return stmt.order_by(Equipment.asset_tag.asc())

    @classmethod
    def paginate(cls, page: int, per_page: int, **filters):
        stmt = cls.search_statement(**filters)
        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    @staticmethod
    def category_names():
        """Equipment type names known to the catalogue."""
        rows = db.session.scalars(
            select(EquipmentCategory.name).order_by(EquipmentCategory.name)
        ).all()
        return rows or []

    # ----------------------------------------------------------- internals
    @staticmethod
    def _record_history(equipment, prev_cond, new_cond, prev_status, new_status,
                        actor, notes):
        entry = EquipmentStatusHistory(
            equipment=equipment,
            previous_condition=prev_cond,
            new_condition=new_cond or prev_cond,
            previous_status=prev_status,
            new_status=new_status or prev_status,
            changed_by=actor.id if actor else None,
            change_notes=notes,
        )
        db.session.add(entry)
        return entry


def _validate_dates(equipment: Equipment) -> None:
    """Reject impossible date combinations (e.g. warranty before purchase)."""
    if equipment.purchase_date and equipment.warranty_expiry_date:
        if equipment.warranty_expiry_date < equipment.purchase_date:
            raise ValidationError(
                "Warranty expiry date cannot be earlier than the purchase date.",
                {"warranty_expiry_date": "Must be after the purchase date."},
            )
    if equipment.purchase_date and equipment.purchase_date > datetime.today().date():
        raise ValidationError(
            "Purchase date cannot be in the future.",
            {"purchase_date": "Purchase date cannot be in the future."},
        )
