from .permissions import is_admin, is_organizer

def roles(request):
    return {"is_organizer": is_organizer(request.user), "is_administrator": is_admin(request.user)}
