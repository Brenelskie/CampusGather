from django.urls import path
from . import views

urlpatterns = [
    path("", views.event_list, name="event-list"),
    path("events/<int:pk>/", views.event_detail, name="event-detail"),
    path("events/<int:pk>/register/", views.registration_create, name="registration-create"),
    path("events/<int:pk>/roster/", views.roster, name="roster"),
    path("organizer/", views.dashboard, name="dashboard"),
    path("registrations/", views.registration_list, name="registration-list"),
    path("registrations/<int:pk>/", views.registration_detail, name="registration-detail"),
    path("registrations/<int:pk>/edit/", views.registration_edit, name="registration-edit"),
    path("registrations/<int:pk>/cancel/", views.registration_delete, name="registration-delete"),
    path("manage/registrations/", views.registration_list, {"admin_mode": True}, name="admin-registration-list"),
    path("manage/registrations/<int:pk>/", views.registration_detail, {"admin_mode": True}, name="admin-registration-detail"),
    path("manage/registrations/<int:pk>/edit/", views.registration_edit, {"admin_mode": True}, name="admin-registration-edit"),
    path("manage/registrations/<int:pk>/delete/", views.registration_delete, {"admin_mode": True}, name="admin-registration-delete"),
    path("manage/<slug:resource>/", views.resource_list, name="resource-list"),
    path("manage/<slug:resource>/add/", views.resource_form, name="resource-create"),
    path("manage/<slug:resource>/<int:pk>/", views.resource_detail, name="resource-detail"),
    path("manage/<slug:resource>/<int:pk>/edit/", views.resource_form, name="resource-update"),
    path("manage/<slug:resource>/<int:pk>/delete/", views.resource_delete, name="resource-delete"),
]
