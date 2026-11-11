# Guided code walkthrough

This guide tours the complete source already in the repository. Read the linked files rather than creating another copy of the project. Run commands from the project root using its existing virtual environment. Record actual results separately from expected results. Each exercise is small enough for a groupmate to explain and review.

## 1. Environment and Django project

Read [requirements.txt](../requirements.txt), [settings.py](../config/settings.py), [.env.example](../.env.example), and [manage.py](../manage.py). Follow the README's environment/migration setup first.

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
```

Expected: the project interpreter runs, dependencies are consistent, and Django reports no system-check errors. If Django is missing, install requirements through this exact interpreter. If tables are missing, run `migrate`. Do not solve setup errors by deleting data.

Questions: **Why a virtual environment?** It separates this project's dependencies. **Why `.env`?** It holds local settings without committing secrets. **Why no Node setup?** Django serves the application and its browser JavaScript needs no build pipeline.

Exercise: explain `INSTALLED_APPS`, middleware, templates, and the SQLite setting to a groupmate.

## 2. Models, migrations, and validation

Read [models.py](../events/models.py), [the migration](../events/migrations/0001_initial.py), [services.py](../events/services.py), and the [ER diagram](er-diagram.md).

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test events.tests.test_rules
```

Expected: no schema drift and passing rule checks. A migration records schema changes; it is source that groupmates need. Validation errors for event/agenda times or coordinates are deliberate boundaries. Fix the input or the responsible validation, rather than bypassing `full_clean()`.

Questions: **Why separate Category from Event?** Many events reuse a category. **Does `save()` automatically validate everything?** No; the shared write service calls `full_clean()`. **Why also have database constraints?** They protect expressible invariants such as unique registrations even when concurrent writes occur.

Exercise: trace which related rows prevent deleting a registered event.

## 3. Authentication and roles

Read [account forms](../accounts/forms.py), [account views](../accounts/views.py), [account routes](../accounts/urls.py), and [permissions.py](../events/permissions.py).

```powershell
.\.venv\Scripts\python.exe manage.py test accounts
```

Expected: signup/login/role checks pass. Manually sign up a student, create an administrator with `createsuperuser`, and grant organizer access at `/accounts/roles/`. A 403 on the organizer dashboard is expected for ordinary students. Logging in alone does not grant organizer access.

Questions: **Where is the student role stored?** It is the ordinary authenticated-user state; there is no extra role column. **Who grants organizers?** An administrator using the `Organizers` group. **What makes an application administrator?** `is_superuser`, checked server-side.

Exercise: revoke and restore one synthetic organizer's access and verify their records remain.

## 4. Organizer HTML CRUD

Read [resources.py](../events/resources.py), [forms.py](../events/forms.py), [views.py](../events/views.py), [URLs](../events/urls.py), and [resource templates](../templates/events/resource_form.html).

```powershell
.\.venv\Scripts\python.exe manage.py test events.tests.test_website
```

Expected: website checks pass. Manually create/edit/read/delete an unused category, then create the organization, venue, event, agenda, and announcement needed for a full flow. If relation choices are missing, check ownership and role. If a time change is rejected, remove affected agenda items before rescheduling and recreate them inside the new window.

Questions: **Why reuse form/list templates?** The six organizer resources share ordinary CRUD structure. **Why hide another organizer's relations?** Choices and writes must both respect ownership. **Why confirm deletion?** It makes the intended removal explicit, then POST performs the change with CSRF protection.

Exercise: give an invalid end time and explain how the error reaches the form without changing the record.

## 5. Student registrations and transactions

Read Registration in [models.py](../events/models.py), the registration views in [views.py](../events/views.py), [services.py](../events/services.py), and [concurrency tests](../events/tests/test_concurrency.py).

```powershell
.\.venv\Scripts\python.exe manage.py test events.tests.test_rules events.tests.test_concurrency
```

Expected: duplicate and transaction checks pass. Demonstrate registration, private detail, note edit, and cancellation in the browser. A published event must still be in the future. Cancelled/started events refuse new registrations and note edits. An existing registration remains readable/deletable by its authorized user.

Questions: **Why not accept a student ID from a form?** Creation must use the authenticated actor. **Why recheck inside a transaction?** Another request may cancel or reschedule an event after a form was opened. **Why SQLite IMMEDIATE mode?** Short writes are serialized before mutable state is checked; external HTTP stays outside these transactions.

Exercise: use two sessions to prove one student cannot read another student's registration.

## 6. REST API

Read [serializers](../events/api/serializers.py), [viewsets](../events/api/views.py), [API permissions](../events/api/permissions.py), and the [Postman guide](api.md).

```powershell
.\.venv\Scripts\python.exe manage.py test events.tests.test_api
```

Expected: API checks pass. Use `/api-auth/login/` in the browsable API, or the documented Postman session flow. A missing CSRF token on an authenticated write should fail. When using Postman after login, read the rotated CSRF cookie.

Questions: **What is a serializer?** It translates approved fields between model records and JSON and validates input. **Why scope querysets as well as check permissions?** Hidden records must not leak through list/detail reads. **Why share services with HTML?** Both interfaces must enforce the same write rules.

Exercise: PATCH an event end before its start and identify the returned field error.

## 7. Maps and event-date weather

Read the venue/event map code under [static](../static/), [event detail template](../templates/events/event_detail.html), and [weather.py](../events/weather.py).

```powershell
.\.venv\Scripts\python.exe manage.py test events.tests.test_weather
```

Expected: mocked weather checks pass. Manually verify saved coordinates and marker, map attribution, keyboard coordinate entry, narrow layout, and map-failure fallback. Then inspect a near-future event with live connectivity. The server uses the event's Manila start date and accepts offsets 0–15 inclusive; offset 16/past must short-circuit before cache/network access. Only a validated matching-date success is cached for fifteen minutes.

Questions: **Is weather a database table?** No; it is external JSON with a temporary cache. **Why not use today's forecast for every event?** That would misrepresent the event date. **What if a provider fails?** Show an unavailable state and keep event/registration flows usable.

Exercise: compare the near-future workshop with the twenty-day research showcase and explain their different weather states.

## 8. Repeatable handoff and presentation

Read [seed_demo.py](../events/management/commands/seed_demo.py), [seed tests](../events/tests/test_seed.py), [the demo](demo.md), and [presentation notes](presentation.md).

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py test events.tests.test_seed
```

The first command assumes demo users already exist; otherwise supply the password through the README prompt. Expected: matching rows are preserved and the repeat run creates no duplicate examples. A changed password argument does not reset existing users. Ask a groupmate to follow the README in their own checkout and record what actually happened.

Questions: **Why synthetic data?** It makes a safe, understandable classroom example. **What belongs in Git?** Source, migrations, dependency pins, and `.env.example`; local secrets, virtual environments, and databases stay local. **Does a local commit prove GitHub publication?** No; verify the intended repository and accessible commit separately.

Exercise: make a small copy edit on a branch, inspect the diff, commit the intended file, and have a groupmate review it in a pull request once a repository has been agreed.
