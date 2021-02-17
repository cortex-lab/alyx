from django.urls import path

from . import views

urlpatterns = [
    path('physiology', views.current_datetime, name='test reports'),
    path('alerts', views.alerts, name='test reports'),
]
