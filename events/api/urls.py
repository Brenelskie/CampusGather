from rest_framework.routers import DefaultRouter

from .views import (
    AgendaItemViewSet, AnnouncementViewSet, EventCategoryViewSet, EventViewSet,
    OrganizationViewSet, RegistrationViewSet, VenueViewSet,
)

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("venues", VenueViewSet, basename="venue")
router.register("categories", EventCategoryViewSet, basename="category")
router.register("events", EventViewSet, basename="event")
router.register("agenda-items", AgendaItemViewSet, basename="agenda-item")
router.register("registrations", RegistrationViewSet, basename="registration")
router.register("announcements", AnnouncementViewSet, basename="announcement")

urlpatterns = router.urls
