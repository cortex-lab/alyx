from django.urls import path
from experiments import views as ev

urlpatterns = [
    path('insertions', ev.ProbeInsertionList.as_view(), name="probeinsertion-list"),
    path('insertions/<uuid:pk>', ev.ProbeInsertionDetail.as_view(), name="probeinsertion-detail"),
    path('trajectories', ev.TrajectoryEstimateList.as_view(), name="trajectoryestimate-list"),
    path('trajectories/<uuid:pk>', ev.TrajectoryEstimateDetail.as_view(),
         name="trajectoryestimate-detail"),
    path('channels', ev.ChannelList.as_view(), name="channel-list"),
    path('channels/<uuid:pk>', ev.ChannelDetail.as_view(), name="channel-detail"),
    path('brain-regions', ev.BrainRegionList.as_view(), name="brainregion-list"),
    path('brain-regions/<int:pk>', ev.BrainRegionDetail.as_view(), name="brainregion-detail"),
]
