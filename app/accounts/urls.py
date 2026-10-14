from django.urls import path

from .views import CSRFTokenView, CurrentUserView, LoginView, LogoutView

urlpatterns = [
    path("csrf/", CSRFTokenView.as_view(), name="auth-csrf"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
]
from .lifecycle_views import PasswordChangeView, PasswordResetRequestView, PasswordResetConfirmView

urlpatterns += [
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]
