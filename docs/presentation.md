# Presentation and question practice

Use the application and code as evidence. Explain assistance accurately: describe any scaffolding, debugging, or documentation help the group used, then identify what each member implemented, checked, and can explain. Do not present unperformed checks or unpublished hosting as completed work.

## Suggested eight-slide outline

| Slide | Main point | Evidence to show |
|---|---|---|
| 1. Problem and users | Campus activity details and signups need one place | Visitor/student/organizer/admin journey |
| 2. Scope | Discovery, registrations, organizer management, API, maps, weather | Working navigation; deferred work clearly labelled |
| 3. Seven application tables | Records model events and participation | ER diagram; User counted separately |
| 4. Permissions | Ownership and registration privacy are enforced on the server | Two-session privacy check and roles page |
| 5. CRUD and validation | Valid writes preserve data relationships | Form error, note edit, protected deletion |
| 6. RESTful API | Seven resources expose JSON CRUD with matching rules | `/api/`, one POST/PATCH/DELETE, session+CSRF |
| 7. External integrations | Saved venue map and correct-event-date forecast | Marker/attribution, forecast date, unavailable state |
| 8. Verification and group work | Claims follow observed checks | Actual status notes, focused tests, meaningful Git review |

Have one member operate the browser and another explain the code path. Keep a synthetic practice event ready for publishing/cancelling. A cancelled event cannot be reopened, so prepare a fresh draft for the next presentation. Follow [demo.md](demo.md) for the full sequence.

## Short code explanation

A request reaches a URL in `config/urls.py`, then an account, HTML, or API view. Read queries are filtered by visibility and ownership. Forms and serializers accept explicit fields. Writes enter `save_record()` or `delete_record()`, which enforce permissions and use short atomic transactions. Models validate the complete record; database constraints provide additional integrity. Django templates render HTML, while DRF serializes JSON. Event detail fetches weather outside write transactions. Browser JavaScript draws the map from safely serialized saved coordinates.

## Professor questions and example answers

1. **What are the seven tables?** Organization, Venue, EventCategory, Event, AgendaItem, Registration, and Announcement. Django authentication tables are additional framework tables.
2. **Why is Registration a separate table?** It connects a student to an event and holds their note and creation time. Many students can join many events through these rows.
3. **What prevents duplicate signups?** A unique database constraint on event/student and validation through the shared write service, including handling a concurrent duplicate as a friendly error.
4. **Where is event ownership?** It derives from Organization.owner. Venue/category must share that owner. The administrator can manage records without taking ownership.
5. **Can signup create an organizer?** No. Signup creates an ordinary student. An administrator assigns the `Organizers` group.
6. **Why check permissions if a button is hidden?** A user can send a direct request. The server scopes records and checks every write independently of the interface.
7. **Can an organizer edit the roster's students?** They can read their own event's roster. Another student's note/deletion remains restricted to that student or an administrator.
8. **What does cancellation do?** It keeps the event and registrations, closes registration/note changes, and permits authorized registration deletion. Cancelled is terminal.
9. **Why protect deletion?** A venue/category/organization in use and an event with registrations should not silently erase important relationships. Unregistered event deletion cascades its agenda and announcements.
10. **What differs between PUT and PATCH?** PUT supplies required writable fields for the record; PATCH supplies selected changes. Both validate the resulting complete record and retain immutable identities.
11. **How is the API authenticated?** Django session cookies through DRF SessionAuthentication. Authenticated unsafe requests need CSRF protection. Login rotates the CSRF token.
12. **Does the API expose everything in a model?** No. Serializers list allowed fields. Owner is write-only, contact email is private, and registration reads are scoped.
13. **Which external API is used?** Open-Meteo supplies daily weather for saved venue coordinates and the event's Asia/Manila start date. Leaflet draws a map using OpenStreetMap tiles in the browser.
14. **What happens for an event twenty days away?** A readable forecast-unavailable state appears. The weather client checks the local date before cache/network work and supports offsets zero through fifteen days.
15. **Why validate the returned date?** A successful HTTP status alone does not prove the forecast belongs to the event. The client requires the matching daily date and valid values.
16. **What if weather or map tiles fail?** Event content, saved address/coordinates, and registration remain available. No automatic weather cancellation occurs.
17. **Why cache weather?** A validated success can be reused for fifteen minutes, reducing repeated requests. Coordinates and the event date are part of its cache identity.
18. **Why SQLite?** It keeps this classroom application easy to run. Short IMMEDIATE write transactions serialize checks and changes. Higher-volume deployment would require a separate database/concurrency evaluation.
19. **How did you test it?** Name only checks recorded in the delivery status: rules, requests/API, CSRF, transaction scenarios, weather payload/cache failures, seed repeatability, and any observed browser checks. Mocked weather is separate from live connectivity.
20. **Is it deployed, a PWA, or Dockerized?** Those are not implemented in this version. They require confirmed course requirements and their own verification.

## Course coverage

| Topic | Demonstration | Status of scope |
|---|---|---|
| Models and relational design | Seven models, foreign keys, uniqueness, deletion policy | Core |
| HTML CRUD, forms, templates | Six organizer resources plus registration pages | Core |
| Authentication and authorization | Signup, session login, group grant/revoke, ownership | Core support |
| RESTful API | Seven DRF resources, JSON, HTTP methods/statuses | Core |
| External API | Correct-event-date weather and failure handling | Core |
| Leaflet/OpenStreetMap | Venue selection and event marker with attribution/fallback | Core |
| Testing | Focused rules, requests, transactions, mocked provider and seed checks | Core; report actual runs |
| Git and collaboration | Source/migrations, small branches, meaningful commits, peer review | Verify repository sharing separately |
| PWA, Docker, hosting, OAuth, AI | Possible later work | Not implemented; confirm rubric first |

Bring the actual course rubric if more coverage is requested. Avoid adding an optional feature solely to claim a topic without a working demonstration and appropriate checks.
