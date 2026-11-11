"""Controlled vocabularies used across the CMIMS application.

Every dropdown, status badge, validation rule and dashboard statistic is
driven by these constants, so the whole application agrees on the exact
spelling of each status / condition / category.
"""

# --- User roles -------------------------------------------------------------
ROLE_ADMIN = "admin"
ROLE_OFFICER = "ict_officer"
ROLE_VIEWER = "viewer"

ROLES = (ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)

ROLE_LABELS = {
    ROLE_ADMIN: "Administrator",
    ROLE_OFFICER: "ICT Officer",
    ROLE_VIEWER: "Viewer",
}

# --- Equipment conditions ----------------------------------------------------
CONDITION_EXCELLENT = "Excellent"
CONDITION_GOOD = "Good"
CONDITION_FAIR = "Fair"
CONDITION_POOR = "Poor"
CONDITION_DAMAGED = "Damaged"

CONDITIONS = (
    CONDITION_EXCELLENT,
    CONDITION_GOOD,
    CONDITION_FAIR,
    CONDITION_POOR,
    CONDITION_DAMAGED,
)

# --- Operational statuses -----------------------------------------------------
STATUS_IN_USE = "In Use"
STATUS_AVAILABLE = "Available"
STATUS_FAULTY = "Faulty"
STATUS_UNDER_MAINTENANCE = "Under Maintenance"
STATUS_RETIRED = "Retired"

OPERATIONAL_STATUSES = (
    STATUS_IN_USE,
    STATUS_AVAILABLE,
    STATUS_FAULTY,
    STATUS_UNDER_MAINTENANCE,
    STATUS_RETIRED,
)

# --- Equipment types -----------------------------------------------------------
TYPE_DESKTOP = "Desktop Computer"
TYPE_LAPTOP = "Laptop Computer"
TYPE_PRINTER = "Printer"
TYPE_SCANNER = "Scanner"
TYPE_MONITOR = "Monitor"
TYPE_KEYBOARD = "Keyboard"
TYPE_ROUTER = "Router"
TYPE_SWITCH = "Network Switch"
TYPE_SERVER = "Server"
TYPE_UPS = "UPS"
TYPE_PROJECTOR = "Projector"
TYPE_OTHER = "Other ICT Equipment"

EQUIPMENT_TYPES = (
    TYPE_DESKTOP,
    TYPE_LAPTOP,
    TYPE_PRINTER,
    TYPE_SCANNER,
    TYPE_MONITOR,
    TYPE_KEYBOARD,
    TYPE_ROUTER,
    TYPE_SWITCH,
    TYPE_SERVER,
    TYPE_UPS,
    TYPE_PROJECTOR,
    TYPE_OTHER,
)

# --- Fault categories -----------------------------------------------------------
FAULT_CAT_NO_START = "Computer Won't Start"
FAULT_CAT_OS = "Operating System Problem"
FAULT_CAT_SOFTWARE = "Software Installation Problem"
FAULT_CAT_NETWORK = "Network Connectivity Problem"
FAULT_CAT_PRINTER = "Printer Problem"
FAULT_CAT_HARDWARE = "Hardware Failure"
FAULT_CAT_VIRUS = "Virus or Malware Concern"
FAULT_CAT_SLOW = "Slow Computer Performance"
FAULT_CAT_POWER = "Power Supply Problem"
FAULT_CAT_PERIPHERAL = "Peripheral Device Problem"
FAULT_CAT_OTHER = "Other"

FAULT_CATEGORIES = (
    FAULT_CAT_NO_START,
    FAULT_CAT_OS,
    FAULT_CAT_SOFTWARE,
    FAULT_CAT_NETWORK,
    FAULT_CAT_PRINTER,
    FAULT_CAT_HARDWARE,
    FAULT_CAT_VIRUS,
    FAULT_CAT_SLOW,
    FAULT_CAT_POWER,
    FAULT_CAT_PERIPHERAL,
    FAULT_CAT_OTHER,
)

# --- Fault priority ---------------------------------------------------------------
PRIORITY_LOW = "Low"
PRIORITY_MEDIUM = "Medium"
PRIORITY_HIGH = "High"
PRIORITY_CRITICAL = "Critical"

FAULT_PRIORITIES = (PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_CRITICAL)

# --- Fault status --------------------------------------------------------------
FAULT_REPORTED = "Reported"
FAULT_ACKNOWLEDGED = "Acknowledged"
FAULT_UNDER_REPAIR = "Under Repair"
FAULT_AWAITING_PARTS = "Awaiting Parts"
FAULT_RESOLVED = "Resolved"
FAULT_CLOSED = "Closed"

FAULT_STATUSES = (
    FAULT_REPORTED,
    FAULT_ACKNOWLEDGED,
    FAULT_UNDER_REPAIR,
    FAULT_AWAITING_PARTS,
    FAULT_RESOLVED,
    FAULT_CLOSED,
)

# Statuses considered "open" (still require ICT attention).
OPEN_FAULT_STATUSES = (
    FAULT_REPORTED,
    FAULT_ACKNOWLEDGED,
    FAULT_UNDER_REPAIR,
    FAULT_AWAITING_PARTS,
)

# Allowed forward transitions - ``{}`` means no transition is permitted.
FAULT_STATUS_TRANSITIONS = {
    FAULT_REPORTED: (FAULT_ACKNOWLEDGED, FAULT_UNDER_REPAIR),
    FAULT_ACKNOWLEDGED: (FAULT_UNDER_REPAIR, FAULT_AWAITING_PARTS, FAULT_CLOSED),
    FAULT_UNDER_REPAIR: (FAULT_AWAITING_PARTS, FAULT_RESOLVED),
    FAULT_AWAITING_PARTS: (FAULT_UNDER_REPAIR, FAULT_RESOLVED),
    FAULT_RESOLVED: (FAULT_CLOSED, FAULT_UNDER_REPAIR),
    FAULT_CLOSED: (),
}

# --- Maintenance -------------------------------------------------------------
MAINT_PREVENTIVE = "Preventive Maintenance"
MAINT_CORRECTIVE = "Corrective Maintenance"
MAINT_HARDWARE_REPAIR = "Hardware Repair"
MAINT_SOFTWARE = "Software Maintenance"
MAINT_NETWORK = "Network Maintenance"
MAINT_UPDATE = "System Update"
MAINT_INSPECTION = "Inspection"
MAINT_OTHER = "Other"

MAINTENANCE_TYPES = (
    MAINT_PREVENTIVE,
    MAINT_CORRECTIVE,
    MAINT_HARDWARE_REPAIR,
    MAINT_SOFTWARE,
    MAINT_NETWORK,
    MAINT_UPDATE,
    MAINT_INSPECTION,
    MAINT_OTHER,
)

OUTCOME_SUCCESS = "Completed - Equipment Working"
OUTCOME_PARTIAL = "Completed - Equipment Not Fully Working"
OUTCOME_UNSUCCESSFUL = "Unsuccessful - Fault Persists"
OUTCOME_DEFERRED = "Deferred - Awaiting Parts"

MAINTENANCE_OUTCOMES = (
    OUTCOME_SUCCESS,
    OUTCOME_PARTIAL,
    OUTCOME_UNSUCCESSFUL,
    OUTCOME_DEFERRED,
)

# --- Maintenance schedules --------------------------------------------------
SCHEDULE_SCHEDULED = "Scheduled"
SCHEDULE_DUE = "Due"
SCHEDULE_IN_PROGRESS = "In Progress"
SCHEDULE_COMPLETED = "Completed"
SCHEDULE_OVERDUE = "Overdue"
SCHEDULE_CANCELLED = "Cancelled"

SCHEDULE_STATUSES = (
    SCHEDULE_SCHEDULED,
    SCHEDULE_DUE,
    SCHEDULE_IN_PROGRESS,
    SCHEDULE_COMPLETED,
    SCHEDULE_OVERDUE,
    SCHEDULE_CANCELLED,
)

# --- Audit actions ------------------------------------------------------------
AUDIT_CREATE = "create"
AUDIT_UPDATE = "update"
AUDIT_STATUS_CHANGE = "status_change"
AUDIT_LOGIN = "login"
AUDIT_LOGOUT = "logout"
AUDIT_RETIRE = "retire"
AUDIT_ASSIGN = "assign"

# Status badge colour hints consumed by the ``status_badge`` Jinja filter.
BADGE_CLASSES = {
    # Equipment condition
    CONDITION_EXCELLENT: "badge-success",
    CONDITION_GOOD: "badge-success",
    CONDITION_FAIR: "badge-warning",
    CONDITION_POOR: "badge-danger",
    CONDITION_DAMAGED: "badge-dark",
    # Operational status
    STATUS_IN_USE: "badge-info",
    STATUS_AVAILABLE: "badge-success",
    STATUS_FAULTY: "badge-danger",
    STATUS_UNDER_MAINTENANCE: "badge-warning",
    STATUS_RETIRED: "badge-dark",
    # Fault status
    FAULT_REPORTED: "badge-danger",
    FAULT_ACKNOWLEDGED: "badge-info",
    FAULT_UNDER_REPAIR: "badge-warning",
    FAULT_AWAITING_PARTS: "badge-warning",
    FAULT_RESOLVED: "badge-success",
    FAULT_CLOSED: "badge-dark",
    # Priority
    PRIORITY_LOW: "badge-secondary",
    PRIORITY_MEDIUM: "badge-info",
    PRIORITY_HIGH: "badge-warning",
    PRIORITY_CRITICAL: "badge-danger",
    # Schedules
    SCHEDULE_SCHEDULED: "badge-info",
    SCHEDULE_DUE: "badge-warning",
    SCHEDULE_IN_PROGRESS: "badge-warning",
    SCHEDULE_COMPLETED: "badge-success",
    SCHEDULE_OVERDUE: "badge-danger",
    SCHEDULE_CANCELLED: "badge-dark",
    # Maintenance outcomes
    OUTCOME_SUCCESS: "badge-success",
    OUTCOME_PARTIAL: "badge-warning",
    OUTCOME_UNSUCCESSFUL: "badge-danger",
    OUTCOME_DEFERRED: "badge-warning",
}
