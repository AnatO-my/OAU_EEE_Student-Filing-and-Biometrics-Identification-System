from django.urls import path

from .views import AdviserMessageSendView

urlpatterns = [
    path(
        "adviser-messages/",
        AdviserMessageSendView.as_view(),
        name="adviser-message-send",
    ),
    path(
        "hod-messages/"
        
    )
]