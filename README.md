# CMIMS — Computer Maintenance and Inventory Management System

A web-based system for an organisation's ICT department: it keeps a register of
every computer and piece of ICT equipment, records the faults reported against
them, tracks the repairs and servicing carried out, schedules preventive
maintenance, generates inventory and maintenance reports, and keeps a complete
audit trail of who did what and when.

Built with **Python, Flask, SQLAlchemy and SQLite**, with server-side
role-based access control, CSRF protection, ORM-only queries, Werkzeug password
hashing and an append-only audit log.

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [Project objectives](#2-project-objectives)
3. [Features](#3-features)
4. [Technologies used](#4-technologies-used)
5. [System architecture](#5-system-architecture)
6. [Database design](#6-database-design)
7. [OOP concepts used](#7-oop-concepts-used)
8. [Installation](#8-installation)
9. [Default accounts](#9-default-accounts)
10. [How to use the system](#10-how-to-use-the-system)
11. [Security measures](#11-security-measures)
12. [Testing instructions](#12-testing-instructions)
13. [Limitations](#13-limitations)
14. [Future improvements](#14-future-improvements)

---

## 1. Project overview

Most organisations track their ICT equipment in spreadsheets, exercise books or
not at all. The result is predictable: nobody knows exactly how many computers
the organisation owns, which department has them, which ones are faulty, what
was spent repairing them, or when a machine was last serviced. When a printer
fails for the third time in a term there is no history to show that it has been
repaired before, and when an asset cannot be found there is no record of who
should have it.

**CMIMS** replaces that with one database-backed system:

* every asset is registered once and gets a unique asset tag,
* every fault is reported and given a reference number (`FR-2026-0001`),
* every repair is recorded against the equipment and, where relevant, against
  the fault it resolved,
* preventive maintenance is scheduled and chased,
* reports and dashboards are generated from live data instead of guesswork,
* and every important action leaves an audit entry.

The system is intended for three kinds of user: the **administrator** who runs
it, the **ICT officers** who do the hands-on work, and **viewers** (for example
a head of department or an auditor) who need read-only access.

---

## 2. Project objectives

| # | Objective |
|---|-----------|
| 1 | Digitise the ICT equipment inventory so every asset is recorded in one place. |
| 2 | Improve equipment record keeping: type, manufacturer, model, serial number, location, custodian, purchase and warranty dates. |
| 3 | Track computer faults from the moment they are reported through to closure. |
| 4 | Maintain a complete repair history for each machine, including cost and outcome. |
| 5 | Schedule preventive maintenance so equipment is serviced before it fails. |
| 6 | Reduce loss of equipment information when staff leave or records are misplaced. |
| 7 | Improve ICT asset management through search, filtering and reporting. |
| 8 | Generate useful inventory and maintenance reports, with CSV export. |
| 9 | Provide accountability through role-based access control and an audit trail. |

---

## 3. Features

### 3.1 Equipment inventory
* Register equipment with asset tag, name, type, manufacturer, model, serial
  number, department, physical location, assigned user, purchase date, warranty
  expiry date, condition and operational status.
* Asset tags and serial numbers are unique — the database and the service layer
  both reject duplicates.
* Automatic warranty state (`Active`, `Expiring Soon`, `Expired`,
  `Not recorded`).
* Full status/condition history per asset, with the responsible user and notes.
* Retirement instead of deletion: retired assets keep all their history.

### 3.2 Fault reporting
* Report a fault against existing equipment with a title, description,
  category, priority and discovery date.
* Automatic reference numbers (`FR-<year>-<sequence>`).
* An enforced workflow: `Reported → Acknowledged → Under Repair →
  Awaiting Parts → Resolved → Closed`, with the legal transitions declared in
  one place.
* A fault cannot be **resolved** until a maintenance/repair record is linked to
  it and resolution notes are supplied — no "resolved" faults with no repair.
* Assignment to ICT officers, priority changes, investigation/troubleshooting
  notes and resolution notes.
* Optional supporting attachment (screenshot or PDF) validated against an
  allowlist and size limit; never required.

### 3.3 Maintenance
* Record repairs, inspections, firmware updates and other maintenance with
  diagnosis, work performed, parts replaced, technician, time on site, cost,
  condition after and outcome.
* Link a record to the fault report it resolves and to the schedule it fulfils.
* Automatic side effects: a successful repair returns the equipment to
  *In Use*, a partial repair or persistent fault marks it *Faulty*, and
  "awaiting parts" marks it *Under Maintenance*.

### 3.4 Preventive maintenance scheduling
* Schedule servicing per asset with a date, responsible ICT officer and
  instructions.
* `Scheduled / Due / In Progress / Overdue / Completed / Cancelled` statuses,
  with due/overdue recalculated automatically from the stored date.
* Completing a schedule can create the matching maintenance record in one step.
* Dashboard and list reminders of overdue and upcoming servicing.

### 3.5 Search, filtering and pagination
* Equipment: asset tag, equipment name, serial number, manufacturer, model;
  filters for type, department, location, condition, operational status,
  purchase date range and warranty state.
* Faults: reference number, asset tag, fault title, equipment name; filters for
  status, priority, department, fault category, assigned officer and reported
  date range.
* Maintenance and schedules have their own equivalent filter sets, and the
  audit trail can be filtered by action, entity, user and date.
* Every list is paginated; filter inputs are validated and invalid values are
  reported and ignored rather than causing an error.

### 3.6 Reports
* Equipment Inventory Report, Fault Report Summary, Maintenance History Report,
  Preventive Maintenance Report and Equipment Condition Report (grouped by
  condition).
* Date range, department, equipment type, condition, status, category,
  priority, technician and officer filters where relevant.
* One-click CSV export of the exact rows on screen, and print-friendly pages.
* All figures come from live database queries — nothing is hard-coded.

### 3.7 Dashboards
* **Administrator:** inventory, faults, accounts, departments, maintenance cost,
  warranty attention, equipment by department/condition, faults by status,
  account roles and the latest audit entries.
* **ICT Officer:** equipment totals, open fault queue, overdue/upcoming
  servicing, status and priority breakdowns, servicing trend, warranty
  watchlist and recent activity.
* **Viewer:** read-only inventory overview — counts, condition/type/department
  breakdowns and recently reported faults.

### 3.8 Accounts, roles and audit
* Administrator, ICT Officer and Viewer roles with a permission model defined
  in code.
* Create, edit, deactivate and reactivate accounts; passwords are reset by an
  administrator or changed by the user themselves.
* The last active administrator cannot be deactivated or demoted.
* Deactivated accounts cannot sign in and immediately lose all permissions.
* Audit trail of creations, edits, status changes, assignments, retirements,
  logins, blocked logins and account activation/deactivation.
* The role permission matrix is documented in the project report: view/create/
  edit equipment, report and manage faults, record maintenance, manage
  schedules, view/export reports, manage departments, users and audit.

---

## 4. Technologies used

| Technology | What it does in this project |
|------------|------------------------------|
| **Python 3.11+** | The programming language the whole application is written in. |
| **Flask** | Web framework: routing, request handling, sessions, Jinja templates and the application factory. |
| **SQLite** | The database engine. It is a single file (`instance/computer_maintenance.db`), which makes it ideal for an organisational deployment without a database server. |
| **SQLAlchemy / Flask-SQLAlchemy** | The ORM. Every query is built from ORM expressions with bound parameters, which is what protects the application against SQL injection. |
| **Flask-Login** | Session-based authentication: `login_user`, `logout_user`, `current_user` and `@login_required`. |
| **Werkzeug** | Password hashing (`generate_password_hash` / `check_password_hash`, scrypt by default), plus `secure_filename` for uploads. |
| **Flask-WTF / WTForms** | Form definitions, server-side validation, CSRF tokens and file-upload fields. |
| **Jinja2** | Templating with automatic HTML escaping (XSS protection) and reusable macros. |
| **HTML5** | Semantic page structure. |
| **CSS3** | The professional blue/dark theme, responsive layout, cards, tables and badges. |
| **JavaScript (vanilla)** | Progressive enhancement only: mobile navigation, confirmation dialogs, dismissible alerts, auto-submitting filters, double-submit guard. The application works without it. |
| **pytest** | The automated test-suite (139 tests). |
| **python-dotenv** | Loads configuration from a local `.env` file. |

---

## 5. System architecture

CMIMS is a classic server-rendered Flask application with a layered structure:

```
 Browser  ──────────────►  Flask (routes/)  ──►  Services (services/)  ──►  Models (models/)  ──►  SQLite
   ▲            HTTP          request handling      business rules             ORM mappings       instance/
   │                          validation of form    transactions, audit        relationships      computer_maintenance.db
   └────────── HTML (Jinja templates + CSS/JS) ◄──┘
```

1. **Browser** — sends a request (usually a page load or a form POST).
2. **Routes (`routes/`)** — a thin HTTP layer. Each blueprint parses the
   request, checks the caller's permission, calls a service and renders a
   template. No business rules live here.
3. **Services (`services/`)** — the business logic and the security boundary:
   uniqueness checks, the fault status machine, maintenance side effects,
   account rules, reports and the audit trail. A service never commits by
   itself; it adds work to the current transaction.
4. **Models (`models/`)** — SQLAlchemy classes that map onto tables and carry
   their own behaviour (warranty state, status history, allowed transitions).
5. **Database** — SQLite. The route layer commits the transaction, so a business
   change and its audit entry either both persist or both roll back.

Supporting layers: **`forms/`** (Flask-WTF validation), **`templates/`** and
**`static/`** (presentation), **`scripts/`** (initialise and seed),
**`tests/`** (automated checks), **`config.py` / `extensions.py`** (wiring).

---

## 6. Database design

### 6.1 Tables

| Table | Purpose | Key fields |
|-------|---------|-----------|
| `users` | Every account, with one of three roles. | `id`, `full_name`, `email` (unique), `password_hash`, `role`, `is_active` |
| `departments` | Organisational units that own equipment. | `id`, `name` (unique), `description`, `location` |
| `equipment_categories` | Master list of equipment types used by the registration form. | `id`, `name` (unique), `description` |
| `equipment` | The asset register. | `id`, `asset_tag` (unique), `equipment_name`, `equipment_type`, `manufacturer`, `model`, `serial_number`, `department_id` → departments, `location`, `purchase_date`, `warranty_expiry_date`, `assigned_user_id` → users, `condition`, `operational_status`, `registered_by` → users |
| `equipment_status_history` | Every condition/status change per asset. | `equipment_id` → equipment, `previous_condition`, `new_condition`, `previous_status`, `new_status`, `changed_by` → users, `change_notes`, `changed_at` |
| `fault_reports` | Reported faults. | `id`, `reference_number` (unique), `equipment_id` → equipment, `reported_by` → users, `assigned_to` → users, `fault_title`, `fault_description`, `fault_category`, `priority`, `status`, `date_discovered`, `resolution_notes`, `attachment_filename`, `resolved_at` |
| `fault_status_history` | Every fault status transition. | `fault_report_id` → fault_reports, `previous_status`, `new_status`, `changed_by` → users, `change_notes`, `changed_at` |
| `fault_notes` | Investigation/troubleshooting notes. | `fault_report_id` → fault_reports, `author_id` → users, `body`, `created_at` |
| `maintenance_records` | Work actually performed. | `id`, `equipment_id` → equipment, `fault_report_id` → fault_reports, `maintenance_type`, `diagnosis`, `work_performed`, `parts_replaced`, `technician_id` → users, `maintenance_date`, `start_time`, `completion_time`, `cost`, `condition_after`, `outcome`, `recorded_by` → users, `schedule_id` → maintenance_schedules |
| `maintenance_schedules` | Planned preventive maintenance. | `id`, `equipment_id` → equipment, `maintenance_type`, `scheduled_date`, `assigned_to` → users, `instructions`, `status`, `completed_at`, `created_by` → users |
| `audit_logs` | Append-only trail of important actions. | `id`, `user_id` → users, `action`, `entity_type`, `entity_id`, `description`, `timestamp` |

### 6.2 Entity relationship diagram

```
                 ┌───────────────┐            ┌──────────────────────┐
                 │ departments   │            │ equipment_categories │
                 │ PK id         │            │ PK id                │
                 │ name (unique) │            │ name (unique)        │
                 └──────┬────────┘            └──────────────────────┘
                        │ 1                                 (typed by name)
                        │
                        │ n
   ┌────────────────────┴────────────────────────────────────────────────┐
   │ equipment                                                           │
   │ PK id · asset_tag (unique) · equipment_name · equipment_type        │
   │ serial_number · location · purchase_date · warranty_expiry_date     │
   │ condition · operational_status                                      │
   │ FK department_id → departments.id                                   │
   │ FK assigned_user_id → users.id            FK registered_by → users  │
   └──┬────────────────────┬────────────────────┬────────────────────┬───┘
      │ 1                  │ 1                  │ 1                  │ 1
      │ n                  │ n                  │ n                  │ n
┌─────┴───────────────┐ ┌──┴────────────────┐ ┌─┴──────────────────┐ ┌┴──────────────────────┐
│ equipment_status_   │ │ fault_reports     │ │ maintenance_       │ │ maintenance_schedules │
│ history             │ │ PK id             │ │ records            │ │ PK id                 │
│ PK id               │ │ reference_number  │ │ PK id              │ │ scheduled_date        │
│ previous_condition  │ │ (unique)          │ │ diagnosis          │ │ instructions          │
│ new_condition       │ │ fault_title       │ │ work_performed     │ │ status                │
│ previous_status     │ │ fault_category    │ │ parts_replaced     │ │ completed_at          │
│ new_status          │ │ priority · status │ │ maintenance_date   │ │                       │
│ change_notes        │ │ date_discovered   │ │ cost · outcome     │ │ FK equipment_id       │
│ changed_at          │ │ resolution_notes  │ │ condition_after    │ │ FK assigned_to → users│
│ FK changed_by → user│ │ attachment        │ │                    │ │ FK created_by → users │
│                     │ │                   │ │ FK equipment_id     │ │                       │
│                     │ │ FK equipment_id   │ │ FK technical_id    │ └───────┬───────────────┘
│                     │ │ FK reported_by    │ │     → users        │         │ 1
│                     │ │ FK assigned_to    │ │ FK fault_report_id │◄────────┘ (schedule_id)
│                     │ └──┬─────────────┬──┘ └────────────────────┘
└─────────────────────┘    │ 1           │ 1
                           │ n           │ n
              ┌────────────┴──────┐  ┌───┴──────────────────┐
              │ fault_status_     │  │ fault_notes          │
              │ history           │  │ PK id                │
              │ PK id             │  │ body · created_at    │
              │ previous_status   │  │ FK author_id → users │
              │ new_status        │  └──────────────────────┘
              │ change_notes      │
              │ changed_at        │            ┌──────────────────┐
              │ FK changed_by     │            │ audit_logs        │
              └───────────────────┘            │ PK id            │
                                               │ action           │
            ┌──────────────────┐               │ entity_type      │
            │ users            │◄──────────────│ entity_id        │
            │ PK id            │  FK user_id   │ description      │
            │ full_name        │               │ timestamp        │
            │ email (unique)   │               └──────────────────┘
            │ password_hash    │
            │ role             │  roles: admin | ict_officer | viewer
            │ is_active        │
            └──────────────────┘
```

Cardinality summary:

* Department **1 — n** Equipment; Equipment **1 — n** faults, maintenance
  records, schedules and status-history rows.
* Fault report **1 — n** status-history rows and notes; **0..n** maintenance
  records.
* User **1 — n** equipment registered, faults reported, faults assigned,
  maintenance performed and audit entries.
* Maintenance schedule **1 — 0..1** maintenance record.

### 6.3 Integrity rules enforced by the database
* `users.email`, `departments.name`, `equipment_categories.name`,
  `equipment.asset_tag` and `fault_reports.reference_number` are `UNIQUE`.
* Not-null constraints on every field that must always have a value (asset tag,
  name, department, condition, status, fault description, outcome, and so on).
* Foreign keys link every child row to its parent; dependent history rows use
  `ON DELETE CASCADE` so an equipment record can never leave orphaned history.

---

## 7. OOP concepts used

| Concept | Where it appears |
|---------|------------------|
| **Classes and objects** | `Equipment`, `FaultReport`, `MaintenanceRecord`, `User`, `Department`, `AuditLog` are classes; each registered asset, fault or repair is an instance of one of them. |
| **Encapsulation** | Password handling is hidden behind `User.set_password()` / `User.check_password()`. Callers never touch `password_hash`. Equipment behaviour such as `update_status()`, `update_condition()`, `retire()` and the `warranty_status` property belongs to the class that owns the data. |
| **Inheritance** | Every model inherits from `db.Model` (SQLAlchemy's declarative base) and `User` additionally inherits from `UserMixin` (Flask-Login). `Administrator`, `ICTOfficer` and `Viewer` inherit from the abstract `Role` base class, and `ValidationError`, `DuplicateError`, `TransitionError` and `NotFoundError` inherit from `ServiceError`. |
| **Abstraction** | `Role` is an abstract base class (using `abc.ABC`) that declares `can()`, `cannot()` and the abstract `dashboard_template()` / `home_endpoint()`. Callers only ever use the public interface. |
| **Polymorphism** | `user.can("fault.manage")` dispatches to the concrete role object, so no route contains `if role == 'admin'` chains. `user.role_object.dashboard_template()` renders the right dashboard for each role, and every blueprint can be registered/unregistered through the same `register_blueprints(app)` call. |
| **Composition / relationships** | Objects are wired by relationships rather than duplicated data: an `Equipment` *has many* `FaultReport`s, a `FaultReport` *has many* `FaultStatusHistory` rows and *belongs to* one `Equipment`. |
| **Methods and properties** | Behaviour lives with the data: `FaultReport.available_transitions()`, `can_transition_to()`, `MaintenanceRecord.is_successful`, `MaintenanceSchedule.days_until`, `Equipment.has_open_faults`. |
| **Service classes (single responsibility)** | `EquipmentService`, `FaultService`, `MaintenanceService`, `ScheduleService`, `UserService`, `ReportService`, `DashboardService`, `AuditService` and `AttachmentService` each own one area of logic. They are stateless (`@staticmethod` / `@classmethod`) so they are easy to test. |
| **Mixin classes** | `ChoiceFormMixin` and `FilterFormMixin` add dynamic dropdown population and filter cleaning to many Flask-WTF forms without copy-pasting code. |
| **Exception-driven flow** | Services raise `ServiceError` subclasses; routes catch them, roll the transaction back and flash a friendly message. |

---

## 8. Installation

### 8.1 Prerequisites
* **Python 3.11 or newer** — check with `python --version`.
* `pip` (bundled with Python).
* Any modern browser (Chrome, Edge, Firefox).
* Windows, macOS or Linux. The commands below cover **Windows Command Prompt**,
  **Windows PowerShell** and Unix shells.

### 8.2 Step 1 — Install Python
Download the installer from <https://www.python.org/downloads/>. On Windows,
tick **"Add python.exe to PATH"** during installation. Verify:

```bat
python --version
pip --version
```

### 8.3 Step 2 — Open the project folder

```bat
:: Windows Command Prompt
cd "computer_maintenance_system"
```

```powershell
# Windows PowerShell
Set-Location "computer_maintenance_system"
```

```bash
# macOS / Linux
cd computer_maintenance_system
```

### 8.4 Step 3 — Create and activate a virtual environment

```bat
:: Windows Command Prompt
python -m venv .venv
.venv\Scripts\activate
```

```powershell
# Windows PowerShell (activate)
python -m venv .venv
.venv\Scripts\Activate.ps1

# If PowerShell blocks the script, allow it for this session only:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 8.5 Step 4 — Install the required packages

```bat
:: Windows Command Prompt and PowerShell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

```bash
# macOS / Linux
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 8.6 Step 5 — Configure the environment variables

Copy the template and edit it:

```bat
:: Windows Command Prompt
copy .env.example .env
notepad .env
```

```powershell
# Windows PowerShell
Copy-Item .env.example .env
notepad .env
```

```bash
# macOS / Linux
cp .env.example .env
nano .env
```

Set at least a real secret key:

```bat
:: Windows Command Prompt — generate and print a strong key
python -c "import secrets; print(secrets.token_hex(32))"
```

```powershell
# Windows PowerShell
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the result into `.env` as `SECRET_KEY=...`. Never commit `.env` — it is
listed in `.gitignore`.

### 8.7 Step 6 — Initialise the database

```bat
:: Windows Command Prompt and PowerShell
python scripts/init_db.py
```

This creates `instance/computer_maintenance.db` and every table. It is safe to
re-run: it only creates what is missing and **never** drops or overwrites an
existing database that contains real records.

### 8.8 Step 7 — Load the sample data

```bat
:: Windows Command Prompt and PowerShell
python scripts/seed_db.py
```

The seeding script is **idempotent** — running it again does not create
duplicate records, and it never modifies records entered by real users. It
creates the accounts below, five departments, the twelve equipment types,
eighteen sample assets, eight faults, eight maintenance records and eight
preventive schedules, all fictional.

### 8.9 Step 8 — Start the application

```bat
:: Windows Command Prompt and PowerShell
python app.py
```

You should see:

```
 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
```

(Equivalent alternatives: `flask --app app run`, or set `HOST` / `PORT` in
`.env` to change the address. Debug mode is off unless you explicitly set
`FLASK_DEBUG=1`, so the development debugger is never exposed by accident.)

### 8.10 Step 9 — Open it in a browser

Go to **<http://127.0.0.1:5000>** and sign in with one of the accounts below.

---

## 9. Default accounts

These are **development** accounts created by `scripts/seed_db.py`:

| Role | Email | Password |
|------|-------|----------|
| Administrator | `admin@cmims.local` | `Admin@2026#ICT` |
| ICT Officer | `officer1@cmims.local` | `Officer@2026#One` |
| ICT Officer | `officer2@cmims.local` | `Officer@2026#Two` |
| Viewer | `viewer@cmims.local` | `Viewer@2026#One` |

> **Change these before deploying.** Passwords are stored only as Werkzeug
> hashes, so they cannot be recovered — they can only be replaced.
>
> * Sign in and open **Profile → Change password** to replace your own.
> * Administrators can reset anyone's password from
>   **Administration → User accounts → Edit** (leave the password blank to keep
>   the current one), or deactivate accounts that should no longer exist.
> * You can also delete `instance/computer_maintenance.db` and re-create the
>   database, then add your own accounts from the user-management screen.

---

## 10. How to use the system

**Register equipment** — *Inventory → Register equipment*. Fill in the asset
tag (must be unique), name, type, department and condition. Purchase and
warranty dates are optional but enable the warranty reports and watchlists.

**Report a fault** — *Faults → Report a fault* (or *Report a fault* on an
equipment record). Choose the equipment, describe the problem, pick a category
and priority, and add an optional screenshot or PDF. The system allocates the
reference number.

**Acknowledge and assign a fault** — open the fault and use the quick action
`Move to Acknowledged`, then **Assign fault** to choose the ICT officer
responsible. **Change priority** escalates or de-escalates it; **Add
troubleshooting note** records what was investigated.

**Record a repair** — from the fault, click **Record a repair** (or *Maintenance
→ Record maintenance*). Describe the diagnosis and the work performed, set the
cost and the outcome. The equipment's status is updated automatically according
to the outcome.

**Resolve and close a fault** — once a repair is linked, *Resolve the fault*
becomes available; resolution notes are required. After a fault is *Resolved*
you can *Close* it. Every transition stores the previous status, the new status,
the responsible user, the notes and the timestamp — and appears in the fault's
status history and in the audit trail.

**Record maintenance that is not a fault repair** — *Maintenance → Record
maintenance*, choose the equipment and type (for example *Preventive
Maintenance* or *System Update*) and leave the fault link empty.

**Schedule preventive maintenance** — *Maintenance → Preventive schedules →
Schedule servicing*. Pick the equipment, date, type and officer, and give
instructions. Schedules that pass their date are flagged *Overdue*, and those
due within the next two weeks are listed at the top of the page and on the ICT
dashboard. Use **Complete this schedule** to close it and (optionally) create
the maintenance record in one step.

**Generate reports** — *Organisation → Reports*. Choose a report, set the date
range and any department/type/status filters, then **Generate**. Use **Export
CSV** to download the same rows as a spreadsheet, or **Print** for a
print-friendly copy.

**Manage user accounts** — *Administration → User accounts*: create an account,
choose its role, edit it, reset a password or deactivate/reactivate it.
Deactivated accounts keep all their history but cannot sign in.

**Review the audit trail** — *Administration → Audit trail*. Filter by action,
entity, user or date to see exactly who created, changed or retired a record and
when.

---

## 11. Security measures

| Requirement | How CMIMS implements it |
|-------------|-------------------------|
| **Password hashing** | `Werkzeug.generate_password_hash()` (scrypt) on every password change; verification through `check_password_hash()`. Plain-text passwords are never stored or logged. |
| **Authentication** | Flask-Login sessions. `@login_required` plus the permission decorators protect every route; `login_manager.session_protection = "strong"`. |
| **Role-based authorization** | Permission strings granted by `Role` subclasses and checked server-side by `permission_required()` / `roles_required()` on every route. Hiding a button is only a convenience. |
| **Active-account checks** | Inactive accounts cannot log in, `User.can()` returns `False` for them, and a `before_request` guard signs out an account that is deactivated mid-session. |
| **CSRF protection** | `Flask-WTF`'s `CSRFProtect` globally; every state-changing form (including logout, deactivate and activate) carries a token. |
| **SQL injection protection** | All data access goes through SQLAlchemy ORM expressions with bound parameters. No query is built by string concatenation. |
| **Input validation** | WTForms validators (required fields, lengths, email format, date ranges, numeric costs) plus a second layer of validation in the services, which is the real security boundary. Filter values are validated and invalid ones ignored. |
| **XSS protection** | Jinja2 autoescaping stays on for all untrusted text; the only `|safe` usage is on markup the application generates itself, and multi-line text is escaped before `<br>` is inserted. |
| **Server-side form validation** | Every form is validated in Flask-WTF *and* re-checked in the service layer, because a crafted POST bypasses the browser entirely. |
| **Unauthorized record modification** | Every mutating route has a permission decorator, and the service layer re-checks ownership/state (for example only ICT staff can be assigned faults, and a fault cannot be resolved without a repair record). |
| **Safe error handling** | Custom 400/403/404/413/500 pages, no stack traces or configuration shown to users; the 500 handler rolls the session back. |
| **Secure configuration** | `SECRET_KEY`, `DATABASE_URL`, `UPLOAD_FOLDER` and cookie settings come from environment variables / `.env`; `SESSION_COOKIE_HTTPONLY`, `SAMESITE=Lax` and (in production) `SESSION_COOKIE_SECURE=True`. Debug mode is off by default. |
| **Audit logging** | A reusable `AuditService` writes the trail; every business change and its audit entry share one database transaction. No route edits or deletes audit rows. |
| **Account activation/deactivation** | Accounts are deactivated rather than deleted, deactivated users cannot sign in or act, and the last active administrator is protected. |
| **Database integrity constraints** | Unique constraints (email, asset tag, serial uniqueness via service check, fault reference), not-null constraints, foreign keys and cascade rules for history rows. |
| **File upload validation** | Optional fault attachments only: extension allowlist, 2 MB request limit (`MAX_CONTENT_LENGTH`, HTTP 413 handled), `secure_filename()` plus a random name, and storage outside the served static tree so files can never execute. |
| **Sensitive data in logs** | Audit descriptions contain human labels only — never passwords, hashes or session data. |

---

## 12. Testing instructions

The test-suite uses **pytest** and its own temporary SQLite database, so running
it never touches `instance/computer_maintenance.db`.

```bat
:: Windows Command Prompt and PowerShell — from the project folder, venv active
pytest
```

```bash
# macOS / Linux
pytest
```

Useful variations:

```bat
pytest -v                          :: one line per test
pytest tests/test_auth.py          :: a single file
pytest -k equipment                :: tests whose name contains "equipment"
pytest --tb=short                  :: shorter tracebacks
```

Expected result:

```
139 passed
```

What is covered:

| File | Coverage |
|------|----------|
| `tests/test_auth.py` | Administrator/ICT officer/viewer login, invalid credentials, password hashing, logout, inactive accounts, login auditing, profile and password change, login-form validation. |
| `tests/test_equipment.py` | Registration, duplicate asset tag and serial number, service-level re-validation, invalid dates, retrieval, editing, status-change history, retirement, search/filtering, pagination, relationships. |
| `tests/test_faults.py` | Recording faults, reference-number generation, persistence, invalid data, status updates, status history, illegal transitions, "no repair record" rule, resolution and closure, assignment, notes, search and pagination. |
| `tests/test_maintenance.py` | Creating records, equipment/fault links, mismatched fault rejection, history retrieval, invalid data, status side effects of each outcome, editing, schedule creation, officer-only assignment, completion, overdue/due recalculation, cancellation. |
| `tests/test_permissions.py` | Anonymous access to every protected page and POST route, viewer restrictions across all modules, ICT officer vs administrator-only areas, inactive-account behaviour, the permission matrix itself. |
| `tests/test_audit.py` | Audit entries for registration, fault reporting, status changes, maintenance, account creation and retirement; the actor/timestamp are present; no passwords inside; the trail can be filtered; no route modifies audit rows; a single shared logging helper is used. |
| `tests/test_reports.py` | Dashboard figures from the database, trend series, search/filter correctness, invalid filter tolerance, all five report pages, condition grouping, CSV contents and filter-respecting exports, export permission. |
| `tests/test_models.py` | Role objects, unknown-role failure, activate/deactivate, unique email, user↔audit relationships, department relationships, warranty states, unique asset tag, condition validation, status-history relationship, fault/maintenance relationships, unique fault reference, the status machine, audit description truncation. |
| `tests/test_pages.py` | Every page renders for each role, detail pages contain the required information, the fault workflow controls appear as the fault progresses, 403/404 pages, and Jinja escaping of user-submitted content. |

---

## 13. Limitations

* **Single-organisation system.** There is no multi-tenant or multi-branch
  isolation; it models one organisation's ICT department.
* **SQLite.** Excellent for a single server or a departmental deployment, but it
  is not designed for high write concurrency across many simultaneous users.
  Moving to PostgreSQL/MySQL means changing `DATABASE_URL` and re-running the
  scripts.
* **No email notifications.** Preventive-maintenance reminders appear in the
  application (dashboard, schedule list, reports) rather than being emailed.
* **PDF export is not implemented.** Reports can be printed from the browser
  (which produces a PDF on most systems) and exported to CSV.
* **One attachment per fault.** Additional photos or documents are not
  supported, and attachments are stored on the local filesystem rather than in
  object storage.
* **No barcode/QR integration.** Asset tags are entered and searched as text;
  labels and scanners are not yet integrated.
* **No offline mode or mobile application.** The interface is responsive but the
  application requires a network connection to the server.
* **Password policy is basic.** Minimum length plus letters and numbers; there
  is no password history, expiry or two-factor authentication.
* **No rate limiting** on the login form (failed attempts are audited, but not
  throttled).
* **Reporting is tabular.** There are simple bar and trend visualisations but no
  advanced analytics or charting library.

---

## 14. Future improvements

1. **QR codes for equipment identification** — generate a QR label per asset and
   open the equipment record by scanning it.
2. **Barcode scanning** — scan asset tags during stock verification and
   physical audits.
3. **Email and SMS maintenance reminders** — notify the assigned officer when a
   schedule becomes due or overdue.
4. **PDF report generation** — server-side PDF templates for signed-off
   inventory and maintenance reports.
5. **Advanced analytics** — failure rates per model, mean time between failures,
   repair cost per department and trend forecasting.
6. **Equipment depreciation tracking** — book value over time with a
   depreciation schedule.
7. **Warranty and licence alerts** — automatic notifications ahead of warranty
   and software-licence expiry.
8. **Network device monitoring** — poll switches, routers and servers for
   availability and raise faults automatically when a device goes down.
9. **Integration with organisational asset systems** — import/export against a
   central asset register or finance system (CSV and API).
10. **Mobile companion app / PWA** — offline fault logging for officers working
    away from a desk.
11. **Bulk operations** — bulk import of equipment from a spreadsheet and bulk
    reassignment between departments.
12. **Two-factor authentication and password policy hardening** for
    administrator accounts.

---

## Project structure

```
computer_maintenance_system/
├── app.py                 # application factory, template helpers, error handlers, CLI
├── config.py              # base / testing / production configuration
├── extensions.py          # db, login_manager, csrf instances
├── requirements.txt
├── pytest.ini
├── README.md
├── .env.example
├── .gitignore
├── models/                # SQLAlchemy models + role policy objects
├── routes/                # blueprints (HTTP layer) + authorization decorators
├── services/              # business logic, audit logging, reporting
├── forms/                 # Flask-WTF forms
├── templates/             # Jinja2 templates (base + macros + per module)
├── static/css, static/js  # theme stylesheet and progressive-enhancement script
├── instance/              # SQLite database (created at runtime, git-ignored)
├── scripts/               # init_db.py, seed_db.py
└── tests/                 # pytest suite
```
