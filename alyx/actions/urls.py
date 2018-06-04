from django.urls import path
from .plot import weighing_plot
from .views import WaterHistoryListView


urlpatterns = [
    path('weighing-plot/<uuid:subject_id>',
         weighing_plot,
         name='weighing-plot',
         ),

    path('water-history/<uuid:subject_id>',
         WaterHistoryListView.as_view(),
         name='water-history',
         ),
]
