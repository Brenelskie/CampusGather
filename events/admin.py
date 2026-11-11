from django.contrib import admin
from .models import Organization, Venue, EventCategory, Event, AgendaItem, Registration, Announcement

class ApplicationDataAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

for model in (Organization, Venue, EventCategory, Event, AgendaItem, Registration, Announcement):
    admin.site.register(model, ApplicationDataAdmin)
admin.site.site_header = "CampusGather administration"
admin.site.site_title = "CampusGather admin"
admin.site.index_title = "Users and groups; manage event data from the organizer dashboard"
