from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from students.models import Student
from .models import AdviserMessage, HODMessage
from .serializers import (AdviserMessageSendSerializer, StudentMessageSerializer,
                          HODMessageSendSerializer, HODInboxSerializer)
from .services import send_adviser_message, send_hod_message

from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import CurrentUserSerializer, LoginSerializer
from .throttling import (
    clear_login_failures,
    login_failure_key,
    login_retry_after,
    record_login_failure,
)


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


#class that starts a staff or student session and returns the authenticated identity,
#failed attempts are counted against the client address and submitted username so
#repeated guessing is paused with a 429 before the credentials are checked again
@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    # Anonymous clients obtain a CSRF token from /api/auth/csrf/ before login.
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        key = login_failure_key(
            request.META.get("REMOTE_ADDR", ""),
            str(request.data.get("username", "")),
        )
        retry_after = login_retry_after(key)
        if retry_after:
            return Response(
                {"detail": "Too many failed sign in attempts. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
            )

        serializer = LoginSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            #every rejected credential counts, including unknown usernames, so
            #the endpoint keeps answering identically while the counter fills
            record_login_failure(key)
            raise

        clear_login_failures(key)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response(CurrentUserSerializer(user).data)


#class that ends the session for a staff member or a student, csrf is enforced here by
#session authentication
class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


#class that reports the current identity so the frontend can gate its interface, it only
#ever returns the caller's own account and no staff or student data
class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)




class IsHOD(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.is_active and user.is_staff and user.is_superuser


class AdviserMessageSendView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AdviserMessageSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = send_adviser_message(user=request.user, validated_data=serializer.validated_data)
        return Response({
            "message_id": message.pk, "audience": message.audience,
            "subject": message.subject, "recipient_count": message.recipients.count(),
            "created_at": message.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class HODMessageSendView(APIView):
    permission_classes = [IsHOD]

    def post(self, request):
        serializer = HODMessageSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = send_hod_message(user=request.user, validated_data=serializer.validated_data)
        return Response({
            "message_id": message.pk, "audience": message.audience,
            "subject": message.subject,
            "recipient_count": message.recipients.count() + message.adviser_recipients.count(),
            "created_at": message.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class MessagePagination(PageNumberPagination):
    page_size = 20


class MyStudentMessagesView(generics.ListAPIView):
    serializer_class = StudentMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MessagePagination

    def get_queryset(self):
        student = get_object_or_404(Student, user=self.request.user)
        return AdviserMessage.objects.filter(recipients=student).select_related("assignment__staff")


class MyHODMessagesView(generics.ListAPIView):
    serializer_class = HODInboxSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MessagePagination

    def get_queryset(self):
        return HODMessage.objects.filter(
            Q(recipients__user=self.request.user) | Q(adviser_recipients=self.request.user)
        ).select_related("sender").distinct()

class MyStudentMessageDetailView(MyStudentMessagesView):
    def get(self, request, *args, **kwargs):
        message = get_object_or_404(
            self.get_queryset(),
            pk=kwargs["message_id"],
        )
        serializer = self.get_serializer(message)
        return Response(serializer.data)