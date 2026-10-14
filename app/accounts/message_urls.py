from django.urls import path
from .views import (
    AdviserMessageSendView,
    HODMessageSendView,
    MyStudentMessageDetailView,
    MyStudentMessagesView,
    MyHODMessagesView,
)

urlpatterns = [
    path(
        "adviser-messages/",
        AdviserMessageSendView.as_view(),
        name="adviser-message-send",
    ),
    path("hod-messages/", HODMessageSendView.as_view(), name="hod-message-send"),
    path("me/messages/", MyStudentMessagesView.as_view(), name="my-student-messages"),
    path("me/hod-messages/", MyHODMessagesView.as_view(), name="my-hod-messages"),
    path(
        "me/messages/<int:message_id>/",
        MyStudentMessageDetailView.as_view(),
        name="my-student-message-detail",
    ),
]
