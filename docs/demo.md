# Classroom demo and manual checks

Use only synthetic accounts and data. Follow the README setup, create an administrator, and run `seed_demo` with a locally chosen strong password. Keep two browser profiles/private windows available to separate sessions. The seed preserves matching examples on rerun, so inspect the dates and permissions before presenting.

## Suggested ten-minute demonstration

1. **Visitor, one minute.** Open `/`. Search for `Campus` and try a category filter. Open “Demo: Campus Discovery Workshop.” Point out the organization, time, status, venue, schedule, announcement, and coordinates. The draft event should be absent. Open its known URL as a visitor and confirm it is hidden.
2. **Map and weather, one minute.** Show the event marker and visible OpenStreetMap attribution. Compare the forecast's date with the event's Manila start date; show Celsius range, rain probability, description, source, and fetch time if available. Open “Demo: Future Research Showcase” to show the unavailable state beyond the forecast horizon. Provider unavailability is a valid visible state, but does not prove a successful live API call.
3. **Student, two minutes.** Sign up a new ordinary practice student, or sign in as a demo student and first cancel their existing workshop registration. Register for the future published workshop, view My registrations, edit the attendance note, and show its detail. Submit a second API registration for the same event to demonstrate the friendly duplicate error and one stored row. The HTML Register action redirects an already registered user to their existing registration.
4. **Privacy, one minute.** In the second session sign in as `demo_student2`. A direct URL for the first student's registration must return not found. A student's organizer dashboard must be denied. Show that the student cannot submit an organizer role during signup.
5. **Organizer, two minutes.** Sign in as `demo_organizer`. Open the dashboard and each catalog list. Create a small practice category, venue, organization, draft event, agenda item, and announcement; read, edit, and delete an unused example through its application pages. Keep event agenda times within the event window. Publish the draft, show its roster, then cancel it. A cancelled event stays visible, keeps its registrations, and refuses new registrations/note edits. Its registered student can still cancel their registration.
6. **Protection and administrator, one minute.** Try deleting a seeded event with registrations; show the readable conflict and retained data. Sign in as administrator, open `/manage/registrations/`, and show all-registration management. Demonstrate grant/revoke at `/accounts/roles/`; restoring a role does not recreate or delete its records.
7. **REST API, two minutes.** Open `/api/` and show all seven collections. Follow [API examples](api.md) with session cookies and CSRF. Demonstrate one creation, PATCH, successful DELETE of an unused record, duplicate validation, and protected deletion. Explain that forms and API writes call the same service.

To show all seven CRUD resources without relying on Django Admin, use the six organizer resource lists under `/manage/` and the registration pages under `/registrations/`. The administrator registration pages are an additional application flow. A successful roster read is not permission to edit another student's registration.

## Browser verification worksheet

Record browser, date, result, and any limitation in `IMPLEMENTATION_STATUS.md` or your group's test notes. These are checks to perform, not assertions that they already passed.

| Check | Expected result |
|---|---|
| Keyboard-only login, signup, search, forms, registration, confirmation | Controls have visible focus; labels/errors are understandable; actions can be reached without a mouse |
| Narrow viewport around 390 px | Navigation, cards, forms, tables, map, and buttons remain usable without clipped essential content |
| Invalid coordinates; end before start; agenda outside event | Readable errors; original valid record retained |
| Organizer A tries organizer B's edit/delete URL | Denied; no cross-owner change |
| Student A tries Student B's registration URL | Hidden/denied; no note or student data exposed |
| Visitor requests draft event and its child API URLs | Hidden; no draft data exposed |
| Cancel event with a registration | Registration remains readable/deletable; new registration and note edit are refused |
| Delete referenced venue/category/organization or registered event | Conflict message; related rows retained |
| Block Leaflet CDN or tile requests in browser developer tools, then reload | Address/coordinates remain readable; typed venue coordinates and other forms still work |
| Enter venue coordinates by keyboard | Save succeeds with valid values, and edit/detail displays the saved location |
| Map popup with punctuation/HTML-like title | Text displayed safely; no script execution |
| Open a near-future event with network available | Matching-date live forecast or a readable provider error; record which occurred |
| Open past or more-than-15-day event | Unavailable state; never show today's weather as a future event's forecast |
| Omit CSRF from a logged-in API write | 403; repeat with the current token and permitted data to succeed |

An event-date forecast may be cached for fifteen minutes. Automated weather tests mock malformed payloads, missing dates, timeouts, and cache behavior. Browser blocking of map requests does not simulate the server's outbound weather connection; report these checks separately. Do not change machine networking or application protection to stage a failure.

## Resetting a practice run

The seed is additive and preserves matching rows; it does not reset edits or move old dates. Cancel a student's registration from their pages, then register again while the event is future and published. Create a fresh draft to repeat a publish/cancel demonstration because cancelled events cannot reopen. Remove unused practice records through their authorized confirmation pages. Do not delete `db.sqlite3` or other users' data merely to refresh the demonstration.
