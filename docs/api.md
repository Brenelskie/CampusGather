# REST API and Postman

Start the server and use `http://127.0.0.1:8000` as the base URL. `/api/` is the browsable API root. IDs below are database IDs, not array positions. A list is paginated with `count`, `next`, `previous`, and `results`; use `?page=2` for the next page when available. There are no API search/category filters. The HTML event list provides those filters.

| Resource | Collection: GET, POST | Detail: GET, PUT, PATCH, DELETE |
|---|---|---|
| Organization | `/api/organizations/` | `/api/organizations/<id>/` |
| Venue | `/api/venues/` | `/api/venues/<id>/` |
| EventCategory | `/api/categories/` | `/api/categories/<id>/` |
| Event | `/api/events/` | `/api/events/<id>/` |
| AgendaItem | `/api/agenda-items/` | `/api/agenda-items/<id>/` |
| Registration | `/api/registrations/` | `/api/registrations/<id>/` |
| Announcement | `/api/announcements/` | `/api/announcements/<id>/` |

Permissions determine which methods and rows each person may use. Public reads include catalog records and published/cancelled events and their children. Drafts are visible only to their organizer and administrators. Students read only their registrations. Organizers additionally read registrations for their own events, but cannot edit/delete somebody else's registration. Administrators can read/edit/delete all registrations. Registration creation always belongs to the acting user, including an administrator.

## Log in without disabling CSRF

The API uses Django sessions, not bearer tokens. An authenticated unsafe request needs both the session cookie and a current CSRF token.

The easiest browser demonstration is to open `/api/`, follow the Login link to `/api-auth/login/`, and sign in. The browsable API forms carry CSRF automatically. A student can test registration; use an organizer for catalog/event writes. Do not put real credentials into saved/shared examples.

For Postman:

1. Send GET `http://127.0.0.1:8000/accounts/login/`. Keep Postman's cookie jar enabled. The response sets `csrftoken` and includes a hidden `csrfmiddlewaretoken` field.
2. Send POST to the same URL with body type **x-www-form-urlencoded** and fields `username`, `password`, and `csrfmiddlewaretoken`. Use the token from that GET response. Set `Referer` to `http://127.0.0.1:8000/accounts/login/`. Let Postman retain response cookies, including `sessionid`.
3. Login rotates the CSRF token. Read the current `csrftoken` from Postman's cookie jar after login, rather than reusing the earlier value.
4. For API POST/PUT/PATCH/DELETE requests, set `X-CSRFToken` to that current value. Set `Content-Type: application/json` for a JSON body. Keep the same host and port so the session and CSRF cookies are sent. On HTTPS, also use the same-origin `Referer`.
5. Send GET `/api/registrations/` to check the authenticated user's scoped list. If a write returns 403, inspect both the role and CSRF message. Do not turn off Django's CSRF middleware or change authentication to work around it.

Clear the client cookies or log out before changing demo users. An empty registration list can be a valid privacy result. Never share an exported Postman environment containing passwords, session cookies, or CSRF tokens.

## Create examples in dependency order

Create Postman variables `base_url`, `organization_id`, `venue_id`, `category_id`, `event_id`, `starts_at`, and `ends_at`. Set `base_url` to the local URL above. Choose `starts_at` about two days in the future and `ends_at` two hours later, using ISO 8601 timestamps such as `YYYY-MM-DDT09:00:00+08:00` with actual numbers. Use that same date for agenda times. Save each created response's `id` into the next variable manually. Numbers substituted into JSON must remain unquoted.

As an organizer, POST `{{base_url}}/api/organizations/`:

```json
{
  "name": "Practice Computing Society",
  "description": "A synthetic practice organization.",
  "contact_email": "practice@example.test"
}
```

POST `/api/venues/`:

```json
{
  "name": "Practice Hall",
  "address": "Example campus, Puerto Princesa",
  "latitude": 9.7392,
  "longitude": 118.7353
}
```

POST `/api/categories/`:

```json
{
  "name": "Practice Workshop",
  "description": "A learning activity."
}
```

POST `/api/events/` after saving the three IDs:

```json
{
  "organization": {{organization_id}},
  "venue": {{venue_id}},
  "category": {{category_id}},
  "title": "Practice Python Workshop",
  "description": "A synthetic event for the API demonstration.",
  "starts_at": "{{starts_at}}",
  "ends_at": "{{ends_at}}",
  "status": "draft"
}
```

POST `/api/agenda-items/` using the event window for this simple example:

```json
{
  "event": {{event_id}},
  "title": "Workshop session",
  "description": "Introduction and practice.",
  "starts_at": "{{starts_at}}",
  "ends_at": "{{ends_at}}"
}
```

POST `/api/announcements/`:

```json
{
  "event": {{event_id}},
  "title": "Welcome",
  "body": "Please check the saved venue before attending."
}
```

Publish with PATCH `/api/events/{{event_id}}/`:

```json
{"status": "published"}
```

Log in as a student, refresh the session/CSRF cookies, and POST `/api/registrations/`:

```json
{
  "event": {{event_id}},
  "attendance_note": "I would like help with the beginner exercises."
}
```

The server supplies `student` and `created_at`. PATCH the new `/api/registrations/<id>/` with `{"attendance_note": "Updated practice note."}`. Use synthetic, ordinary participation notes; avoid sensitive personal information.

## Fields and update rules

Every resource returns `id`. The JSON examples list writable business fields. Announcement also returns `created_at`. Registration returns `student` and `created_at`. These server fields should be omitted from write bodies. Unknown field names and conflicting read-only identities produce validation errors.

`owner` is an optional **write-only** field for Organization, Venue, and EventCategory. Ordinarily omit it: ownership defaults to the acting organizer. An administrator may assign an eligible organizer/administrator when creating a catalog record. Ownership cannot change on update. No response exposes `owner`; `contact_email` is returned only to the organization's owner or an administrator.

PUT supplies a full set of required writable fields. PATCH changes selected fields, but the shared service validates the whole prospective record. Existing event `organization`, child `event`, and registration `event`/`student` cannot be changed. Venue/category must have the event organization's owner. Valid event transitions are Draft → Published or Cancelled, and Published → Cancelled. Cancelled cannot reopen. Note edits stop when an event starts or is cancelled, including administrator edits; authorized deletion remains available.

## Expected outcomes

| Status | Meaning and practice check |
|---|---|
| 200 | Read or successful PUT/PATCH |
| 201 | Record created |
| 204 | DELETE completed; response has no JSON body |
| 400 | Invalid fields, duplicate registration, invalid times/relations, or forbidden identity change |
| 403 | Authentication/role/ownership permission denied or failed CSRF check |
| 404 | Unknown record or a row hidden by the caller's scope, such as another student's registration |
| 409 | Protected deletion, such as an event that still has registrations |
| 503 | A temporary database lock exhausted its wait; retry after another update finishes |

Validation errors normally use field names with a list of messages; cross-field errors use `non_field_errors`. Permission/conflict errors use `detail`. Do not rely on every denied write using the same status: collection permissions, scoped record lookup, and field validation protect different boundaries.

Practice checks: submit the same registration twice (400 and one row), set event end before start (400), request a draft as a visitor (404), PATCH another student's note (denied), and DELETE a registered event as its organizer (409). To remove the practice event completely, authorized students/admin must delete its registrations first. Then delete the event; its agenda and announcements cascade. Catalog records can be deleted after no events reference them.

The implementation is in [serializers](../events/api/serializers.py), [viewsets](../events/api/views.py), [permissions](../events/api/permissions.py), and the shared [write service](../events/services.py).
