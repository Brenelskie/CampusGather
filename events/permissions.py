from django.db.models import Q

def is_admin(user):
    return user.is_authenticated and user.is_superuser

def is_organizer(user):
    return user.is_authenticated and (is_admin(user) or user.groups.filter(name="Organizers").exists())

def visible_events(user, queryset=None):
    from .models import Event
    qs = queryset if queryset is not None else Event.objects.all()
    if is_admin(user):
        return qs
    public = Q(status__in=[Event.Status.PUBLISHED, Event.Status.CANCELLED])
    if is_organizer(user):
        public |= Q(organization__owner=user)
    return qs.filter(public)

def managed_events(user):
    from .models import Event
    if is_admin(user):
        return Event.objects.all()
    return Event.objects.filter(organization__owner=user) if is_organizer(user) else Event.objects.none()

def can_manage(user, obj):
    if not is_organizer(user):
        return False
    if is_admin(user):
        return True
    owner_id = obj.owner_id if hasattr(obj, "owner_id") else (obj.organization.owner_id if hasattr(obj, "organization_id") else obj.event.organization.owner_id)
    return owner_id == user.pk
