from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import CurrentUserSerializer, LoginSerializer


#class that issues the csrf cookie and returns its value so the React client can
#send it in the X-CSRFToken header, called again after login because Django
#rotates the token when the session changes
@method_decorator(never_cache, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFTokenView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


#class that starts a staff session and returns the authenticated identity
class LoginView(APIView):
    #session authentication is deliberately skipped here, the client cannot present a
    #csrf token before it has authenticated, and the credentials in the request body
    #are what authorise the action
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        login(request, user)
        return Response(CurrentUserSerializer(user).data)


#class that ends the staff session, csrf is enforced here by session authentication
class LogoutView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


#class that reports the current staff identity so the frontend can gate its interface
class CurrentUserView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)
