# CampusGather

CampusGather is a Django campus event planner. Students discover events and manage their own registrations. Organizers maintain their own organizations, venues, categories, events, schedules, and announcements. Administrators assign organizer access and can manage all records.

The runtime uses Python, Django, Django REST Framework, SQLite, and server-rendered HTML. Leaflet displays venue maps with OpenStreetMap tiles. A server-side Open-Meteo client supplies a forecast for the event's date. Node.js is not required.

## Try CampusGather

- [Live website](https://bren11.pythonanywhere.com/)
- [GitHub repository](https://github.com/Brenelskie/CampusGather)
- [Hosting, administrator setup, and update guide](docs/deployment.md)

Visitors can browse the synthetic sample events. Choose **Join CampusGather** to create your own student account and try registration. Organizer access is assigned by an administrator; account passwords are kept private. The hosted database is separate from each groupmate's local database.

For your project defense, start with the [quick reference](docs/CAMPUSGATHER_QUICK_REFERENCE.md), then work through the [student study guide](docs/CAMPUSGATHER_STUDENT_STUDY_GUIDE.md). The [complete walkthrough](docs/CAMPUSGATHER_COMPLETE_WALKTHROUGH.md) traces the actual source, and the [presentation guide](docs/CAMPUSGATHER_PRESENTATION_GUIDE.md) provides a timed demonstration and 66 questions with answers. Current verification evidence is in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## Run on Windows with PowerShell

Open this project folder in VS Code, then open its PowerShell terminal. These commands assume Python 3.13 is installed; the development interpreter is Python 3.13.5. Check the selected interpreter rather than relying on the default `py` version.

```powershell
py -3.13 --version
if (-not (Test-Path -LiteralPath .venv\Scripts\python.exe)) {
    py -3.13 -m venv .venv
}
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
.\.venv\Scripts\python.exe -c "from dotenv import dotenv_values, set_key; from django.core.management.utils import get_random_secret_key; dotenv_values('.env').get('DJANGO_SECRET_KEY') or set_key('.env', 'DJANGO_SECRET_KEY', get_random_secret_key())"
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Reuse an existing `.venv` when it uses Python 3.13 and belongs to this project. Commands call its Python directly, so PowerShell script activation is optional. Keep an existing `.env`; do not replace its settings. For local development, set a stable, private `DJANGO_SECRET_KEY` in `.env` so sessions survive server restarts. Keep `.env` out of Git. The debug fallback key is generated per process.

Create synthetic examples with a password you choose locally. This prompt avoids putting a password into PowerShell command history:

```powershell
$demoSecret = Read-Host "Choose a strong demo-only password for the three new demo accounts" -AsSecureString
$env:CAMPUSGATHER_DEMO_PASSWORD = [System.Net.NetworkCredential]::new("", $demoSecret).Password
try {
    .\.venv\Scripts\python.exe manage.py seed_demo
} finally {
    Remove-Item Env:CAMPUSGATHER_DEMO_PASSWORD -ErrorAction SilentlyContinue
    $demoSecret = $null
}
.\.venv\Scripts\python.exe manage.py runserver
```

Open [CampusGather locally](http://127.0.0.1:8000/). Stop the server with Ctrl+C. Maps and live weather require internet access; event information and registration remain usable when either provider is unavailable.

The seed creates `demo_organizer`, `demo_student`, and `demo_student2`. Only a newly created `demo_organizer` receives the `Organizers` group. There is no seeded administrator. Existing usernames retain their passwords, profile data, and roles. On reruns, matching demo names, schedules, and registrations are preserved; ordinary data is never reset. Once all three accounts exist, `manage.py seed_demo` needs no password. The optional `--password` applies only to new accounts and is less suitable for an interactive shell because arguments can enter history. Passwords must pass Django's configured validators and are never printed.

The examples include published events approximately two and five days ahead, a draft, a cancelled event, and an event twenty days ahead. Dates are chosen on first creation and stay fixed on reruns. Old demo events eventually close for registration; use the organizer pages to create fresh examples when needed.

If an existing demo account's password is unknown, change it explicitly with `.\.venv\Scripts\python.exe manage.py changepassword demo_organizer` (or the chosen student username). Running the seed with another password will not reset existing passwords.

Sample registrations are created only for student accounts newly created by that seed run. Existing accounts are never enrolled automatically, and rerunning the seed does not recreate a registration that a student cancelled. For normal event creation, save a draft first, then edit it to publish or cancel.

## Accounts and permissions

Signup creates an ordinary student. Sign in with the administrator created above and visit [Role management](http://127.0.0.1:8000/accounts/roles/) to grant or revoke organizer access. The name of the Django group is exactly `Organizers`. Django's `is_staff` flag alone does not grant the application's administrator role; the application checks `is_superuser`.

| Person | Main actions |
|---|---|
| Visitor | Read published and cancelled events and public catalog information |
| Student | Register as themselves for a future published event; read their own registrations; edit their note while registration is open; cancel their own registration at any time |
| Organizer | Student actions, plus CRUD for their own catalog records/events/agenda/announcements and read-only rosters for their events |
| Administrator | Manage all domain records, view/edit/delete registrations under the same timing rules, and assign organizer access |

Draft events and their agenda/announcements are private to their organizer and administrators. Contact email is private in the API. Event ownership comes from its organization's owner. Users cannot transfer ownership or change a registration's event/student through an edit.

## Find the features

| Feature | Local path |
|---|---|
| Search, category filter, paginated event list | `/` |
| Event details, schedule, announcements, map, weather | `/events/<id>/` |
| Signup and login | `/accounts/signup/`, `/accounts/login/` |
| Organizer dashboard and catalog CRUD | `/organizer/`, `/manage/<resource>/` |
| Personal registration CRUD | `/registrations/` and an event's Register action |
| Organizer roster | `/events/<id>/roster/` |
| Administrator registration management | `/manage/registrations/` |
| Seven JSON resources and browsable API | `/api/` |
| Browsable API session login | `/api-auth/login/` |
| Django administration | `/admin/` |

The six organizer resource names are `organizations`, `venues`, `categories`, `events`, `agenda-items`, and `announcements`. Registrations have their own student and administrator pages. All seven also have REST endpoints. HTML deletion uses a confirmation page and POST. The API uses DELETE. Session-authenticated API writes require CSRF protection.

Important pages have a consistent **← Back** link near the top, including authentication, management, native admin and browsable API screens. It works without JavaScript. Links carry a bounded `return_to` origin so search/category/page context can survive forms. The server checks the destination's host, scheme, registered route, user access and record visibility; invalid or unsafe destinations use a sensible parent. After deletion it returns to a surviving list. `next` remains the separate sign-in continuation.

Actions opened from an event page also carry an `event_parent` ID. The server verifies both access and the edited record's actual parent before using it for Back/Cancel; it cannot redirect to an arbitrary event. The event page still remembers the original filtered list. This metadata is used only by the HTML navigation flow.

Weather uses the saved venue coordinates and the application's configured timezone (`Asia/Manila` here). It distinguishes past dates, dates beyond today plus fifteen days, invalid locations, temporary provider failures and usable forecasts. A missing rain percentage does not discard valid temperatures and conditions; zero still means 0%. Successful forecasts are cached for fifteen minutes, and provider failure reasons are logged without event titles or attendee data. The panel includes Open-Meteo/CC BY 4.0 attribution. See the status record for dated live evidence; a later request may differ.

## Check the project

Run these from another terminal while the server is stopped, or while using its separate development database normally:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py collectstatic --dry-run --noinput
```

Django tests create a separate test database. Weather tests mock external HTTP; they do not establish live provider availability. Follow the [demo checks](docs/demo.md) for browser, keyboard, narrow-screen, map, and live-weather checks. See `IMPLEMENTATION_STATUS.md` for the checks actually recorded for this delivery; this README does not claim that every environment or groupmate has passed them.

Common fixes:

- **`No module named django`:** run pip through `.venv\Scripts\python.exe`, then use the same interpreter for `manage.py`.
- **`no such table`:** run `manage.py migrate` from this folder before seeding or browsing.
- **Organizer page returns 403:** an administrator must grant the `Organizers` group through `/accounts/roles/`.
- **CSRF error:** use one hostname consistently, refresh the login/form page, and keep cookies enabled. Postman instructions are in [API examples](docs/api.md).
- **Forecast unavailable:** read the specific panel message. Check the event date, saved venue coordinates, internet connection and server logs. Only offsets zero through fifteen days are supported, and the provider must return the matching date. A twenty-day demo event intentionally shows “not available yet.” No API key is required. Rerunning the seed preserves old dates; create a new synthetic event through the organizer pages when examples become old.
- **An updated page still looks unchanged:** use Ctrl+F5 to reload cached CSS, then confirm the terminal is serving this CampusGather folder.
- **Port already in use:** run `manage.py runserver 8001` and use that port consistently in the browser and API client.

## Learn and share

The seven application models are Organization, Venue, EventCategory, Event, AgendaItem, Registration, and Announcement. Django's users, groups, sessions, permissions, and admin tables are framework infrastructure and are counted separately.

- [Database relationships and deletion rules](docs/er-diagram.md)
- [REST API and Postman session/CSRF examples](docs/api.md)
- [Demo script and browser checks](docs/demo.md)
- [Code walkthrough, guided stages, and exercises](docs/walkthrough.md)
- [Presentation outline and professor questions](docs/presentation.md)
- [Requirements and verification checklist](docs/requirements-checklist.md)
- [Complete source walkthrough (A–M)](docs/CAMPUSGATHER_COMPLETE_WALKTHROUGH.md)
- [Presentation script and 66 defense questions](docs/CAMPUSGATHER_PRESENTATION_GUIDE.md)
- [Personal study guide: 17 practical lessons](docs/CAMPUSGATHER_STUDENT_STUDY_GUIDE.md)
- [Defense quick reference](docs/CAMPUSGATHER_QUICK_REFERENCE.md)

For group work, share the repository and live website links above. Each member can clone the repository and follow the Windows setup to create their own `.venv`, `.env`, SQLite database, and local accounts. Do not share these generated files or real credentials. Commit source, migrations, dependency pins, and `.env.example`.

Use small branches such as `git switch -c feature/event-copy`, inspect `git diff`, and commit only the intended files with a message describing the behavior changed. Open a pull request and ask a groupmate to run the focused check and explain the change before merging. A useful first exercise is a small event-page copy edit with a screenshot and a reviewer comment.

This version is hosted on PythonAnywhere. It does not implement a PWA, Docker packaging, OAuth, payments, AI features, or attendance QR codes. Confirm any additional course requirements before extending the scope.
