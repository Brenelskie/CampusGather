# Learn CampusGather by tracing the real project

This guide teaches the application in `C:\Users\brene\Desktop\CampusGather`. Read a lesson, open its source, and explain it in your own words before moving on. The code blocks are excerpts from this project; extra example JSON is labelled. Do not run a write example against important data. Use synthetic practice records and your own local accounts.

Use the [complete walkthrough](CAMPUSGATHER_COMPLETE_WALKTHROUGH.md) for the full model inventory and eleven end-to-end workflows, the [presentation guide](CAMPUSGATHER_PRESENTATION_GUIDE.md) for a timed rehearsal and defense questions, and the [quick reference](CAMPUSGATHER_QUICK_REFERENCE.md) during revision. The latest executed checks are in [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md). Instructions to run something are not evidence it has already passed.

Suggested order: lessons 1–5 explain the basic structure and access; 6–11 explain changes and APIs; 12–15 explain maps, weather, and navigation; 16–17 explain verification and running the project. Study in several short sessions. After each session, trace one request without looking at the guide.

## Lesson 1 — Reading a small piece of Python

**Simple explanation.** A program stores values and uses instructions to make decisions. A name such as `starts_at` refers to a value. A function is a reusable group of instructions. A class describes a type of thing, such as an Event. `self` means the particular event being examined. A comparison produces True or False. `and` requires both conditions to be true.

In [`events/models.py`](../events/models.py), an Event answers whether registration is open:

```python
    @property
    def registration_open(self):
        return self.status == self.Status.PUBLISHED and self.starts_at > timezone.now()
```

`==` compares status. `>` compares the saved start time with the current time. `return` gives the answer to the caller. `@property` lets other code read `event.registration_open` like a value, even though Python calculates it. It is not a separate database column.

**Analogy.** A school gate opens only when the event is approved **and** its starting time has not arrived. Passing just one condition does not open it.

**Important terms.** Value: a piece of data. Function: named instructions. Class: a definition for objects. Object: a particular instance. Boolean: True or False. Property: a calculated value accessed like an attribute.

**Practice questions and answers.**

1. What does `self` refer to? **The particular Event object whose property is being read.**
2. Is a future draft open for registration? **No. It also needs Published status.**
3. Is `registration_open` stored in SQLite? **No. It is calculated from status, start time, and the current time.**

**Small exercise.** On paper, evaluate the property for a future published event, a future cancelled event, and a published event that already started. Expected answers: True, False, False.

**Sample professor question.** “Why calculate registration availability instead of storing an `open` flag?” **Answer:** Time changes even when nobody edits the record. This property uses the current time whenever it is checked.

## Lesson 2 — Following one browser request

**Simple explanation.** The browser asks for an address. Django matches that address to a Python function. The function finds the data and sends back a page. The browser then displays it. HTML describes the page content, CSS controls its appearance, and JavaScript supplies interactions such as moving a map marker.

The actual route in [`events/urls.py`](../events/urls.py) is:

```python
    path("events/<int:pk>/", views.event_detail, name="event-detail"),
```

`<int:pk>` means a numeric ID is extracted from the URL. In [`events/views.py`](../events/views.py), the first lookup is:

```python
def event_detail(request, pk):
    event = get_object_or_404(visible_events(request.user).select_related("venue", "organization", "category"), pk=pk)
```

The function uses the requesting user when selecting visible events. If the row is absent or hidden, it returns a 404 response. The remaining function retrieves agenda, announcements, registration and weather, prepares map data, and renders `templates/events/event_detail.html`. The template extends `templates/base.html`; that shared layout includes `static/css/site.css`, navigation, messages, and the footer.

**Analogy.** A receptionist reads a room number, sends the request to the right staff member, and returns the requested information. The address is the room number; the view is the staff member.

**Important terms.** HTTP request: a browser's message to the server. URL: its address. Route: the matching rule. View: request-handling Python code. Template: HTML with values filled in. Response: the server's reply. Query: a request for database records.

**Practice questions and answers.**

1. Does `pk` mean a position in a displayed list? **No. It is a database primary-key value.**
2. Where does the event page's HTML come from? **`templates/events/event_detail.html`, using the shared base template.**
3. Why call `visible_events` before the lookup? **A private draft must not become readable just because someone guessed its ID.**

**Small exercise.** Open `config/urls.py`, `events/urls.py`, `events/views.py`, and the event-detail template. Point to each step for `/events/2/`, without assuming row 2 is visible to every user.

**Sample professor question.** “What is Django's model-template-view pattern here?” **Answer:** Models define stored event data, views handle requests, and templates render the human-readable page.

## Lesson 3 — Understanding the seven database tables

**Simple explanation.** A table stores records of one kind. A row is one record; a field is one value on that record. Instead of repeating all venue information inside every event, an event stores a link to one Venue. That link is a foreign key. Django's model classes describe those tables.

Actual excerpt from [`events/models.py`](../events/models.py):

```python
class Organization(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="organizations")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=3000)
    contact_email = models.EmailField(blank=True)
```

`CharField` stores bounded text. `TextField` stores longer text. `blank=True` permits an empty submitted value; it does not automatically mean SQL NULL. `ForeignKey` points to another row. `PROTECT` prevents deletion of a referenced parent. `related_name` gives code a way to follow the relationship in reverse, such as a user's organizations.

Every model receives an automatic large integer `id` because [`config/settings.py`](../config/settings.py) sets `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`.

| Model | Important actual fields and types | Why it exists and how it relates |
|---|---|---|
| Organization | owner: user foreign key; name: text ≤120; description: optional text ≤3000; contact_email: optional email | Campus group hosting events. One owner can own many organizations; one organization can host many events. |
| Venue | owner: user foreign key; name: text ≤120; address: text ≤250; latitude/longitude: floating-point numbers | Reusable location. One venue can locate many events. Coordinates need finite numbers and valid ranges. |
| EventCategory | owner: user foreign key; name: text ≤80; description: optional text ≤250 | Reusable event label for discovery. One category can classify many events. |
| Event | organization/venue/category: foreign keys; title: text ≤160; description: text ≤6000; starts_at/ends_at: date-time; status: choice text | Central activity record. Links its host, location, type, schedule, and publication state. |
| AgendaItem | event: foreign key; title: text ≤160; description: optional text ≤2000; starts_at/ends_at: date-time | One scheduled part of an event. Many agenda items can belong to one event. |
| Registration | event/student: foreign keys; attendance_note: optional text ≤300; created_at: automatically set date-time | Participation record connecting a student and event. The pair is unique. |
| Announcement | event: foreign key; title: text ≤160; body: text ≤3000; created_at: automatically set date-time | An event's organizer messages. Many announcements can belong to one event. |

Organization, Venue, and EventCategory protect their user owner. Event protects its organization, venue, and category. Registration protects its event and student. AgendaItem and Announcement use CASCADE for their event: deleting that event deletes those children. The seven tables do not define a one-to-one relationship or a direct `ManyToManyField`. Registration is the explicit connecting model for the logical many-to-many student/event relationship.

Source-defined synthetic examples include `Demo: CampusGather Society`, `Demo: Innovation Hall`, and `Demo: Campus Discovery Workshop`. These names come from `seed_demo.py`; they are not a promise that every database has the same IDs or row counts.

**Analogy.** A timetable lists a room number rather than copying the entire room's details into every class. The room table holds the details; the event's foreign key holds the reference.

**Important terms.** Table, row, field, primary key, foreign key, one-to-many, connecting model, PROTECT, CASCADE, constraint.

**Practice questions and answers.**

1. Where is an event organizer's owner stored? **On the related Organization, not a separate Event owner field.**
2. Which model connects students and events? **Registration, with its own note and creation time.**
3. Can a registered event be deleted immediately? **No. Its protected registrations must first be removed by authorized users.**

**Small exercise.** Draw a User, Organization, Venue, EventCategory, Event, AgendaItem, Registration, and Announcement box. Draw every foreign-key arrow. Mark Registration links PROTECT and event-child links CASCADE.

**Sample professor question.** “Why not put an agenda list in one Event text field?” **Answer:** Separate rows let each item have validated start/end times and its own create, edit, and delete actions.

## Lesson 4 — Accounts, passwords, sessions, and roles

**Simple explanation.** An account identifies a person. A password proves access to that account. Django stores a password hash rather than the original password. After login, a session lets the server recognize later requests without asking for the password every time. A role controls the actions that account can perform.

Actual role checks from [`events/permissions.py`](../events/permissions.py):

```python
def is_admin(user):
    return user.is_authenticated and user.is_superuser

def is_organizer(user):
    return user.is_authenticated and (is_admin(user) or user.groups.filter(name="Organizers").exists())
```

[`accounts/forms.py`](../accounts/forms.py) extends Django's `UserCreationForm`. Its accepted profile fields are `username`, `first_name`, `last_name`, and `email`; it inherits the password fields and password checks. [`accounts/views.py`](../accounts/views.py) saves a valid signup, logs the new ordinary student in, and validates any `next` continuation before redirecting.

`accounts/urls.py` uses Django `LoginView` and `LogoutView`. The base template submits logout as POST with a CSRF token. The superuser-only `/accounts/roles/` view adds/removes users from `Organizers`. Revoking organizer access preserves their records. `is_staff` alone does not grant the application's organizer/admin role. Native `/admin/` has Django's separate staff and permission checks.

**Analogy.** An ID card identifies a person; a key proves possession; a permission list determines which rooms they can enter. Being recognized does not allow entry to every room.

**Important terms.** Authentication: identifying the user. Authorization: deciding allowed actions. Hash: one-way password representation. Session: server-recognized login state. Group: a set of users. Superuser: the application's administrator here.

**Practice questions and answers.**

1. Can signup request `is_superuser=true` to become an admin? **No. That is not an accepted signup field.**
2. How does a normal account become an organizer? **A superuser grants the Organizers group through role management.**
3. Do two ordinary browser tabs have independent users? **Usually no. They share session cookies in the same profile. Use separate profiles/private sessions to demonstrate roles.**

**Small exercise.** Read `SignUpForm`, `signup`, and `roles`. Explain why only the last of these assigns organizer access, and why that view requires a superuser.

**Sample professor question.** “Why use Django authentication instead of saving raw passwords?” **Answer:** Django supplies hashing, validation, session integration, and established authentication behavior; this project reuses it.

## Lesson 5 — Visibility, ownership, and privacy

**Simple explanation.** Reading a record and changing a record are different permissions. Public visitors may read published/cancelled events. An organizer can additionally read their own drafts and manage their own resources. A student sees their own registrations. An organizer can read attendees for their event, but that does not permit changing other students' registrations.

Actual event visibility in [`events/permissions.py`](../events/permissions.py):

```python
    public = Q(status__in=[Event.Status.PUBLISHED, Event.Status.CANCELLED])
    if is_organizer(user):
        public |= Q(organization__owner=user)
    return qs.filter(public)
```

`Q` combines database conditions. `|=` adds an OR condition. The omitted earlier branch in the same function returns all events for an administrator. The double underscore in `organization__owner` follows a relationship. `can_manage` checks a direct owner's ID or follows the event's organization to its owner.

The website uses scoped lookups before rendering details. The API has its own scoped querysets and permission classes. The shared service checks permissions again before a change. Therefore hiding the Edit link is only a convenience; it is not the access check. An unauthorized ID may produce 404 because it is outside the caller's queryset, while a role failure may produce 403.

**Analogy.** A notice board may be public while its editing key belongs to one club. Seeing a notice does not give permission to replace it.

**Important terms.** Visibility: which rows can be read. Ownership: who controls a record. Queryset: a Django selection of rows. Scope: the permitted subset. Object permission: permission for a particular row.

**Practice questions and answers.**

1. Can a visitor see a cancelled event? **Yes. Cancelled events remain public, with registration closed.**
2. Can organizer A manage organizer B's venue by guessing its ID? **No. Scoped lookups and service ownership checks reject that.**
3. Does reading a roster permit editing attendees' notes? **No. Ordinary organizers cannot change another student's registration.**

**Small exercise.** Trace `resource_queryset`, `can_manage`, and `RegistrationViewSet.get_queryset`. Write the allowed rows for a student, an organizer, and a superuser.

**Sample professor question.** “Why check permissions in more than the template?” **Answer:** A client can send a request directly without using the template. Server-side views, querysets, and services must enforce access.

## Lesson 6 — HTML forms and reusable CRUD pages

**Simple explanation.** A form collects text and choices from the browser. It turns submitted strings into Python values and reports invalid fields. CampusGather reuses one management page pattern for six resource types. It changes the model and fields, while the common create/edit code stays in one place. Registration has separate student/admin pages.

Actual form factory from [`events/forms.py`](../events/forms.py):

```python
def form_for(model):
    return forms.modelform_factory(model, form=ResourceForm, fields=FIELDS[model])
```

`FIELDS` is a per-model allowed-field list in `events/services.py`. `ResourceForm.__init__` takes the current user and restricts related choices. An organizer sees their own organizations/venues/categories, new event status is Draft, and existing event organization or child event fields are disabled. Date-time fields use `datetime-local`; users enter Philippine local times. Server checks remain necessary even if browser validation or disabled fields are bypassed.

The route `/manage/<resource>/add/` or `/manage/<resource>/<id>/edit/` calls `resource_form`. It constructs the appropriate form. On GET, it displays blank/saved values. On POST, `form.is_valid()` produces `cleaned_data`; the view calls `save_record`, then redirects to the saved detail. Errors render the same form with messages. The `resource` slug must exist in `events/resources.py`.

**Analogy.** A reusable school application form has different sections for different programs, but the office uses the same process to receive and check each submission.

**Important terms.** GET: retrieve/display. POST: submit. Bound form: a form with submitted data. `cleaned_data`: validated Python values. Factory: code that creates the right form class. CRUD: Create, Read, Update, Delete.

**Practice questions and answers.**

1. What are the six generic resource slugs? **organizations, venues, categories, events, agenda-items, announcements.**
2. Does `form.is_valid()` save the record? **No. The view passes valid data to the shared service for the actual write.**
3. What happens to a validation error? **The form redisplays with field/non-field errors; the record is not successfully saved.**

**Small exercise.** Trace Add Venue from `events/urls.py` through `resource_form`, `form_for`, `ResourceForm`, `save_record`, and the detail redirect. Then repeat with EventCategory and identify what changes.

**Sample professor question.** “Why reuse these views?” **Answer:** The six resources share list/detail/form/delete structure. Their field lists, model validation, and permissions still distinguish their behavior.

## Lesson 7 — One write service for both interfaces

**Simple explanation.** Valid data still needs permission and business-rule checks before it is saved. A central function performs these steps for HTML and API callers. A transaction groups the write so a failure can roll it back. The service reloads existing/related records because values selected earlier by a form may have changed meanwhile.

Actual final save steps in [`events/services.py`](../events/services.py):

```python
            if model is not Registration and not can_manage(user, obj):
                raise PermissionDenied("You cannot manage this organizer's records.")
            obj.full_clean()
            obj.save()
            return obj
```

Earlier in `save_record`, `transaction.atomic()` encloses the work; permissions are checked, allowed fields are copied from `FIELDS`, and server-controlled owner/student identities are assigned. `full_clean()` runs model field, model-wide, uniqueness, and constraint validation. Calling ordinary ORM `save()` alone does **not** automatically run all those checks. The database also enforces declared constraints, including unique registration and time/coordinate checks.

`delete_record` repeats authorization and deletes inside a transaction. It converts protected relationships into `ProtectedDeletion` and SQLite lock exhaustion into `TemporarilyBusy`. The HTML layer shows a useful error; the API maps protected deletion to 409 and a temporary database lock to 503. A failed permission must not be “fixed” by removing the check.

**Analogy.** Two doors lead into the same records office: one for people with paper forms, one for computer submissions. Both use the same clerk and rules before changing official records.

**Important terms.** Service: shared application operation. Validation: checking values/rules. Transaction: grouped database work. Atomic: all succeeds or rolls back. Exception: a reported failure. Constraint: a database-enforced rule.

**Practice questions and answers.**

1. Why not let serializers call ordinary `.save()` without this service? **That would split business/permission behavior from HTML and could bypass shared checks.**
2. Does the service accept every submitted field? **No. It copies only fields listed for that model, and controls identities separately.**
3. Why re-read related records inside the transaction? **A previously selected event or relation may now have different values or no longer exist.**

**Small exercise.** In `save_record`, mark the lines that check permission, assign owner/student, copy allowed fields, refresh relations, validate, and save. Explain each in that order.

**Sample professor question.** “Does `full_clean()` replace database constraints?” **Answer:** No. It gives useful validation before saving; database constraints still protect stored data, including competing writes.

## Lesson 8 — Event lifecycle, agenda, and announcements

**Simple explanation.** An event follows allowed states. A draft is preparation; published is public; cancelled is a terminal state in this project. Agenda items must fit the event's time window. Announcements are messages attached to the event. Keeping these rules in models means the HTML and API can enforce the same final record rules.

Actual excerpt from `Event.clean` in [`events/models.py`](../events/models.py):

```python
        if not self.pk and self.status != self.Status.DRAFT:
            errors["status"] = "New events must start as drafts. Save the draft, then publish or cancel it."
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "End time must be after start time."
```

The same method checks that venue/category have the organization's owner, prevents changing the event's organization, limits status transitions, and blocks reschedules that strand agenda items. `AgendaItem.clean` requires its end after its start and the entire item inside its event. AgendaItem and Announcement cannot change their event after creation.

The useful creation order is Organization + Venue + EventCategory → Event Draft → agenda and announcement → publish. Read the event page to see schedule and messages. Update the child via its edit action. Delete using confirmation POST. A published event can only remain published or become cancelled; a cancelled one remains cancelled even if other details are edited.

**Analogy.** A school activity moves from proposal to approved notice to cancellation. A session on its program cannot start before the activity itself starts or finish after it ends.

**Important terms.** Lifecycle: allowed states over time. Choice field: one of defined values. Cross-field validation: checking fields together. Immutable relationship: a link that cannot change after creation. Terminal state: no reopening transition.

**Practice questions and answers.**

1. Can a new POST create a published event directly? **No, ordinary application/API writes require draft-first creation.**
2. Can you shorten an event around an existing agenda outside the new window? **No. Remove affected agenda items before rescheduling.**
3. Can an Announcement be reassigned to another event? **No. Its event is fixed after creation.**

**Small exercise.** Draw allowed status arrows: Draft → Published, Draft → Cancelled, Published → Cancelled. Add each state's self-loop. Explain why Published → Draft and Cancelled → Published are absent.

**Sample professor question.** “Is disabling the organization dropdown enough to keep an event's organization fixed?” **Answer:** No. Model/service validation also rejects a changed relationship, including API attempts.

## Lesson 9 — Registration, notes, and cancellation

**Simple explanation.** A Registration records one signed-in user's participation in one event. Creating a registration needs a future published event. Updating changes only the attendance note and is allowed while registration remains open. Cancellation removes the registration, even after the event starts or is cancelled. It does not change the Event status.

Actual identity assignment inside [`events/services.py`](../events/services.py):

```python
            if model is Registration:
                if not user.is_authenticated or (not creating and not (is_admin(user) or obj.student_id == user.pk)):
                    raise PermissionDenied("You can change only your own registration.")
                if creating:
                    obj.student = user
```

The unique pair constraint is declared in [`events/models.py`](../events/models.py):

```python
        constraints = [models.UniqueConstraint(fields=["event", "student"], name="one_registration_per_student_event")]
```

Website flow: `/events/<id>/register/` → `registration_create` → `RegistrationNoteForm` → `save_record` → `/registrations/<registration-id>/`. `registration_edit` handles the note; `registration_delete` renders confirmation and deletes only after POST. `registration_queryset` scopes personal records to the current student; admin mode requires a superuser. The roster view instead requires an organizer and their managed event.

**Analogy.** A reservation belongs to the person who made it and one activity. Correcting the note does not turn it into another person's reservation or move it to another event.

**Important terms.** Server-assigned identity, unique pair, duplicate, note update, cancellation, personal queryset, roster.

**Practice questions and answers.**

1. Who chooses `student` during creation? **The server uses the acting authenticated user, including when the actor is an administrator.**
2. Can an admin edit a note after the event starts? **No. The timing rule still applies. Authorized deletion remains possible.**
3. What prevents duplicate rows under racing requests? **Validation plus the database unique constraint; the service handles the expected duplicate database error.**

**Small exercise.** Create a synthetic future published event, register as your practice student, edit the note, read it in My registrations, then cancel. Explain why each step is Create, Update, Read, or Delete. Use only data you created for practice.

**Sample professor question.** “Why not trust a submitted student ID?” **Answer:** A caller could impersonate another user. The server assigns the authenticated identity instead.

## Lesson 10 — REST resources, JSON, and HTTP methods

**Simple explanation.** A website page is designed for a person. An API offers structured operations that programs can call. JSON is the text data format used by our API. It uses named fields and values, rather than page markup. HTTP methods tell the server whether the client wants to read, create, change, or remove a resource.

Actual router registrations in [`events/api/urls.py`](../events/api/urls.py):

```python
router.register("events", EventViewSet, basename="event")
router.register("agenda-items", AgendaItemViewSet, basename="agenda-item")
router.register("registrations", RegistrationViewSet, basename="registration")
router.register("announcements", AnnouncementViewSet, basename="announcement")
```

The preceding three entries register organizations, venues, and categories. `config/urls.py` mounts this router at `/api/`.

| Resource | Collection | Detail |
|---|---|---|
| Organization | `/api/organizations/` | `/api/organizations/<id>/` |
| Venue | `/api/venues/` | `/api/venues/<id>/` |
| EventCategory | `/api/categories/` | `/api/categories/<id>/` |
| Event | `/api/events/` | `/api/events/<id>/` |
| AgendaItem | `/api/agenda-items/` | `/api/agenda-items/<id>/` |
| Registration | `/api/registrations/` | `/api/registrations/<id>/` |
| Announcement | `/api/announcements/` | `/api/announcements/<id>/` |

GET collection lists rows; POST collection creates one. GET detail reads one; PUT detail supplies all required writable fields; PATCH detail updates selected fields; DELETE detail removes the record. Access and business rules determine whether the request is allowed. The API root is browsable at `/api/`; collections normally paginate 20 records using `count`, `next`, `previous`, and `results`. Search/category filtering exists on HTML discovery, not this API.

Representative JSON for a student's registration POST is `{"event": 42, "attendance_note": "I will attend."}`. Here 42 is a placeholder for an actual visible future published event ID. Output additionally contains the generated `id`, acting `student`, and `created_at`. Do not copy a placeholder ID as if it were guaranteed to exist.

**Analogy.** A restaurant's customer-facing menu is like HTML. Its structured order form for a delivery system is like an API: the fields have agreed names and meanings.

**Important terms.** API, resource, endpoint, JSON object, HTTP method, collection, detail, pagination, status code.

**Practice questions and answers.**

1. Does GET create a record? **No. Use authorized POST to the collection for creation.**
2. How do PUT and PATCH differ? **PUT requires the required writable fields; PATCH supplies selected changes. Both validate the final record.**
3. What do 201 and 204 mean? **201 means created. 204 means deleted successfully, with no response JSON body.**

**Small exercise.** Open `/api/` locally. Find each of the seven resource links. Read a list and one visible detail without submitting writes. Identify numeric IDs and paginated results.

**Sample professor question.** “Does exposing CRUD mean any user can perform every method?” **Answer:** No. Resource methods are subject to role, ownership, object visibility, validation, and CSRF checks.

## Lesson 11 — Serializers, API permissions, CSRF, and errors

**Simple explanation.** API input must be checked just like a browser form. A serializer describes allowed fields, converts submitted values, and formats output. A permission class checks allowed actions. A session cookie identifies the user; a CSRF token helps prevent another site from causing that logged-in browser to make an unwanted change.

Actual Registration serializer in [`events/api/serializers.py`](../events/api/serializers.py):

```python
class RegistrationSerializer(ResourceSerializer):
    student = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Registration
        fields = ("id", "event", "student", "attendance_note", "created_at")
        read_only_fields = ("created_at",)
        # The shared service validates uniqueness with the server-assigned student.
        validators = []
```

`ResourceSerializer` rejects unknown input fields and conflicting read-only identities. Its `create`/`update` call `save_record`. `OwnedSerializer.owner` is optional write-only input: normal organizers can assign only themselves, an admin can choose an eligible owner on creation, and ownership cannot change. Organization output removes `contact_email` for callers other than its owner/admin; `owner` is never output.

`ResourceViewSet` uses SessionAuthentication. `OrganizerWrites` permits safe reads and requires organizer access for writes; querysets further scope rows. Registration requires login; organizer roster reads are wider than registration write permission. The API maps validation failures to 400, protected deletion to 409, and temporary database contention to 503. Hidden/absent rows may return 404; permission or CSRF failures return 403. A status code explains a category of outcome, not every internal detail.

For Postman, follow [api.md](api.md): GET the login page, POST username/password and its CSRF token with retained cookies, then read the **rotated** current CSRF cookie and send `X-CSRFToken` for API writes. Keep host/port consistent. The browsable API supplies browser forms and session login. This project does not use bearer tokens.

**Analogy.** A clerk first checks the submitted form's allowed boxes, then verifies the person's authority. A stamped request token gives extra assurance that the submission came through the expected session flow.

**Important terms.** Serializer, read-only, write-only, validation error, SessionAuthentication, cookie, CSRF, scoped queryset.

**Practice questions and answers.**

1. Why is `student` read-only? **The client must not choose or change another person's identity; the service assigns the actor.**
2. Does `validators = []` remove all registration validation? **No. It disables serializer-level automatic validators here; the shared service/model and database enforce uniqueness with the assigned student.**
3. Why might a signed-in Postman write return 403? **The role may be insufficient, or CSRF/session cookies/token may be missing or inconsistent. Read the error; do not disable protections.**

**Small exercise.** Read `ResourceSerializer.to_internal_value`, `validate`, `RegistrationAccess`, and `RegistrationViewSet.get_queryset`. Explain which checks apply to a forged `student`, an unknown field, and another student's ID.

**Sample professor question.** “Why treat the browsable form's CSRF field specially?” **Answer:** SessionAuthentication checks that transport field. The serializer permits the HTML transport token without accepting arbitrary unknown JSON fields or bypassing CSRF.

## Lesson 12 — Saved coordinates, Leaflet, and OpenStreetMap

**Simple explanation.** Latitude and longitude describe a position on Earth. The Venue table stores them. Leaflet is browser JavaScript that turns those numbers into an interactive map and pin. OpenStreetMap tile images provide the background. A tile is one small image in the grid assembled as the user pans or zooms.

Actual map creation in [`static/js/event-map.js`](../static/js/event-map.js):

```javascript
    const map = window.L.map(container, { scrollWheelZoom: false }).setView([latitude, longitude], 16);
    const tiles = window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
```

The event view builds `map_data` from `event.venue`. The template transfers it using `{{ map_data|json_script:"event-map-data" }}`. The script parses that JSON, checks numeric ranges, creates a map/marker, and builds popup elements using `textContent`. Using text rather than arbitrary HTML prevents venue names/addresses being executed as markup in the popup.

On the venue form, `static/js/venue-map.js` accepts map clicks, marker dragging, or typed coordinates. The initial Philippines overview does not select a location. The form saves only when valid latitude and longitude are submitted. The server rejects nonfinite numbers and latitude outside −90..90 or longitude outside −180..180. If Leaflet or tiles fail, the page explains the fallback; address and coordinates remain available and forms still accept manual coordinate entry. There is no route planner, live GPS tracking, or automatic address geocoding in this code.

**Analogy.** Coordinates are a precise shelf location. Leaflet is the viewer that shows the shelf plan; the tile provider supplies the drawing behind it.

**Important terms.** Latitude, longitude, coordinates, Leaflet, OpenStreetMap, tile, marker, popup, JSON script, DOM text.

**Practice questions and answers.**

1. Does clicking the map immediately save SQLite data? **No. It fills form fields; submitting a valid form saves them.**
2. Where do the event pin's coordinates come from? **The saved Venue related to that Event.**
3. Why can the page still work when tiles fail? **Event data and registration are ordinary Django features; text location and typed coordinate fields remain.**

**Small exercise.** Trace Venue form → saved `Venue.latitude/longitude` → `event_detail.map_data` → `json_script` → `JSON.parse` → `L.marker`. Explain what runs in Python and what runs in the browser.

**Sample professor question.** “Are Leaflet and OpenStreetMap the same thing?” **Answer:** No. Leaflet displays/interacts with the map; OpenStreetMap provides credited map data and the tile service used here.

## Lesson 13 — Requesting the correct event-day weather

**Simple explanation.** CampusGather asks another server for a forecast because the local database does not calculate weather. It uses the saved venue position and the event's local date. Timezone matters: a UTC timestamp can fall on a different calendar date in the Philippines. The app therefore explicitly converts times using its configured timezone, Asia/Manila.

Actual date conversion from [`events/weather.py`](../events/weather.py):

```python
    event_timezone = timezone.get_default_timezone()
    target = timezone.localtime(event.starts_at, event_timezone).date()
    today = timezone.localtime(timezone.now(), event_timezone).date()
    offset = (target - today).days
```

The service accepts offsets **0 through 15 inclusive**. A past date returns `past`; offset 16 or greater returns `out_of_range`. Those cases skip network/cache access. Eligible dates then require valid saved coordinates. The request uses `https://api.open-meteo.com/v1/forecast`, `latitude`, `longitude`, configured `timezone`, `temperature_unit: "celsius"`, and identical ISO `start_date`/`end_date`. Its daily fields are `temperature_2m_max`, `temperature_2m_min`, `precipitation_probability_max`, and `weather_code`.

`requests.get(..., timeout=(2, 3))` supplies connect/read limits. It does not guarantee a precise five-second total. `raise_for_status()` checks HTTP failure, and `response.json()` reads structured data. No event title, student's name, password, or attendance note is sent as a weather parameter. This is a daily forecast for the date, not hour-specific weather for the event's exact start time.

**Analogy.** Asking a weather office for “the forecast at these coordinates on this date” is more precise than asking for today's weather or naming a room it does not know.

**Important terms.** External API, HTTP request, query parameter, timezone, UTC offset, ISO date, forecast horizon, daily aggregate, timeout.

**Practice questions and answers.**

1. Which date is requested? **The saved event start converted to `settings.TIME_ZONE`, not today's date as a substitute.**
2. Is day 15 eligible? Is day 16? **Day 15 is eligible; day 16 is outside this integration's window.**
3. Does the browser request weather directly? **No. Django's Python service uses `requests`; the returned result is rendered in HTML.**

**Small exercise.** In `forecast_for_event`, identify every early return before HTTP. Explain why past/far-future dates and invalid coordinates should not make a provider request.

**Sample professor question.** “What happens around UTC midnight?” **Answer:** The code converts both event time and current time to the configured timezone before calculating date difference, so the forecast uses the Philippine calendar date.

## Lesson 14 — Validating weather, caching, and honest failure states

**Simple explanation.** Receiving HTTP 200 does not prove the response contains useful weather. The parser must match the requested date, check arrays and required measurements, and avoid inventing missing values. A cache temporarily remembers a valid answer so repeated event visits do not always repeat an external request.

Actual optional-rain handling in [`events/weather.py`](../events/weather.py):

```python
    rain_values = daily.get("precipitation_probability_max")
    rain = None
    if rain_values is not None:
        if not isinstance(rain_values, list) or len(rain_values) != len(dates):
            return None
        rain = rain_values[index]
        if rain is not None and (not _finite_number(rain) or not 0 <= rain <= 100):
            return None
```

`None` means missing here; it is not zero percent. `_daily_forecast` also requires one matching date, aligned temperature/condition arrays, finite numeric values excluding booleans, minimum ≤ maximum, and a recognized weather condition code. Valid data returns a date, description, icon, Celsius range, and optional rain. A malformed supplied rain array/value still fails validation.

The cache key is `event-weather:v2:` plus a SHA-256 hash of the sorted request parameters. Date, coordinates, fields, timezone, and units therefore affect the key. A valid result, including `fetched_at`, is cached for **900 seconds**. Failures are not cached. The date/location checks happen before cache lookup, so a now-past event cannot reuse an old success. The current default cache is in memory per process; it is not permanent database storage.

| `state` | Meaning |
|---|---|
| `available` | Required validated forecast is present; rain may be absent. |
| `past` | Event's configured local date is before today. |
| `out_of_range` | Date is today +16 days or later. |
| `invalid_location` | Saved coordinates are missing, invalid, nonfinite, or out of range. |
| `temporarily_unavailable` | Request/HTTP/JSON/payload could not yield a usable forecast; `reason` distinguishes the failure. |

The template displays readable weather messages, source/licence, date, temperatures, condition, icon, optional rain, and fetch time. Icon decoration is hidden from assistive technology while the condition remains text. It does not stop event details or registration. Diagnostics log reason/date/status, not a private event title.

**Evidence to understand.** Live HTTP checks on 13 November 2026 returned 200 for saved events 1 and 2, and the old parser accepted the payloads. The historical screenshot failure was not reproduced. A separate optional-rain parser bug was confirmed and corrected. Do not say that fix proves the screenshot's cause. See the final status record for exact verification scope.

**Analogy.** Keep a checked weather bulletin on a desk for fifteen minutes, but do not reuse it for a changed date/location. A missing rain line does not mean a promise of no rain.

**Important terms.** Parser, required/optional field, null/None, cache, cache key, hash, expiry, diagnostic reason, graceful failure.

**Practice questions and answers.**

1. Can HTTP 200 still produce an unavailable result? **Yes. JSON can be malformed, have the wrong date, or lack required valid values.**
2. Does missing rain become `0%`? **No. It remains None and the page says rain probability is unavailable. Real zero is displayed as zero.**
3. Are failed requests cached for fifteen minutes? **No. Only validated successful forecasts are cached.**

**Small exercise.** Read `_daily_forecast`. List three essential failures and two optional-rain cases that preserve success. Then compare its output with the event template's `weather.available` branch.

**Sample professor question.** “How can you prove live weather works?” **Answer:** Record a real saved-event request, target date, HTTP outcome, and validated result separately from mocked tests. A screenshot or mock alone is not proof of current provider availability.

## Lesson 15 — Back links that preserve context safely

**Simple explanation.** A useful Back link needs a destination even when the page was opened directly. CampusGather builds a real link on the server. It may carry the page the user came from in `return_to`, but that input must be checked because a client can change it. Login continuation uses a separate `next` value.

Actual host/scheme guard in [`events/navigation.py`](../events/navigation.py):

```python
    if not url_has_allowed_host_and_scheme(candidate, {request.get_host()}, require_https=request.is_secure()):
        return ""
```

The rest of `safe_destination` rejects malformed/backslash/control-character paths, unknown routes, self-links, inaccessible objects, authentication/form/destructive destinations, and unpermitted query values. `_can_visit` applies the relevant role/object-read rules. `_list_query` preserves bounded `q`, `category`, and page values for appropriate list pages, while stripping nested navigation and unrelated parameters. Same-host absolute destinations become local path/query links.

`navigation_context` chooses validated explicit origin or a named parent. Event detail falls back to discovery; registration detail to My registrations; a management list to dashboard; edit/delete forms to an existing detail. `templates/base.html` includes the common near-top arrow and Back text. Admin and browsable API templates include their equivalent navigation. `return_field.html` carries context through HTML form POST, and save/delete redirects revalidate it. Successful deletion goes to a surviving list rather than the deleted detail. Discovery itself has no self-referential Back button.

**Analogy.** A campus sign can point back to the correct building, but it should not accept a stranger's instruction to send students to any address. If the visitor arrived through a direct gate, the sign uses a known main entrance.

**Important terms.** Destination, redirect, fallback, same host, safe route, query string, `return_to`, `next`, parent page.

Event-page edit/delete actions also carry `event_parent`, a numeric ID rather than a URL. `event_parent_id` checks organizer access and that the record really belongs to that event before choosing the Back/Cancel parent. The original list remains in `return_to`. Both values are checked again after form submission; a hidden input is still user-controlled input.

**Practice questions and answers.**

1. Why not only use `history.back()`? **A directly opened tab may have no useful previous page. Server-defined parent links still work.**
2. Is same-host validation alone enough? **No. A same-host URL can be a mutation/auth page, private object, self-link, or nonexistent destination.**
3. Why preserve only selected query fields? **They retain useful discovery/pagination context without nesting arbitrary destinations or unrelated input.**

**Small exercise.** Open an event through search/category filtering and inspect its Back link. Then open the same event directly in a new session/tab and compare the fallback. Read `navigation_context` to explain both results.

**Sample professor question.** “Does a safe Back link replace authorization on the destination?” **Answer:** No. Destination views still enforce access. Link validation supplies safe navigation, not permission to a resource.

## Lesson 16 — Tests, constraints, concurrency, and security evidence

**Simple explanation.** A test performs a small action and checks an expected result. Good regression tests reproduce a bug's important behavior so the bug is less likely to return. A mocked dependency replaces an external service with controlled responses. A live test instead contacts the real service. They answer different questions.

Actual regression test in [`events/tests/test_rules.py`](../events/tests/test_rules.py):

```python
    def test_duplicate_registration_is_validation_error(self):
        save_record(self.student, Registration, {"event": self.event})
        with self.assertRaises(ValidationError):
            save_record(self.student, Registration, {"event": self.event})
        self.assertEqual(Registration.objects.count(), 1)
```

The first call creates the registration. The second must report ValidationError. The last assertion checks that only one row exists. `TestCase` supplies isolated test data; Django creates a separate test database. `SimpleTestCase` weather tests use fake event objects and patched HTTP/clock/cache. `TransactionTestCase` concurrency tests exercise competing writes with real transactions in their test environment.

| Test area | Source and purpose |
|---|---|
| Accounts | `accounts/tests.py`: signup cannot promote a user, safe continuation, login/POST logout, CSRF. |
| HTML | `events/tests/test_website.py`: six generic CRUD resources, registration CRUD/privacy, search, admin/roles, validation/deletion. |
| REST | `events/tests/test_api.py`: all seven CRUD resources, field/identity checks, session/CSRF, drafts/registration privacy, errors. |
| Rules/concurrency | `test_rules.py`, `test_concurrency.py`: duplicates, statuses, schedule/coordinate rules, competing registrations/reschedules. |
| Seed | `test_seed.py`: password requirements and preservation of existing data/accounts/cancellations. |
| Weather | `test_weather.py`: correct dates/coordinates/parameters, success cache, optional rain, states, malformed data/network failures. |
| Navigation | `test_navigation.py`: safe destinations, parent fallbacks, filter/page preservation, form/save/delete context, admin/API HTML. |

SQLite has no row-level `select_for_update` locking. This project uses `transaction_mode: "IMMEDIATE"`, a ten-second database timeout, short atomic writes, reloaded related rows, and constraints. It can return a friendly retry response under contention. That is evidence of deliberate behavior, not proof of unlimited scale.

Security mechanisms include Django password hashing/validators, sessions, CSRF, escaped templates, ORM queries, role/ownership checks, safe popup text, safe Back destinations, immutable identities, and database constraints. Native admin domain models are read-only to avoid bypassing the custom write path. Production cookies become secure when DEBUG is false; production setup still needs separate deployment verification. Do not weaken authentication or expose secrets to make a demonstration pass.

**Current evidence rule.** The original measured baseline was 65 passing tests. Added regressions change the total; read the latest dated table in [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md) for final counts, failures, live checks, browser checks, and remaining manual checks. Do not claim this guide ran a new test suite or the Postman desktop application.

**Analogy.** A fire drill checks a known route under planned conditions. It provides evidence about that route, not a guarantee about every possible emergency or every future day.

**Important terms.** Test, assertion, regression, mock, fixture, isolated database, constraint, race/competing write, live check, coverage limitation.

**Practice questions and answers.**

1. Does a mocked weather pass prove Open-Meteo is online now? **No. It proves the tested local behavior under a controlled response.**
2. Why check the database count after duplicate creation? **The test must verify stored state, not only that an exception occurred.**
3. Does a passing suite establish full mobile/accessibility/production behavior? **No. Browser/device checks, assistive technology, network behavior, and load need their own evidence.**

**Small exercise.** Explain the duplicate test above line by line. Find one navigation test and one weather test that would fail if their corresponding fix were removed. Describe the tested boundary without changing the code.

**Sample professor question.** “How do you know your changes did not break the original system?” **Answer:** Compare the recorded baseline with the final complete suite and focused regressions, then state which browser/live/manual checks were actually performed and what remains unverified.

## Lesson 17 — Running, migrating, seeding, and explaining honestly

**Simple explanation.** The project needs the correct Python environment, installed libraries, database tables, and local accounts. A virtual environment keeps this project's libraries separate. A migration is a versioned instruction for database structure. A seed command adds synthetic practice examples; it is not a database reset. Configuration and secrets belong in private local settings.

Actual seed preservation code from [`events/management/commands/seed_demo.py`](../events/management/commands/seed_demo.py):

```python
            obj, was_created = model.objects.get_or_create(**lookup, defaults=defaults)
```

This helper creates a matching example only if it is missing; defaults do not overwrite an existing match. The surrounding code validates new rows and rolls back ambiguous/invalid seeding. Existing users keep passwords, profile data, and roles. New users require a chosen password that passes Django validation. Only a newly created `demo_organizer` receives Organizers automatically. Existing students are not automatically enrolled and cancelled registrations are not recreated. No admin is seeded. Existing event dates remain fixed and eventually become past dates.

Read the full secure first-time setup in [README.md](../README.md). These are **commands for your own local rehearsal**, not claims of additional execution by this guide:

```powershell
Set-Location -LiteralPath 'C:\Users\brene\Desktop\CampusGather'
.\.venv\Scripts\Activate.ps1
python --version
python manage.py check
python manage.py migrate
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
python manage.py runserver
```

Activation changes the terminal's selected Python. If activation is unavailable, use `.\.venv\Scripts\python.exe` in place of `python`; no security-policy change is needed. `check` checks Django configuration. `migrate` applies existing schema instructions. `makemigrations --check --dry-run` checks for model/schema drift without generating migration files. `test` runs the isolated suite. `runserver` starts local development serving; Ctrl+C stops it. Open `http://127.0.0.1:8000/`, or the actual port displayed.

For a new environment, the README explains `py -3.13 -m venv .venv` and `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`: create the environment, then install the pinned dependencies through its Python. Reuse a working environment. Preserve an existing `.env` and stable private secret key. Do not put passwords into published scripts.

Use `.\.venv\Scripts\python.exe manage.py createsuperuser` to create your own administrator. Use `manage.py changepassword demo_student` or the selected username if you explicitly need to set that account's local password. The README's secure prompt supplies `CAMPUSGATHER_DEMO_PASSWORD` to `seed_demo` without printing it; it affects new users only. Once users already exist, `seed_demo` may run without a new password, and it still preserves old schedules.

| File/folder | Actual job |
|---|---|
| `manage.py` | Entry point for Django management commands. |
| `config/settings.py`, `config/urls.py` | Environment, apps, database, middleware, timezone, security, and top-level routes. |
| `config/asgi.py`, `config/wsgi.py` | Server integration entry points. |
| `accounts/` | Signup, login/logout routing, organizer role assignment, account tests; no custom profile model. |
| `events/models.py`, `migrations/` | Seven table definitions/validation and versioned schema history. |
| `events/views.py`, `forms.py`, `urls.py`, `resources.py` | Browser workflows, allowed input, routes, and six-resource specifications. |
| `events/services.py`, `permissions.py` | Shared writes/deletes, role checks, ownership, and visible/managed records. |
| `events/api/` | Serializers, viewsets, API permissions/router. |
| `events/weather.py` | Existing forecast request, validation, states, cache. |
| `events/navigation.py`, `context_processors.py` | Safe Back destinations and values shared with templates. |
| `templates/`, `static/` | HTML pages/shared includes, CSS, local icon, map JavaScript; admin/API template overrides. |
| `events/tests/`, `accounts/tests.py` | Automated behavior checks. |
| `events/management/commands/seed_demo.py` | Repeat-safe synthetic demonstration data. |
| `README.md`, `IMPLEMENTATION_STATUS.md`, `docs/` | Setup, actual evidence, and explanation. |

**Analogy.** A virtual environment is a project's own toolbox. Migrations are the approved building plans. Seeding places practice furniture in the finished rooms without replacing furniture people already use.

**Important terms.** Virtual environment, dependency pin, configuration, migration, schema, seed, local development server, secret, evidence.

**Practice questions and answers.**

1. Does running the seed with a different password reset existing demo users? **No. Use an explicit password-change command for an account you are authorized to manage.**
2. Does migration drift checking apply database changes? **No. `makemigrations --check --dry-run` reports whether model changes need migrations. `migrate` applies migrations.**
3. What should you say about AI assistance? **State that you used help, explain the code you actually studied, and admit what still needs study. Do not claim unsupported authorship or understanding.**

**Small exercise.** Rehearse explaining a student registration from request to saved row, then map coordinates from saved row to marker, then weather from event date to cache/result. Check your explanation against source. Use the quick sheet only after trying from memory.

**Sample professor question.** “What would you verify before demonstrating on a groupmate's computer?” **Answer:** Correct Python/environment, dependencies, migrations, local accounts/roles, a fresh future event, core registration flow, actual test results, and separate live map/weather behavior. A result on this computer is not proof of theirs.

## Self-check before the defense

You are ready to present a feature when you can point to its URL, view, model, input validation, access rule, and visible result. For registration also explain its unique pair and cancellation rule. For weather separate local parser tests from live provider evidence. For maps distinguish saved coordinates, Leaflet, and OSM tiles. For navigation explain why a parent fallback is necessary and why a submitted destination is untrusted.

A useful truthful sentence is: “I built and improved this with AI assistance. I can trace this part in the code, and I am still studying that other part.” Follow it by explaining a real request and rule rather than reciting a technology list.
