from django.conf.urls import include, url
from .plot import (weighing_plot,)


urlpatterns = [
    url(
        r'^weighing-plot/(?P<subject_id>[-_\w].+)/$',
        weighing_plot,
        name='weighing-plot',
    ),
]
