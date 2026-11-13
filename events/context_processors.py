from .permissions import is_admin, is_organizer
from .navigation import navigation_context

def roles(request):
    return {"is_organizer": is_organizer(request.user), "is_administrator": is_admin(request.user), **navigation_context(request)}
