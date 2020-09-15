from django.urls import path
from jobs import views as jv

urlpatterns = [
    path('tasks', jv.TaskList.as_view(), name="tasks-list"),
    path('tasks/<uuid:pk>', jv.TaskDetail.as_view(), name="tasks-detail"),


    path('admin-tasks/status', jv.TasksStatusView.as_view(), name='tasks_status',),
    path('admin-tasks/status/<str:graph>', jv.TasksStatusView.as_view(),
         name='tasks_status_graph', ),
    path('admin-tasks/status/<str:graph>/<str:lab>', jv.TasksStatusView.as_view(),
         name='tasks_status_graph_lab', ),
]
