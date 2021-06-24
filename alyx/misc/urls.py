from django.urls import path, re_path
from misc import views as mv

user_list = mv.UserViewSet.as_view({'get': 'list'})
user_detail = mv.UserViewSet.as_view({'get': 'retrieve'})

urlpatterns = [
    path('', mv.api_root),
    path('labs', mv.LabList.as_view(), name="lab-list"),
    path('labs/<str:name>', mv.LabDetail.as_view(), name="lab-detail"),
    path('notes', mv.NoteList.as_view(), name="note-list"),
    path('notes/<uuid:pk>', mv.NoteDetail.as_view(), name="note-detail"),
    path('users/<str:username>', user_detail, name='user-detail'),
    path('users', user_list, name='user-list'),
    re_path('^uploaded/(?P<img_url>.*)', mv.UploadedView.as_view(), name='uploaded'),
    path('cache.zip', mv.CacheDownloadView.as_view(), name='cache-download'),
    path('cache/info', mv.CacheVersionView.as_view(), name='cache-info'),
]
