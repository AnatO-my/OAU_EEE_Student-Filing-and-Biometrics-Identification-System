from django.urls import path
from . import views
urlpatterns = [
    path("teaching/courses/", views.CoursesView.as_view()),
    path("teaching/messages/", views.MessagesView.as_view()),
    path("teaching/messages/<uuid:message_id>/", views.MessageView.as_view()),
    path("teaching/messages/<uuid:message_id>/history/", views.MessageHistoryView.as_view()),
    path("teaching/materials/", views.MaterialsView.as_view()),
    path("teaching/materials/<uuid:material_id>/", views.MaterialView.as_view()),
    path("teaching/materials/<uuid:material_id>/versions/<int:version>/download/", views.MaterialDownloadView.as_view()),
    path("teaching/timetable/", views.TimetableView.as_view()),
    path("teaching/timetable/<int:entry_id>/", views.TimetableEntryView.as_view()),
]
urlpatterns += [path("teaching/audience-options/", views.AudienceOptionsView.as_view())]
