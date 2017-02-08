from django.conf.urls import include, url
from subjects.views import (SubjectAutocomplete,
                            CageLabelAutocomplete,
                            )

urlpatterns = [
    url(
        r'^subjects/$',
        SubjectAutocomplete.as_view(),
        name='subject-autocomplete',
    ),
    url(
        r'^cage-label/$',
        CageLabelAutocomplete.as_view(),
        name='cage-label-autocomplete',
    ),
]
