from django.urls import path

from . import views

urlpatterns = [
    path('physiology', views.current_datetime, name='reports physiology'),
    # path('alerts', views.alerts, name='reports alerts'),
    path('alerts', views.basepage, name='reports alerts'),
    path('alerts/<str:lab>', views.AlertsLabView.as_view(), name='reports alerts lab'),
    path('alerts/<str:lab>/insertions', views.AlertsInsertionView.as_view(), name='reports alerts insertions' )
]
