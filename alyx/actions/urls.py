from django.conf.urls import url
from .plot import weighing_plot
from .views import WaterHistoryListView


urlpatterns = [
    url(
        r'^weighing-plot/(?P<subject_id>[-_\w].+)/$',
        weighing_plot,
        name='weighing-plot',
    ),

    url(
        r'^water-history/(?P<subject_id>[-_\w].+)/$',
        WaterHistoryListView.as_view(),
        name='water-history',
    ),
]
