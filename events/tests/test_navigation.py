from datetime import timedelta
from html import escape
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from events.models import AgendaItem, Announcement, Event, EventCategory, Organization, Registration, Venue


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class NavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.student = users.objects.create_user("nav-student", password="test-password")
        cls.owner = users.objects.create_user("nav-owner", password="test-password")
        cls.other = users.objects.create_user("nav-other", password="test-password")
        cls.staff = users.objects.create_user("nav-staff", password="test-password", is_staff=True)
        cls.admin = users.objects.create_superuser("nav-admin", "admin@example.invalid", "test-password")
        group = Group.objects.create(name="Organizers")
        cls.owner.groups.add(group)
        cls.other.groups.add(group)
        cls.org = Organization.objects.create(name="Navigation Club", owner=cls.owner)
        cls.venue = Venue.objects.create(name="Navigation Hall", address="Campus", latitude=9.7, longitude=118.7, owner=cls.owner)
        cls.category = EventCategory.objects.create(name="Navigation Workshop", owner=cls.owner)
        start = timezone.now() + timedelta(days=2)
        cls.event = Event.objects.create(title="Navigation event", description="Navigation & campus", organization=cls.org, venue=cls.venue, category=cls.category, starts_at=start, ends_at=start + timedelta(hours=2), status="published")
        cls.registration = Registration.objects.create(event=cls.event, student=cls.student)

    def setUp(self):
        weather = patch("events.weather.forecast_for_event", return_value={"available": False, "message": "Weather unavailable"})
        weather.start()
        self.addCleanup(weather.stop)

    def assert_back(self, response, expected):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], expected)
        self.assertContains(response, 'data-back-navigation', count=1)
        self.assertContains(response, 'href="' + escape(expected, quote=True) + '"')
        self.assertContains(response, '<span aria-hidden="true">←</span> Back')

    def test_discovery_links_restore_encoded_filter_page_and_strip_nested_context(self):
        origin = "/?" + urlencode({"q": "Navigation & campus", "category": self.category.pk, "page": 2})
        listing = self.client.get(origin)
        self.assertNotContains(listing, "data-back-navigation")
        self.assertContains(listing, "return_to=" + escape(urlencode({"return_to": origin}).split("=", 1)[1]))
        detail = reverse("event-detail", args=[self.event.pk])
        self.assert_back(self.client.get(detail, {"return_to": origin + "&return_to=https://evil.invalid/&other=discard"}), origin)
        self.assert_back(self.client.get(detail), "/")

    def test_unsafe_unknown_and_mutation_destinations_fall_back(self):
        detail = reverse("event-detail", args=[self.event.pk])
        unsafe = ["https://evil.invalid/", "//evil.invalid/", "\\\\evil.invalid/", "/\\evil.invalid/", "javascript:alert(1)", "/\n/evil.invalid/", "https://[invalid", "/does-not-exist/", detail, reverse("logout"), reverse("login"), reverse("signup"), reverse("registration-create", args=[self.event.pk]), reverse("registration-delete", args=[self.registration.pk]), reverse("resource-delete", args=["events", self.event.pk]), "/%2f%2fevil.invalid/", "/%5cevil.invalid/"]
        for destination in unsafe:
            with self.subTest(destination=destination):
                self.assert_back(self.client.get(detail, {"return_to": destination}), "/")

    def test_same_host_absolute_url_is_local_and_https_cannot_downgrade(self):
        detail = reverse("event-detail", args=[self.event.pk])
        self.assert_back(self.client.get(detail, {"return_to": "http://testserver/?q=campus#discard"}), "/?q=campus")
        self.assert_back(self.client.get(detail, {"return_to": "http://testserver/?q=campus"}, secure=True), "/")
        self.assert_back(self.client.get(detail, {"return_to": "https://testserver/?q=campus"}, secure=True), "/?q=campus")

    def test_private_deleted_and_cross_role_destinations_are_rejected(self):
        self.client.force_login(self.student)
        detail = reverse("event-detail", args=[self.event.pk])
        other_registration = Registration.objects.create(event=self.event, student=self.other)
        candidates = [reverse("dashboard"), reverse("roles"), reverse("admin-registration-list"), reverse("resource-list", args=["venues"]), reverse("registration-detail", args=[other_registration.pk]), reverse("registration-detail", args=[999999]), reverse("admin:index")]
        for destination in candidates:
            with self.subTest(destination=destination):
                self.assert_back(self.client.get(detail, {"return_to": destination}), "/")
        self.client.force_login(self.other)
        self.assert_back(self.client.get(detail, {"return_to": reverse("resource-detail", args=["organizations", self.org.pk])}), "/")
        self.client.force_login(self.staff)
        self.assert_back(self.client.get(detail, {"return_to": reverse("dashboard")}), "/")

    def test_organizer_edit_invalid_post_save_preserves_list_origin(self):
        self.client.force_login(self.owner)
        origin = reverse("resource-list", args=["organizations"]) + "?page=2"
        detail = reverse("resource-detail", args=["organizations", self.org.pk])
        edit = reverse("resource-update", args=["organizations", self.org.pk])
        detail_with_origin = detail + "?" + urlencode({"return_to": origin})
        self.assert_back(self.client.get(detail, {"return_to": origin}), origin)
        self.assert_back(self.client.get(edit, {"return_to": origin}), detail_with_origin)
        invalid = self.client.post(edit, {"name": "", "return_to": origin})
        self.assert_back(invalid, detail_with_origin)
        self.assertContains(invalid, 'name="return_to" value="' + escape(origin, quote=True) + '"')
        saved = self.client.post(edit, {"name": self.org.name, "description": "Updated", "return_to": origin})
        self.assertRedirects(saved, detail_with_origin, fetch_redirect_response=False)
        self.assert_back(self.client.get(saved.url), origin)
        self.assertRedirects(self.client.post(edit, {"name": self.org.name, "return_to": "https://evil.invalid/"}), detail, fetch_redirect_response=False)

    def test_delete_back_is_live_detail_and_success_uses_surviving_page(self):
        self.client.force_login(self.owner)
        child = Announcement.objects.create(event=self.event, title="Navigation notice", body="Hello")
        origin = reverse("resource-list", args=["announcements"]) + "?page=2"
        detail = reverse("resource-detail", args=["announcements", child.pk])
        delete = reverse("resource-delete", args=["announcements", child.pk])
        self.assert_back(self.client.get(delete, {"return_to": origin}), detail + "?" + urlencode({"return_to": origin}))
        self.assertRedirects(self.client.post(delete, {"return_to": origin}), origin, fetch_redirect_response=False)
        self.assertFalse(Announcement.objects.filter(pk=child.pk).exists())
        protected = self.client.post(reverse("resource-delete", args=["events", self.event.pk]), {"return_to": reverse("resource-list", args=["events"]) + "?page=2"})
        self.assertEqual(protected.status_code, 409)
        self.assertEqual(urlsplit(protected.context["back_url"]).path, reverse("resource-detail", args=["events", self.event.pk]))

    def test_registration_edit_cancel_preserves_page_and_revalidates_post(self):
        self.client.force_login(self.student)
        origin = reverse("registration-list") + "?page=2"
        detail = reverse("registration-detail", args=[self.registration.pk])
        edit = reverse("registration-edit", args=[self.registration.pk])
        self.assert_back(self.client.get(edit, {"return_to": origin}), detail + "?" + urlencode({"return_to": origin}))
        saved = self.client.post(edit, {"attendance_note": "Arriving early", "return_to": origin})
        self.assertEqual(parse_qs(urlsplit(saved.url).query), {"return_to": [origin]})
        self.assert_back(self.client.get(saved.url), origin)
        delete = reverse("registration-delete", args=[self.registration.pk])
        self.assert_back(self.client.get(delete, {"return_to": origin}), detail + "?" + urlencode({"return_to": origin}))
        self.assertRedirects(self.client.post(delete, {"return_to": detail}), reverse("registration-list"), fetch_redirect_response=False)

    def test_direct_entry_role_parent_matrix(self):
        self.client.force_login(self.owner)
        for resource, pk in [("organizations", self.org.pk), ("venues", self.venue.pk), ("categories", self.category.pk), ("events", self.event.pk)]:
            for route, expected in [("resource-list", reverse("dashboard")), ("resource-create", reverse("resource-list", args=[resource])), ("resource-detail", reverse("resource-list", args=[resource])), ("resource-update", reverse("resource-detail", args=[resource, pk])), ("resource-delete", reverse("resource-detail", args=[resource, pk]))]:
                args = [resource] if route in {"resource-list", "resource-create"} else [resource, pk]
                with self.subTest(route=route, resource=resource):
                    self.assert_back(self.client.get(reverse(route, args=args)), expected)
        self.assert_back(self.client.get(reverse("dashboard")), "/")
        self.assert_back(self.client.get(reverse("roster", args=[self.event.pk])), reverse("event-detail", args=[self.event.pk]))
        self.client.force_login(self.student)
        self.assert_back(self.client.get(reverse("registration-list")), "/")
        self.assert_back(self.client.get(reverse("registration-detail", args=[self.registration.pk])), reverse("registration-list"))
        self.client.force_login(self.admin)
        self.assert_back(self.client.get(reverse("roles")), reverse("dashboard"))
        self.assert_back(self.client.get(reverse("admin-registration-list")), reverse("dashboard"))
        self.assert_back(self.client.get(reverse("admin-registration-detail", args=[self.registration.pk])), reverse("admin-registration-list"))

    def test_account_admin_and_api_html_have_one_back_without_changing_json(self):
        for route in ["login", "signup", "rest_framework:login"]:
            with self.subTest(route=route):
                self.assert_back(self.client.get(reverse(route)), "/")
        self.client.force_login(self.admin)
        self.assert_back(self.client.get(reverse("admin:index")), reverse("dashboard"))
        self.assert_back(self.client.get(reverse("admin:auth_user_changelist")), reverse("admin:index"))
        self.assert_back(self.client.get(reverse("admin:auth_user_change", args=[self.student.pk])), reverse("admin:auth_user_changelist"))
        root = reverse("api:api-root")
        self.assert_back(self.client.get(root, HTTP_ACCEPT="text/html"), "/")
        listing = reverse("api:event-list")
        self.assert_back(self.client.get(listing, HTTP_ACCEPT="text/html"), root)
        self.assert_back(self.client.get(reverse("api:event-detail", args=[self.event.pk]), HTTP_ACCEPT="text/html"), listing)
        response = self.client.get(reverse("api:event-detail", args=[self.event.pk]), {"return_to": "/?q=campus"}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("return_to", response.json())
        self.assertNotIn("back_url", response.json())
        self.assertNotIn("event_parent", response.json())

    def test_available_weather_handles_missing_rain_zero_and_attribution(self):
        detail = reverse("event-detail", args=[self.event.pk])
        result = {"available": True, "state": "available", "date": "2026-11-15", "description": "Clear sky", "icon": "☀", "temp_min": 24, "temp_max": 30, "rain_probability": None, "fetched_at": "Now"}
        with patch("events.weather.forecast_for_event", return_value=result):
            response = self.client.get(detail)
            self.assertContains(response, 'aria-hidden="true">☀</span>')
            self.assertContains(response, "Rain probability is unavailable")
            self.assertNotContains(response, "None%")
            self.assertContains(response, "https://creativecommons.org/licenses/by/4.0/")
            self.assertContains(response, "Daily values and icons formatted by CampusGather")
        result["rain_probability"] = 0
        with patch("events.weather.forecast_for_event", return_value=result):
            self.assertContains(self.client.get(detail), "0% chance of rain")
        for state in ["past", "out_of_range", "invalid_location", "temporarily_unavailable"]:
            with patch("events.weather.forecast_for_event", return_value={"available": False, "state": state, "message": state}):
                response = self.client.get(detail)
                self.assertContains(response, state)
                self.assertContains(response, "https://creativecommons.org/licenses/by/4.0/")
                self.assertContains(response, 'id="event-map"')

    def test_event_child_pages_and_auth_links_retain_event_ancestry(self):
        origin = "/?q=campus&page=2"
        detail = reverse("event-detail", args=[self.event.pk])
        parent = detail + "?" + urlencode({"return_to": origin})
        self.client.force_login(self.owner)
        self.assert_back(self.client.get(reverse("roster", args=[self.event.pk]), {"return_to": origin}), parent)
        for resource in ["agenda-items", "announcements"]:
            self.assert_back(self.client.get(reverse("resource-create", args=[resource]), {"event": self.event.pk, "return_to": origin}), parent)
        self.client.logout()
        response = self.client.get(detail, {"return_to": origin})
        next_url = reverse("registration-create", args=[self.event.pk]) + "?" + urlencode({"return_to": origin})
        for route in ["login", "signup"]:
            url = reverse(route) + "?next=" + quote(next_url, safe="/") + "&" + urlencode({"return_to": detail})
            self.assertContains(response, 'href="' + escape(url, quote=True) + '"')
            self.assert_back(self.client.get(url), detail)

    def test_event_actions_preserve_immediate_parent_and_original_filter(self):
        self.client.force_login(self.owner)
        origin = "/?q=campus&page=2"
        parent = reverse("event-detail", args=[self.event.pk])
        parent_with_origin = parent + "?" + urlencode({"return_to": origin})
        announcement = Announcement.objects.create(event=self.event, title="Event action", body="Notice")
        agenda = AgendaItem.objects.create(event=self.event, title="Schedule", starts_at=self.event.starts_at, ends_at=self.event.ends_at)
        response = self.client.get(parent, {"return_to": origin})
        self.assertContains(response, "event_parent=" + str(self.event.pk))
        for resource, record in [("events", self.event), ("agenda-items", agenda), ("announcements", announcement)]:
            for route in ["resource-update", "resource-delete"]:
                with self.subTest(resource=resource, route=route):
                    response = self.client.get(reverse(route, args=[resource, record.pk]), {"return_to": origin, "event_parent": self.event.pk})
                    self.assert_back(response, parent_with_origin)
                    label = "Cancel" if route == "resource-update" else "Keep " + {"events": "event", "agenda-items": "agenda item", "announcements": "announcement"}[resource]
                    self.assertContains(response, 'href="' + escape(parent_with_origin, quote=True) + '">' + label + '</a>')
        edit = reverse("resource-update", args=["announcements", announcement.pk])
        payload = {"event": self.event.pk, "title": "", "body": "Edited", "return_to": origin, "event_parent": self.event.pk}
        self.assert_back(self.client.post(edit, payload), parent_with_origin)
        payload["title"] = announcement.title
        saved = self.client.post(edit, payload)
        self.assertEqual(saved.status_code, 302)
        self.assert_back(self.client.get(saved.url), parent_with_origin)
        fallback = reverse("resource-detail", args=["announcements", announcement.pk]) + "?" + urlencode({"return_to": origin})
        foreign_org = Organization.objects.create(name="Foreign club", owner=self.other)
        foreign_event = Event.objects.create(organization=foreign_org, venue=self.venue, category=self.category, title="Foreign draft", description="Private", starts_at=self.event.starts_at, ends_at=self.event.ends_at)
        unrelated_event = Event.objects.create(organization=self.org, venue=self.venue, category=self.category, title="Unrelated owned event", description="Different parent", starts_at=self.event.starts_at, ends_at=self.event.ends_at)
        for value in [foreign_event.pk, unrelated_event.pk, "https://evil.invalid/", "9" * 100, "²"]:
            with self.subTest(event_parent=value):
                self.assert_back(self.client.get(edit, {"return_to": origin, "event_parent": value}), fallback)
        payload.update(title="", event_parent=foreign_event.pk)
        self.assert_back(self.client.post(edit, payload), fallback)

    def test_unnamed_admin_catch_all_is_rejected_without_crashing(self):
        self.client.force_login(self.admin)
        unknown = "/admin/nonexistent/"
        self.assert_back(self.client.get(reverse("event-detail", args=[self.event.pk]), {"return_to": unknown}), "/")
        response = self.client.get(unknown)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.context["back_url"], reverse("admin:index"))
