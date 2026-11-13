from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import SignUpForm
from events.permissions import is_admin
from events.navigation import saved_detail_url

def signup(request):
    if request.user.is_authenticated:
        return redirect("event-list")
    form = SignUpForm(request.POST or None)
    next_url = request.POST.get("next", request.GET.get("next", ""))
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to CampusGather. Your student account is ready.")
        if url_has_allowed_host_and_scheme(next_url, {request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)
        return redirect("event-list")
    return render(request, "accounts/signup.html", {"form": form, "next": next_url})

@login_required
def roles(request):
    if not is_admin(request.user):
        raise PermissionDenied
    group, _ = Group.objects.get_or_create(name="Organizers")
    if request.method == "POST":
        try:
            user = get_object_or_404(get_user_model(), pk=request.POST.get("user_id"))
        except (ValueError, OverflowError) as exc:
            raise Http404 from exc
        action = request.POST.get("action")
        if action == "grant":
            user.groups.add(group)
            messages.success(request, f"Organizer access granted to {user.username}.")
        elif action == "revoke":
            user.groups.remove(group)
            messages.success(request, f"Organizer access removed from {user.username}. Their records are retained.")
        return redirect(saved_detail_url(request, reverse("roles")))
    users = get_user_model().objects.order_by("username").prefetch_related("groups")
    return render(request, "accounts/roles.html", {"profiles": [{"user": u, "organizer": any(g.name == "Organizers" for g in u.groups.all())} for u in users]})
