from .models import Organization, Venue, EventCategory, Event, AgendaItem, Announcement

RESOURCES = {
    "organizations": {"model": Organization, "singular": "organization", "label": "Organizations", "description": "The campus groups behind your events."},
    "venues": {"model": Venue, "singular": "venue", "label": "Venues", "description": "Places to meet, with a saved map location."},
    "categories": {"model": EventCategory, "singular": "category", "label": "Categories", "description": "Help students discover the right event."},
    "events": {"model": Event, "singular": "event", "label": "Events", "description": "Plan, publish and manage your campus events."},
    "agenda-items": {"model": AgendaItem, "singular": "agenda item", "label": "Agenda items", "description": "Build a schedule inside each event's times."},
    "announcements": {"model": Announcement, "singular": "announcement", "label": "Announcements", "description": "Keep participants up to date."},
}
