# CampusGather implementation status

Verified locally on 11 November 2026 using Python 3.13.5 on Windows. The application is built in `C:\Users\brene\Desktop\CampusGather`. No repository has been published and no hosted deployment is claimed.

## Completed milestones

| Milestone | Result |
|---|---|
| Environment | Reused working `.venv`; installed pinned Django 5.2.19 LTS, DRF 3.18.3, requests 2.34.2, python-dotenv 1.2.4 |
| Django foundation | Settings, URLs, authentication, static files, private local environment and initial migration |
| Accounts and database | Student signup, session login/logout, administrator role assignment and exactly seven principal models |
| Complete website | Responsive public discovery/search/filter, event details, organizer dashboard, six organizer CRUD resources, student registration CRUD, organizer roster, administrator registration management |
| REST API | Seven collection/detail resources, GET/POST/PUT/PATCH/DELETE, session/CSRF, ownership, private registrations, immutable identities and useful errors |
| Maps | Leaflet 1.9.4, OSM tiles/attribution, coordinate entry and click selection, safe text popups, fallback |
| Weather | Saved venue coordinates, actual Manila event date, forecast offsets 0–15, daily Celsius range/rain/description, 15-minute success cache, graceful errors |
| Handoff | Repeat-safe synthetic data, tests, README, ER diagram, API/Postman examples, walkthrough, demo, presentation and professor Q&A |

## Final automated results

| Check actually executed | Result |
|---|---|
| `python manage.py test --noinput` | **65 tests passed in 52.682 seconds; zero failures/errors** |
| Focused review-fix suite (API/rules/seed/concurrency) | 38 tests passed in 31.969 seconds |
| `python manage.py check` | No issues, zero silenced |
| `python manage.py migrate --noinput` | Fresh local database migrated successfully |
| `python manage.py migrate --check --noinput` | Passed; no unapplied migrations |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py collectstatic --dry-run --noinput --verbosity 0` | Passed |
| `python -m pip check` | No broken requirements |
| Django template compilation | All 24 templates loaded successfully |
| JavaScript syntax | Both map scripts passed `node --check` |
| Python syntax | All 43 Python files parsed during the simplification pass; final changed production files exercised by the full suite |
| Seed rerun | Zero new users or domain records; existing data/passwords/roles preserved |

The suite covers all seven HTML and REST CRUD resources, authentication, CSRF, role/ownership restrictions, draft privacy, registration privacy/duplicates/notes/cancellation, administrator actions, schedule/coordinate validation, protected/cascading deletion, competing SQLite writes, mock weather failures/success/cache and sample-data preservation. Tests use a separate test database.

There is no separately configured lint or static type-check command. Node was used only for browser/JavaScript verification; the application itself needs no Node runtime or npm dependencies.

## Errors found and corrected

- First full run: 58 tests, one assertion failure and one page error. A search assertion mistook a category label for an event result; it now checks the actual result list. Closed-event registration GET attempted to add an error to an unbound form; it now renders the closed state safely.
- Malformed category parameters were reproduced as Unicode conversion and oversized SQLite integer errors. They now produce an empty result safely. Event pagination now has explicit date/ID ordering.
- Independent code review completed with nine perspectives. Its three confirmed findings were fixed: browsable form CSRF metadata is accepted without relaxing session/CSRF checks or unknown JSON fields; new user-created events must begin as drafts; sample data cannot enroll pre-existing student accounts or recreate cancelled registrations.
- Five new review regressions were run before those fixes and all five failed for the expected reasons. They pass after the fixes. The agenda race test was strengthened and both write orderings are checked explicitly.
- The completed review receipt is `20261111-143541-915c113b` in the local Codex temporary review artifacts. No confirmed finding remains unapplied. The review used local independent contexts; a separate-provider pass was unavailable.

## Actual browser and provider checks

Checked in Chromium through Playwright at desktop 1440×1000 and mobile 390×844:

- Public event discovery and event detail rendered; desktop/mobile screenshots inspected.
- Event detail, organizer dashboard and venue form measured a 390-pixel content width without horizontal overflow.
- Student login preserved its return destination. Registration creation, attendance-note editing, POST cancellation and logout worked. Temporary test registration was removed.
- A student visiting the organizer dashboard received the intended 403 page.
- Organizer login/dashboard worked. Invalid latitude produced an accessible field error. Clicking the map filled both coordinates and placed a marker. Saving and deleting that temporary venue worked.
- Event map loaded 12 OSM tiles with a marker and visible attribution. Blocking the Leaflet CDN produced the textual location fallback while event actions remained usable; the block was removed afterward.
- Live Open-Meteo data appeared for the actual 13 November event date, with temperatures, rain probability and fetch time. The twenty-day example displayed the intended unavailable state. Network/payload failures and cache behavior are covered by mocked tests.
- Tab showed the visible skip-link focus and Enter moved to main content.
- The real browsable API HTML POST was reproduced failing before the CSRF fix, then retested successfully with HTTP 201 after restarting the server. The temporary API-created organization was removed.
- A missing favicon discovered in the first browser run was corrected with a local SVG icon.

Browser screenshots remain under ignored `output/playwright/`. Intentional 403/400 and simulated CDN 503 responses during negative tests are expected results, not remaining application errors.

## Current local demo data and account setup

| Model | Rows |
|---|---:|
| Organization | 1 |
| Venue | 2 |
| EventCategory | 2 |
| Event | 5 |
| AgendaItem | 5 |
| Registration | 3 |
| Announcement | 5 |

The three accounts are `demo_organizer`, `demo_student`, `demo_student2`. A random local demo password was stored only in ignored `.env` to load and browser-test the examples; no password is committed or printed. Choose your own login passwords using `manage.py changepassword demo_student` and `manage.py changepassword demo_organizer`. Create your private administrator with `manage.py createsuperuser`. There is no default administrator password.

Use the existing `.venv\Scripts\python.exe` for these commands. The README contains the complete Windows setup and run sequence. The local URL is `http://127.0.0.1:8000/`.

## Remaining manual checks and limits

- Administrator workflows have automated coverage; create your own administrator and rehearse them before presenting.
- A groupmate has not yet followed the README on a second computer. Real phones, other browser engines and a full screen-reader audit are not claimed.
- Postman examples are documented; real authenticated HTTP behavior was tested using Django/APIClient and the browsable API rather than the Postman desktop application.
- SQLite is the local classroom database. Brief competing writes can return a friendly retry response. Production scale/load testing was not performed.
- Weather/CDN/tile availability depends on internet and third-party services. The cache is per process; forecasts are not guarantees, and far-future/past dates intentionally show unavailable.
- Demo dates are fixed on first creation and eventually become past dates. Create fresh draft events rather than resetting the database.
- Git is local on `codex/campusgather`. GitHub destination/account/visibility must be verified before publishing. No remote was configured or changed.
- PWA, Docker, OAuth, AI features and hosted deployment remain future scope, as instructed. Production settings/hosting need their own deployment validation.

The verified required local application is complete. These checks provide evidence for this version, not a claim that software can have no bugs.
