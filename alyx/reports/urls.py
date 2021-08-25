from django.urls import path

from . import views

urlpatterns = [
    path('alerts/overview', views.InsertionTableWithFilter.as_view(), name='insertion table'),
    path('alerts/task_qc/<uuid:pid>', views.plot_task_qc, name='plot_task_qc'),
    path('alerts/video_qc/<uuid:pid>', views.plot_video_qc, name='plot_video_qc'),
    path('alerts/overview/<uuid:pid>', views.InsertionOverview.as_view(),
         name='insertion overview'),
]
