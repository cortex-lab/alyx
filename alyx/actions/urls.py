from django.urls import path
from .views import SubjectHistoryListView, WaterHistoryListView, weighing_plot


urlpatterns = [
    path('weighing-plot/<uuid:subject_id>',
         weighing_plot,
         name='weighing-plot',
         ),

    path('water-history/<uuid:subject_id>',
         WaterHistoryListView.as_view(),
         name='water-history',
         ),

    path('subject-history/<uuid:subject_id>',
         SubjectHistoryListView.as_view(),
         name='subject-history',
         ),
]
