from django.urls import path
from jobs import views as jv

urlpatterns = [
    path('jobs', jv.JobList.as_view(), name="job-list"),
    path('jobs/<uuid:pk>', jv.JobDetail.as_view(), name="jobs-detail"),
]
