from django.urls import path

from . import views

urlpatterns = [
    path('physiology', views.current_datetime, name='reports physiology'),
    path('alerts', views.alerts, name='reports alerts'),
]
