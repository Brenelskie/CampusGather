import os
from collections import Counter
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from events.models import (
    AgendaItem, Announcement, Event, EventCategory, Organization, Registration, Venue,
)


class Command(BaseCommand):
    help = (
        "Create repeat-safe synthetic examples. New demo users require "
        "CAMPUSGATHER_DEMO_PASSWORD or --password; existing passwords are preserved."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            help="Password for new demo users only. Prefer CAMPUSGATHER_DEMO_PASSWORD to avoid shell history.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        usernames = ("demo_organizer", "demo_student", "demo_student2")
        password = options["password"]
        if password is None:
            password = os.environ.get("CAMPUSGATHER_DEMO_PASSWORD") or None

        if password is not None:
            try:
                validate_password(password)
            except ValidationError as exc:
                raise CommandError("Demo password rejected: " + " ".join(exc.messages)) from exc

        created = Counter()
        preserved_users = []
        skipped_registrations = False
        skipped_existing_students = False
        with transaction.atomic():
            missing = [name for name in usernames if not User.objects.filter(username=name).exists()]
            if missing and not password:
                raise CommandError(
                    "New demo users need a password. Set CAMPUSGATHER_DEMO_PASSWORD "
                    "or pass --password, then run seed_demo again. Nothing was changed."
                )
            for name in missing:
                try:
                    validate_password(password, User(username=name))
                except ValidationError as exc:
                    raise CommandError("Demo password rejected: " + " ".join(exc.messages)) from exc

            users = {}
            for name in usernames:
                user = User.objects.filter(username=name).first()
                if user is None:
                    user = User.objects.create_user(username=name, password=password)
                    created["users"] += 1
                    if name == "demo_organizer":
                        group, _ = Group.objects.get_or_create(name="Organizers")
                        user.groups.add(group)
                else:
                    preserved_users.append(name)
                users[name] = user

            owner = users["demo_organizer"]
            organization = self.example(
                created, Organization, {"owner": owner, "name": "Demo: CampusGather Society"},
                {"description": "A synthetic campus group for classroom demonstrations.",
                 "contact_email": "demo@example.test"},
            )
            hall = self.example(
                created, Venue, {"owner": owner, "name": "Demo: Innovation Hall"},
                {"address": "Example campus, Puerto Princesa, Palawan", "latitude": 9.7392, "longitude": 118.7353},
            )
            quadrangle = self.example(
                created, Venue, {"owner": owner, "name": "Demo: Campus Quadrangle"},
                {"address": "Example campus grounds, Puerto Princesa, Palawan", "latitude": 9.7398, "longitude": 118.7360},
            )
            workshop = self.example(
                created, EventCategory, {"owner": owner, "name": "Demo: Workshop"},
                {"description": "Synthetic learning activities."},
            )
            community = self.example(
                created, EventCategory, {"owner": owner, "name": "Demo: Community"},
                {"description": "Synthetic campus gatherings."},
            )

            now = timezone.now().replace(second=0, microsecond=0)
            definitions = (
                ("Demo: Campus Discovery Workshop", 2, Event.Status.PUBLISHED, hall, workshop),
                ("Demo: Green Campus Meetup", 5, Event.Status.PUBLISHED, quadrangle, community),
                ("Demo: Draft Leadership Forum", 7, Event.Status.DRAFT, hall, workshop),
                ("Demo: Cancelled Arts Night", 8, Event.Status.CANCELLED, quadrangle, community),
                ("Demo: Future Research Showcase", 20, Event.Status.PUBLISHED, hall, workshop),
            )
            examples = []
            for title, days, status, venue, category in definitions:
                starts_at = now + timedelta(days=days)
                event = self.example(
                    created, Event, {"organization": organization, "title": title},
                    {"venue": venue, "category": category, "description": "Synthetic classroom example. No real event or attendee information.",
                     "starts_at": starts_at, "ends_at": starts_at + timedelta(hours=2), "status": status},
                )
                examples.append(event)
                self.example(
                    created, AgendaItem, {"event": event, "title": "Demo: Opening session"},
                    {"description": "Welcome and introduction to the activity.", "starts_at": event.starts_at,
                     "ends_at": event.starts_at + (event.ends_at - event.starts_at) / 2},
                )
                self.example(
                    created, Announcement, {"event": event, "title": "Demo: Before you arrive"},
                    {"body": "Check the event location and schedule. This is synthetic demonstration data."},
                )

            for event, student in (
                (examples[0], users["demo_student"]),
                (examples[0], users["demo_student2"]),
                (examples[1], users["demo_student"]),
            ):
                if Registration.objects.filter(event=event, student=student).exists():
                    continue
                if student.username not in missing:
                    skipped_existing_students = True
                    continue
                if not event.registration_open:
                    skipped_registrations = True
                    continue
                self.example(
                    created, Registration, {"event": event, "student": student},
                    {"attendance_note": "Synthetic attendee: looking forward to the activity."},
                )

        self.stdout.write(self.style.SUCCESS("Synthetic demo data is ready. Existing records were preserved."))
        for label in ("users", "Organization", "Venue", "EventCategory", "Event", "AgendaItem", "Registration", "Announcement"):
            self.stdout.write(f"Created {label}: {created[label]}")
        self.stdout.write("Demo usernames: " + ", ".join(usernames))
        self.stdout.write("No administrator was seeded. Use createsuperuser for an administrator.")
        if preserved_users:
            self.stderr.write(self.style.WARNING(
                "Reused existing usernames without changing passwords, profile data, or roles: "
                + ", ".join(preserved_users)
                + ". Existing demo records and schedules were also preserved."
            ))
        if not owner.is_superuser and not owner.groups.filter(name="Organizers").exists():
            self.stderr.write(self.style.WARNING(
                "The reused demo_organizer account has no organizer access. "
                "An administrator can grant it at /accounts/roles/."
            ))
        if skipped_registrations:
            self.stderr.write(self.style.WARNING(
                "Some preserved events are no longer open; no new registrations were added to those events."
            ))
        if skipped_existing_students:
            self.stderr.write(self.style.WARNING(
                "Existing student accounts were not enrolled. Sample registrations are created only for students newly created by this run."
            ))

    @staticmethod
    def example(created, model, lookup, defaults):
        try:
            obj, was_created = model.objects.get_or_create(**lookup, defaults=defaults)
        except MultipleObjectsReturned as exc:
            raise CommandError(
                f"Multiple {model.__name__} rows match a demo name. "
                "Resolve that ambiguity before seeding; this run was rolled back."
            ) from exc
        if was_created:
            try:
                obj.full_clean()
            except ValidationError as exc:
                raise CommandError(
                    f"Could not validate a new {model.__name__} example: "
                    + " ".join(exc.messages)
                    + " This run was rolled back."
                ) from exc
            created[model.__name__] += 1
        return obj
