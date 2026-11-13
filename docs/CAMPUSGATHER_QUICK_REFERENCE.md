# CampusGather — defense quick reference

**Purpose:** Campus event discovery, schedules, locations, announcements, and personal registrations. **Flow:** browser → URL → view → form/serializer → shared service → model → SQLite → HTML/JSON response. CSS styles pages; JavaScript handles maps.

**Stack:** Python + Django + Django REST Framework + SQLite; HTML/CSS/JavaScript; Leaflet + OpenStreetMap tiles; `requests` + Open-Meteo. No Node runtime needed. Local root: `C:\Users\brene\Desktop\CampusGather`.

| Role | Actual permission |
|---|---|
| Visitor / student | Public Published/Cancelled events; logged-in users register as themselves, read own registrations, edit note while open, cancel own registration. |
| Organizer | `Organizers` group or superuser; manage own six resources; read own event rosters. Cannot change another student's registration. |
| Administrator | Authenticated `is_superuser`; all domain management and role assignment. `is_staff` alone is not app admin. Native admin domain tables are read-only. |

| Seven models | Main relationship / API collection |
|---|---|
| Organization | user owner → many events; `/api/organizations/` |
| Venue | owner, address, latitude/longitude → many events; `/api/venues/` |
| EventCategory | owner → many events; `/api/categories/` |
| Event | organization + venue + category; `/api/events/` |
| AgendaItem | event, title, start/end; `/api/agenda-items/` |
| Registration | event + student, note, created time; `/api/registrations/` |
| Announcement | event, title/body, created time; `/api/announcements/` |

**Keys/rules:** automatic `id`; foreign key links rows. Registration is the student/event connecting model; unique `(event, student)`. No direct app `ManyToManyField` or one-to-one profile. New Event starts Draft → Published or Cancelled; Published → Cancelled; Cancelled cannot reopen. End > start; agenda inside event; related catalog owners match. Registration/note changes only for future Published events; cancellation remains allowed. Owner and parent identities cannot be transferred.

**CRUD:** Create / Read / Update / Delete. Organizer: `/organizer/` and `/manage/<resource>/`; student: event Register + `/registrations/`; admin: `/manage/registrations/`, `/accounts/roles/`, `/admin/`. HTML deletion = confirmation + POST. Cleanup new practice data: **Registration → AgendaItem → Announcement → Event → Venue/Category/Organization**. Event deletion cascades agenda/announcements; registrations and referenced parents use PROTECT.

**API:** `/api/`; detail adds `<id>/`. GET read; POST create; PUT full required fields; PATCH selected fields; DELETE remove. JSON is named structured data. Serializer checks fields and calls shared service. Session login + CSRF required for unsafe methods. Server assigns registration student. Lists paginate 20; HTML search/category filters are not API filters. Codes: **200** OK, **201** created, **204** deleted, **400** invalid, **403** denied/CSRF, **404** missing/hidden, **409** protected delete, **503** database busy.

**Map:** Venue coordinates → view `map_data` → template `json_script` → `event-map.js` → Leaflet marker + OSM tiles. Latitude −90..90, longitude −180..180, finite numbers. Form click/drag fills coordinates; Save persists them. Popup uses `textContent`; address/coordinates remain if map fails.

**Weather:** `events/weather.py::forecast_for_event`; saved coordinates + event's **Asia/Manila date** → Open-Meteo daily min/max °C, condition/icon, optional rain. Eligible offsets **0–15 inclusive**; states available / past / out_of_range / invalid_location / temporarily_unavailable. Missing rain ≠ 0%. Valid success cached **900s**, parameter-hash key `event-weather:v2:`; failures not cached; timeout `(2, 3)`. Source/licence visible. Historical screenshot not reproduced; live Nov 13 saved-event requests succeeded; optional-rain defect independently fixed. Never call mock/old data live.

**Back/security:** `events/navigation.py` validates `return_to`, filters/page and role-aware fallbacks; `event_parent` must match the authorized record's event. No dependency on history. `next` is login continuation. Shared `save_record`/`delete_record` check access and atomic writes; `full_clean()` before `save()`. Django hashing, sessions, CSRF, escaping, ORM and constraints; ordinary `save()` does not run all validation.

**Rehearse:** organizer creates/reads/updates six synthetic resources → student creates/reads/edits registration → map/weather/Back → roster/admin/API → authorized dependency-safe deletion. Explain one request fully. Say truthfully that AI helped and identify the code you understand.

**Local commands:** `.\.venv\Scripts\python.exe manage.py` followed by `check`, `migrate`, `makemigrations --check --dry-run`, `test --noinput`, `createsuperuser`, or `runserver`. Open `http://127.0.0.1:8000/`. Demo users: `demo_organizer`, `demo_student`, `demo_student2`; chosen local passwords, no seeded admin. Seed preserves old dates/passwords/roles/data. **Evidence:** latest counts and manual/live limits in [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md); mocked weather tests ≠ live verification. Study [lessons](CAMPUSGATHER_STUDENT_STUDY_GUIDE.md) and [full walkthrough](CAMPUSGATHER_COMPLETE_WALKTHROUGH.md).
