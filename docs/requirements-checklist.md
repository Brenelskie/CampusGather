# Requirements and verification map

This maps intended behavior to code, application entry points, and checks. A linked test is a check to run, not a claim that it passed. `IMPLEMENTATION_STATUS.md` records authoritative results for this delivery. Manual and live-provider checks remain separate from mocked tests.

| Requirement | Application/API evidence | Automated check or source | Manual proof |
|---|---|---|---|
| Seven domain resources have CRUD | `/manage/organizations/`, `/manage/venues/`, `/manage/categories/`, `/manage/events/`, `/manage/agenda-items/`, `/manage/announcements/`, `/registrations/`; seven `/api/` resources | `events/tests/test_website.py`, `test_api.py`; `events/resources.py` | Create/read/edit/delete an authorized unused example of each, including registration |
| Public discovery and private drafts | `/`, `/events/<id>/`; event/agenda/announcement API scopes | `events/permissions.py`, `test_website.py`, `test_api.py` | Visitor sees published/cancelled; draft and its children hidden |
| Student signup and administrator role assignment | `/accounts/signup/`, `/accounts/roles/` | `accounts/tests.py`, `events/permissions.py` | New signup has no organizer access; admin grants/revokes without data loss |
| Organizer ownership | Organizer dashboard, scoped form relations, API writes | `events/forms.py`, `services.py`, `test_website.py`, `test_api.py` | Organizer A cannot change B's records or use B's relations |
| Private registrations and read-only organizer roster | `/registrations/`, `/events/<id>/roster/`, `/manage/registrations/`, registration API | `test_website.py`, `test_api.py` | Two students cannot read each other's rows; organizer reads own-event roster only |
| Future published registration and timed note edits | Event Register, personal/admin note edit, registration API | `models.py`, `services.py`, `test_rules.py`, `test_api.py` | Draft/cancelled/started refused; self creation server-controlled |
| One registration per student/event and concurrent safety | Duplicate form/API submissions | Unique constraint; `test_rules.py`, `test_concurrency.py` | Friendly duplicate; one retained row |
| Time, coordinate, and shared-owner validation | Venue, event, agenda forms and API | `models.py`, `test_rules.py`, `test_api.py` | Invalid range/time/relation errors preserve valid data |
| Event state transitions and agenda-safe rescheduling | Event form/API | `models.py`, `test_rules.py`, `test_website.py`, `test_api.py` | Draft publish/cancel; published cancel; cancelled stays terminal; agenda blocks invalid schedule |
| Protected and cascading deletion | HTML POST confirmations; API DELETE | `models.py`, `services.py`, `test_website.py`, `test_api.py` | In-use catalog/registered event retained; otherwise event children cascade |
| API fields, permissions, and session CSRF | All seven collections/details; `/api-auth/login/` | `events/api/`, `test_api.py` | Postman cookie/token flow; unsafe request without token fails |
| Event-date forecast with units and attribution | Event detail weather panel | `weather.py`, `test_weather.py` | Compare displayed date to event Manila date; identify source/fetch time |
| Forecast bounds, cache, payload/network failure | Near-future and twenty-day example event | `test_weather.py` | Record live result separately; unavailable state preserves event actions |
| Saved venue map, safe popup, typed fallback, attribution | Venue form and event detail | Map scripts under `static/`, website tests for server data | Keyboard entry, CDN/tile block, narrow screen, safe popup text |
| Repeat-safe synthetic examples without committed passwords | `manage.py seed_demo` | `test_seed.py` | Repeat preserves counts/edits/passwords/roles; no administrator seeded |
| Reproducible group handoff and explanation | README, ER/API/demo/walkthrough/presentation docs | Dependency pins, `.env.example`, migrations | Groupmate setup run and professor-question practice |

## Completion checks

- [x] Dependency consistency, Django system check, 65 tests, migration drift, fresh migration application, and static collection checks have recorded results.
- [x] All seven HTML/API CRUD resources and administrator flows have automated coverage; critical student/organizer flows, denied access, validation and browsable API POST have browser evidence.
- [x] Keyboard access, narrow-screen layout, map fallback, attribution and live weather were checked; broader accessibility/device limits are recorded.
- [x] A second seed run preserves existing rows and credentials; no database reset is needed.
- [ ] A groupmate follows the README in a clean checkout and records any setup problem.
- [ ] Repository owner, URL, visibility, and intended shared commit are verified before claiming publication.
- [ ] Any requested deployment or additional rubric item has a separate implementation and verification result.

No test totals are fixed here because the suite may grow. PWA, Docker, OAuth, AI, and hosted deployment are outside this version's implementation; their course relevance must be confirmed before promising them.
