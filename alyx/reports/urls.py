from django.urls import path

from . import views

urlpatterns = [
    path('physiology', views.current_datetime, name='reports physiology'),
    path('alerts', views.alerts, name='reports alerts'),
    #path('alerts', views.basepage, name='reports alerts'),
    #path('alerts/<str:lab>', views.AlertsLabView.as_view(), name='reports alerts lab'),

    path('alerts/overview', views.InsertionTable.as_view(), name='insertion table'),
    path('alerts/task_qc/<uuid:pid>', views.plot_task_qc, name='plot_task_qc'),
    path('alerts/overview/<uuid:pid>', views.InsertionOverview.as_view(), name='insertion overview'),

]
