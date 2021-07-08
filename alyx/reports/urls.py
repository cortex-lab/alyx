from django.urls import path

from . import views

urlpatterns = [
    path('physiology', views.current_datetime, name='reports physiology'),
    # path('alerts', views.alerts, name='reports alerts'),
    path('alerts', views.basepage, name='reports alerts'),
    path('alerts/<str:lab>', views.AlertsLabView.as_view(), name='reports alerts lab'),
    path('alerts/<str:lab>/insertions', views.AlertsInsertionView.as_view(), name='reports alerts insertions'),
    path('alerts/session/task_qc/<uuid:eid>', views.plot_task_qc, name='plot_task_qc'),
    path('blabla/filter', views.session_option, name='year'),
]
