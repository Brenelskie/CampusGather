from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from .forms import form_for, RegistrationNoteForm
from .models import Event, EventCategory, Registration
from .navigation import saved_detail_url, surviving_list_url
from .permissions import can_manage, is_admin, is_organizer, managed_events, visible_events
from .resources import RESOURCES
from .services import OWNED_MODELS, FIELDS, ProtectedDeletion, TemporarilyBusy, delete_record, save_record

def event_list(request):
    qs = visible_events(request.user).select_related("venue", "organization", "category").annotate(total_registrations=Count("registrations"))
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "")
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(organization__name__icontains=query))
    if category_id:
        if category_id.isascii() and category_id.isdecimal() and len(category_id) <= 19 and 0 < int(category_id) <= 9223372036854775807:
            qs = qs.filter(category_id=int(category_id))
        else:
            qs = qs.none()
    categories = EventCategory.objects.filter(events__in=visible_events(request.user)).distinct()
    page = Paginator(qs.order_by("starts_at", "pk"), 9).get_page(request.GET.get("page"))
    return render(request, "events/event_list.html", {"events": page, "page_obj": page, "query": query, "category_id": category_id, "categories": categories, "today": timezone.localdate()})

def event_detail(request, pk):
    event = get_object_or_404(visible_events(request.user).select_related("venue", "organization", "category"), pk=pk)
    from .weather import forecast_for_event
    registration = event.registrations.filter(student=request.user).first() if request.user.is_authenticated else None
    return render(request, "events/event_detail.html", {"event": event, "can_manage": can_manage(request.user, event), "registration": registration, "agenda_items": event.agenda_items.all(), "announcements": event.announcements.all(), "weather": forecast_for_event(event), "map_data": {"latitude": event.venue.latitude, "longitude": event.venue.longitude, "name": event.venue.name, "address": event.venue.address}})

def organizer_required(user):
    if not is_organizer(user):
        raise PermissionDenied("Organizer access is required. An administrator can grant access.")

@login_required
def dashboard(request):
    organizer_required(request.user)
    events = managed_events(request.user).select_related("organization", "venue", "category")
    resources = []
    for key, spec in RESOURCES.items():
        resources.append({"key": key, "label": spec["label"], "description": spec["description"], "count": resource_queryset(request.user, key).count()})
    return render(request, "events/dashboard.html", {"events": events[:6], "event_count": events.count(), "published_count": events.filter(status=Event.Status.PUBLISHED).count(), "registration_count": Registration.objects.filter(event__in=events).count(), "resources": resources})

def resource_spec(resource):
    if resource not in RESOURCES:
        raise Http404
    return RESOURCES[resource]

def resource_queryset(user, resource):
    model = resource_spec(resource)["model"]
    qs = model.objects.all()
    if is_admin(user):
        return qs
    if model in OWNED_MODELS:
        return qs.filter(owner=user)
    if model is Event:
        return managed_events(user)
    return qs.filter(event__in=managed_events(user))

@login_required
def resource_list(request, resource):
    organizer_required(request.user)
    spec = resource_spec(resource)
    page = Paginator(resource_queryset(request.user, resource), 20).get_page(request.GET.get("page"))
    return render(request, "events/resource_list.html", {"spec": spec, "resource": resource, "records": page, "page_obj": page})

@login_required
def resource_detail(request, resource, pk):
    organizer_required(request.user)
    obj = get_object_or_404(resource_queryset(request.user, resource), pk=pk)
    fields = [(obj._meta.get_field(name).verbose_name, getattr(obj, name)) for name in FIELDS[type(obj)]]
    return render(request, "events/resource_detail.html", {"spec": resource_spec(resource), "resource": resource, "object": obj, "fields": fields})

def add_errors(form, exc):
    if hasattr(exc, "message_dict"):
        for field, errors in exc.message_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, str(exc))

@login_required
def resource_form(request, resource, pk=None):
    organizer_required(request.user)
    spec = resource_spec(resource)
    instance = get_object_or_404(resource_queryset(request.user, resource), pk=pk) if pk else None
    initial = {}
    if request.GET.get("event") and "event" in FIELDS[spec["model"]]:
        try:
            initial["event"] = get_object_or_404(managed_events(request.user), pk=request.GET["event"])
        except (ValueError, OverflowError) as exc:
            raise Http404 from exc
    form = form_for(spec["model"])(request.POST if request.method == "POST" else None, instance=instance, initial=initial, user=request.user)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            obj = save_record(request.user, spec["model"], form.cleaned_data, instance)
            messages.success(request, f"{spec['singular'].capitalize()} saved.")
            return redirect(saved_detail_url(request, reverse("resource-detail", kwargs={"resource": resource, "pk": obj.pk})))
        except (ValidationError, TemporarilyBusy) as exc:
            add_errors(form, exc)
            if isinstance(exc, TemporarilyBusy):
                status = 503
    return render(request, "events/resource_form.html", {"form": form, "spec": spec, "resource": resource, "object": instance, "is_venue": resource == "venues", "title": f"{'Edit' if pk else 'Add'} {spec['singular']}"}, status=status)

@login_required
def resource_delete(request, resource, pk):
    organizer_required(request.user)
    obj = get_object_or_404(resource_queryset(request.user, resource), pk=pk)
    return delete_page(request, obj, reverse("resource-list", kwargs={"resource": resource}), {"resource": resource, "spec": resource_spec(resource)})

def delete_page(request, obj, return_url, extra=None):
    error = ""
    status = 200
    if request.method == "POST":
        try:
            delete_record(request.user, obj)
            messages.success(request, "Record removed.")
            return redirect(surviving_list_url(request, return_url))
        except (ProtectedDeletion, TemporarilyBusy) as exc:
            error = str(exc)
            status = 409 if isinstance(exc, ProtectedDeletion) else 503
    return render(request, "events/confirm_delete.html", {"object": obj, "return_url": return_url, "error": error, **(extra or {})}, status=status)

@login_required
def registration_create(request, pk):
    event = get_object_or_404(visible_events(request.user), pk=pk)
    existing = event.registrations.filter(student=request.user).first()
    if existing:
        return redirect(saved_detail_url(request, reverse("registration-detail", kwargs={"pk": existing.pk})))
    form = RegistrationNoteForm(request.POST if request.method == "POST" else None)
    status = 200
    if not event.registration_open and form.is_bound:
        form.add_error(None, "This event is not open for registration.")
    elif request.method == "POST" and form.is_valid():
        try:
            registration = save_record(request.user, Registration, {"event": event, **form.cleaned_data})
            messages.success(request, "You're registered. See you there!")
            return redirect(saved_detail_url(request, reverse("registration-detail", kwargs={"pk": registration.pk})))
        except (ValidationError, TemporarilyBusy) as exc:
            add_errors(form, exc)
            if isinstance(exc, TemporarilyBusy):
                status = 503
    return render(request, "events/registration_form.html", {"form": form, "event": event, "title": "Register for event", "can_submit": event.registration_open}, status=status)

def registration_queryset(user, admin_mode=False):
    qs = Registration.objects.select_related("event", "event__venue", "student")
    if admin_mode:
        if not is_admin(user):
            raise PermissionDenied
        return qs
    return qs.filter(student=user)

@login_required
def registration_list(request, admin_mode=False):
    page = Paginator(registration_queryset(request.user, admin_mode), 20).get_page(request.GET.get("page"))
    return render(request, "events/registration_list.html", {"registrations": page, "page_obj": page, "admin_mode": admin_mode})

@login_required
def registration_detail(request, pk, admin_mode=False):
    obj = get_object_or_404(registration_queryset(request.user, admin_mode), pk=pk)
    return render(request, "events/registration_detail.html", {"registration": obj, "admin_mode": admin_mode, "can_edit": obj.event.registration_open, "can_cancel": True})

@login_required
def registration_edit(request, pk, admin_mode=False):
    obj = get_object_or_404(registration_queryset(request.user, admin_mode), pk=pk)
    form = RegistrationNoteForm(request.POST if request.method == "POST" else None, instance=obj)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            save_record(request.user, Registration, form.cleaned_data, obj)
            messages.success(request, "Attendance note saved.")
            return redirect(saved_detail_url(request, reverse("admin-registration-detail" if admin_mode else "registration-detail", kwargs={"pk": obj.pk})))
        except (ValidationError, TemporarilyBusy) as exc:
            add_errors(form, exc)
            if isinstance(exc, TemporarilyBusy):
                status = 503
    return render(request, "events/registration_form.html", {"form": form, "event": obj.event, "registration": obj, "admin_mode": admin_mode, "title": "Edit attendance note", "can_submit": obj.event.registration_open}, status=status)

@login_required
def registration_delete(request, pk, admin_mode=False):
    obj = get_object_or_404(registration_queryset(request.user, admin_mode), pk=pk)
    return delete_page(request, obj, reverse("admin-registration-list" if admin_mode else "registration-list"), {"admin_mode": admin_mode})

@login_required
def roster(request, pk):
    organizer_required(request.user)
    event = get_object_or_404(managed_events(request.user), pk=pk)
    return render(request, "events/roster.html", {"event": event, "registrations": event.registrations.select_related("student")})
