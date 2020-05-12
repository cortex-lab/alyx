from django.urls import path
from jobs import views as jv

urlpatterns = [
    path('jobs', jv.JobList.as_view(), name="jobs-list"),
    path('jobs/<uuid:pk>', jv.JobDetail.as_view(), name="jobs-detail"),
    path('tasks', jv.TaskList.as_view(), name="tasks-list"),
    path('tasks/<str:name>', jv.TaskDetail.as_view(), name="tasks-detail"),
]
