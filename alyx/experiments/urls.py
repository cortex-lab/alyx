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
    path('chronic-insertions', ev.ChronicInsertionList.as_view(), name="chronicinsertion-list"),
    path('chronic-insertions/<uuid:pk>', ev.ChronicInsertionDetail.as_view(),
         name="chronicinsertion-detail"),
    path('fields-of-view', ev.FOVList.as_view(), name="fieldsofview-list"),
    path('fields-of-view/<uuid:pk>', ev.FOVDetail.as_view(), name="fieldsofview-detail"),
    path('fov-location', ev.FOVLocationList.as_view(), name="fovlocation-list"),
    path('imaging-stack', ev.ImagingStackList.as_view(), name="imagingstack-list"),
    path('imaging-stack/<uuid:pk>', ev.ImagingStackDetail.as_view(), name="imagingstack-detail")]
