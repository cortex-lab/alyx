from django.urls import path
from experiments import views as ev

urlpatterns = [
    path('insertions', ev.ProbeInsertionList.as_view(), name="probeinsertion-list"),
    path('insertions/<uuid:pk>', ev.ProbeInsertionDetail.as_view(), name="probeinsertion-detail"),
    path('trajectories', ev.TrajectoryEstimateList.as_view(), name="trajectoryestimate-list"),
    path('trajectories/<uuid:pk>', ev.TrajectoryEstimateDetail.as_view(),
         name="trajectoryestimate-detail"),
]
