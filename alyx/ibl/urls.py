from django.urls import path

from . import views

urlpatterns = [
        path('', views.SubjectIncompleteListView.as_view(), name='cop page')
]
