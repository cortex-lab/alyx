from django.urls import path
from jobs import views as jv

urlpatterns = [
    path('tasks', jv.TaskList.as_view(), name="tasks-list"),
    path('tasks/<uuid:pk>', jv.TaskDetail.as_view(), name="tasks-detail"),
]
