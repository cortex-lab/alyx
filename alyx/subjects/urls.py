from django.conf.urls import include, url
from subjects.views import SubjectAutocomplete

urlpatterns = [
    url(
        r'^subjects/$',
        SubjectAutocomplete.as_view(),
        name='subject-autocomplete',
    ),
]
