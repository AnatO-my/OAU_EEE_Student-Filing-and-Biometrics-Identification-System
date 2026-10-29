from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied

class SetupSessionAuthentication(SessionAuthentication):

    def authenticate(self, request):
        result = super().authenticate(request)
        if result and result[0].must_change_password and (request.path not in {'/api/auth/csrf/', '/api/auth/me/', '/api/auth/password/change/', '/api/auth/logout/'}):
            raise PermissionDenied('Change your temporary password before accessing the system.')
        return result
