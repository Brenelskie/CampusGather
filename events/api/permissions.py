from rest_framework.permissions import BasePermission, SAFE_METHODS

from events.permissions import is_admin, is_organizer


class OrganizerWrites(BasePermission):
    message = "Organizer access is required."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_organizer(request.user)


class RegistrationAccess(BasePermission):
    message = "You can change only your own registration."

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or is_admin(request.user) or obj.student_id == request.user.pk
