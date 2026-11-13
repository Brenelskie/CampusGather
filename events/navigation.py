from urllib.parse import parse_qs, unquote, urlencode, urlsplit

from django.contrib import admin
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Event, Registration
from .permissions import is_admin, is_organizer, managed_events, visible_events
from .resources import RESOURCES
from .services import OWNED_MODELS


def _resource_records(user, resource):
    model = RESOURCES[resource]["model"]
    if is_admin(user):
        return model.objects.all()
    if model in OWNED_MODELS:
        return model.objects.filter(owner=user)
    if model is Event:
        return managed_events(user)
    return model.objects.filter(event__in=managed_events(user))


def _admin_model(match):
    if not match.url_name:
        return None, ""
    for model, model_admin in admin.site._registry.items():
        prefix = f"{model._meta.app_label}_{model._meta.model_name}_"
        if match.url_name.startswith(prefix):
            return model_admin, match.url_name[len(prefix):]
    return None, ""


def _can_visit(request, match):
    name, kwargs, user = match.url_name, match.kwargs, request.user
    if match.namespace == "admin":
        if not user.is_active or not user.is_staff:
            return False
        if name == "index":
            return True
        if name == "app_list":
            return user.has_module_perms(kwargs["app_label"])
        model_admin, action = _admin_model(match)
        if not model_admin or action not in {"changelist", "change", "history"}:
            return False
        obj = None
        if action != "changelist":
            obj = model_admin.get_object(request, kwargs.get("object_id"))
            if obj is None:
                return False
        return model_admin.has_view_or_change_permission(request, obj)
    if match.namespace == "api":
        if kwargs.get("format"):
            return False
        if name == "api-root":
            return True
        if not name or not name.endswith(("-list", "-detail")):
            return False
        if name.startswith("registration-") and not user.is_authenticated:
            return False
        view = match.func.cls()
        view.request = type("ReadRequest", (), {"user": user, "method": "GET"})()
        records = view.get_queryset()
        return name.endswith("-list") or records.filter(pk=kwargs.get("pk")).exists()
    if match.namespace:
        return False
    if name == "event-list":
        return True
    if name == "event-detail":
        return visible_events(user).filter(pk=kwargs["pk"]).exists()
    if name == "dashboard":
        return is_organizer(user)
    if name == "roles":
        return is_admin(user)
    if name == "roster":
        return is_organizer(user) and managed_events(user).filter(pk=kwargs["pk"]).exists()
    if name in {"resource-list", "resource-detail"}:
        resource = kwargs["resource"]
        if not is_organizer(user) or resource not in RESOURCES:
            return False
        return name == "resource-list" or _resource_records(user, resource).filter(pk=kwargs["pk"]).exists()
    if name in {"registration-list", "registration-detail", "admin-registration-list", "admin-registration-detail"}:
        if not user.is_authenticated or (name.startswith("admin-") and not is_admin(user)):
            return False
        if name.endswith("-list"):
            return True
        records = Registration.objects.all() if name.startswith("admin-") else Registration.objects.filter(student=user)
        return records.filter(pk=kwargs["pk"]).exists()
    return False


def _list_query(match, query):
    if match.url_name != "event-list" and not (match.url_name or "").endswith(("-list", "_changelist")):
        return ""
    parsed = parse_qs(query, max_num_fields=30)
    values = {}
    for key in ("q", "category", "page", "p"):
        value = parsed.get(key, [""])[-1]
        if key == "q" and value and len(value) <= 200 and not any(ord(c) < 32 or ord(c) == 127 for c in value):
            values[key] = value
        elif key == "category" and value.isascii() and value.isdecimal() and len(value) <= 19:
            values[key] = value
        elif key in {"page", "p"} and value.isascii() and value.isdecimal() and len(value) <= 6 and (int(value) > 0 or key == "p"):
            if key != "p" or match.namespace == "admin":
                values[key] = value
    return urlencode(values)


def safe_destination(request, candidate, *, allow_current=False):
    if not isinstance(candidate, str) or not candidate or len(candidate) > 2048:
        return ""
    if candidate != candidate.strip() or "\\" in candidate or any(ord(c) < 32 or ord(c) == 127 for c in candidate):
        return ""
    if not url_has_allowed_host_and_scheme(candidate, {request.get_host()}, require_https=request.is_secure()):
        return ""
    try:
        parts = urlsplit(candidate)
        decoded = unquote(parts.path)
        if not parts.path.startswith("/") or decoded.startswith("//") or "\\" in decoded or any(ord(c) < 32 or ord(c) == 127 for c in decoded):
            return ""
        if not allow_current and parts.path == request.path:
            return ""
        match = resolve(parts.path)
        if not _can_visit(request, match):
            return ""
        query = _list_query(match, parts.query)
    except (ValueError, Resolver404):
        return ""
    return parts.path + ("?" + query if query else "")


def return_destination(request):
    match = getattr(request, "resolver_match", None)
    data = request.POST if request.method == "POST" and match and not match.namespace else request.GET
    return safe_destination(request, data.get("return_to", ""))


def event_parent_id(request):
    match = getattr(request, "resolver_match", None)
    if not match or match.namespace or match.url_name not in {"resource-create", "resource-detail", "resource-update", "resource-delete"}:
        return ""
    resource = match.kwargs.get("resource")
    if resource not in {"events", "agenda-items", "announcements"} or not is_organizer(request.user):
        return ""
    data = request.POST if request.method == "POST" else request.GET
    value = data.get("event_parent", "")
    if not (value.isascii() and value.isdecimal() and len(value) <= 19 and 0 < int(value) <= 9223372036854775807):
        return ""
    if not managed_events(request.user).filter(pk=value).exists():
        return ""
    pk = match.kwargs.get("pk")
    if pk:
        field = "pk" if resource == "events" else "event_id"
        actual_parent = _resource_records(request.user, resource).filter(pk=pk).values_list(field, flat=True).first()
        if str(actual_parent) != str(int(value)):
            return ""
    elif resource == "events" or data.get("event") != str(int(value)):
        return ""
    return str(int(value))


def with_return_to(url, destination, event_parent=""):
    params = {}
    if destination and urlsplit(destination).path != urlsplit(url).path:
        params["return_to"] = destination
    if event_parent:
        params["event_parent"] = event_parent
    return url + ("?" + urlencode(params) if params else "")


def saved_detail_url(request, url):
    return with_return_to(url, return_destination(request), event_parent_id(request))


def surviving_list_url(request, url):
    destination = return_destination(request)
    return destination if urlsplit(destination).path == url else url


def _parent(request):
    match = getattr(request, "resolver_match", None)
    if not match:
        return reverse("event-list")
    name, kwargs = match.url_name or "", match.kwargs
    if match.namespace == "admin":
        if name == "index" or name == "login":
            return reverse("dashboard") if is_organizer(request.user) else reverse("event-list")
        model_admin, action = _admin_model(match)
        if model_admin:
            if action == "changelist":
                return reverse("admin:index")
            opts = model_admin.model._meta
            prefix = f"admin:{opts.app_label}_{opts.model_name}_"
            if action in {"delete", "history", "password_change"} and "object_id" in kwargs:
                return reverse(prefix + "change", args=[kwargs["object_id"]])
            return reverse(prefix + "changelist")
        return reverse("admin:index")
    if match.namespace == "api":
        if name.endswith("-detail"):
            return reverse("api:" + name.removesuffix("-detail") + "-list")
        return reverse("event-list") if name == "api-root" else reverse("api:api-root")
    if name.startswith("resource-") and kwargs.get("resource") in RESOURCES:
        resource = kwargs["resource"]
        if name in {"resource-update", "resource-delete"}:
            return reverse("resource-detail", args=[resource, kwargs["pk"]])
        if name == "resource-list":
            return reverse("dashboard")
        if name == "resource-create" and resource in {"agenda-items", "announcements"}:
            event = request.GET.get("event", "")
            if event.isascii() and event.isdecimal() and len(event) <= 19 and managed_events(request.user).filter(pk=event).exists():
                return reverse("event-detail", args=[event])
        return reverse("resource-list", args=[resource])
    if name.startswith("admin-registration-") or name in {"registration-list", "registration-detail", "registration-edit", "registration-delete"}:
        prefix = "admin-registration-" if name.startswith("admin-") else "registration-"
        if name.endswith(("-edit", "-delete")):
            return reverse(prefix + "detail", args=[kwargs["pk"]])
        if name.endswith("-detail"):
            return reverse(prefix + "list")
        return reverse("dashboard") if name.startswith("admin-") else reverse("event-list")
    if name in {"registration-create", "roster"}:
        return reverse("event-detail", args=[kwargs["pk"]])
    if name == "roles":
        return reverse("dashboard")
    return reverse("event-list")


def navigation_context(request):
    match = getattr(request, "resolver_match", None)
    name = match.url_name if match else ""
    origin = return_destination(request)
    event_parent = event_parent_id(request)
    try:
        parent = reverse("event-detail", args=[event_parent]) if event_parent else _parent(request)
        parent = safe_destination(request, parent) or reverse("event-list")
    except NoReverseMatch:
        parent = reverse("event-list")
    back = origin or parent
    if event_parent:
        back = with_return_to(parent, origin)
    if name in {"resource-update", "resource-delete", "registration-edit", "registration-delete", "admin-registration-edit", "admin-registration-delete", "registration-create"}:
        back = with_return_to(parent, origin)
    if name == "roster" or (name == "resource-create" and match.kwargs.get("resource") in {"agenda-items", "announcements"} and parent.startswith("/events/")):
        back = with_return_to(parent, origin)
    current = safe_destination(request, request.get_full_path(), allow_current=True) or request.path
    origin_params = {"return_to": origin or parent}
    if event_parent:
        origin_params["event_parent"] = event_parent
    return {
        "back_url": back,
        "show_back": not (match and not match.namespace and name == "event-list"),
        "return_to": origin,
        "event_parent": event_parent,
        "navigation_query": urlencode({"return_to": current}),
        "origin_query": urlencode(origin_params),
    }
