from django.conf.urls import include
from django.urls import path, re_path
from django.contrib import admin
from rest_framework.authtoken import views as authv
from rest_framework.documentation import include_docs_urls

from subjects import views as sv
from actions import views as av
from data import views as dv
from misc import views as mv


register_file = dv.RegisterFileViewSet.as_view({
    'post': 'create'
})
sync_file_status = dv.SyncViewSet.as_view({
    'post': 'sync',
    'get': 'sync_status'
})
new_download = dv.DownloadViewSet.as_view({
    'post': 'create'
})

user_list = mv.UserViewSet.as_view({
    'get': 'list'
})

user_detail = mv.UserViewSet.as_view({
    'get': 'retrieve'
})

admin.site.site_header = 'Alyx'

urlpatterns = [
    path('', mv.api_root),

    path('', include('experiments.urls')),
    path('', include('jobs.urls')),

    path('admin/', admin.site.urls),

    path('admin-subjects/', include('subjects.urls')),

    path('admin-actions/', include('actions.urls')),

    path('auth/', include('rest_framework.urls', namespace='rest_framework')),

    path('auth-token', authv.obtain_auth_token),

    path('data-formats', dv.DataFormatList.as_view(),
         name="dataformat-list"),

    path('data-formats/<str:name>', dv.DataFormatDetail.as_view(),
         name="dataformat-detail"),

    path('data-repository-type', dv.DataRepositoryTypeList.as_view(),
         name="datarepositorytype-list"),

    path('data-repository-type/<str:name>', dv.DataRepositoryTypeDetail.as_view(),
         name="datarepositorytype-detail"),

    path('data-repository', dv.DataRepositoryList.as_view(),
         name="datarepository-list"),

    path('data-repository/<str:name>', dv.DataRepositoryDetail.as_view(),
         name="datarepository-detail"),

    path('datasets', dv.DatasetList.as_view(),
         name="dataset-list"),

    path('datasets/<uuid:pk>', dv.DatasetDetail.as_view(),
         name="dataset-detail"),

    path('dataset-types', dv.DatasetTypeList.as_view(),
         name="datasettype-list"),

    path('dataset-types/<str:name>', dv.DatasetTypeDetail.as_view(),
         name="datasettype-detail"),

    path('docs/', include_docs_urls(title='Alyx REST API documentation')),

    path('downloads', dv.DownloadList.as_view(),
         name="download-list"),

    path('downloads/<uuid:pk>', dv.DownloadDetail.as_view(),
         name="download-detail"),

    path('files', dv.FileRecordList.as_view(),
         name="filerecord-list"),

    path('files/<uuid:pk>', dv.FileRecordDetail.as_view(),
         name="filerecord-detail"),

    path('labs', mv.LabList.as_view(),
         name="lab-list"),

    path('labs/<str:name>', mv.LabDetail.as_view(),
         name="lab-detail"),

    path('locations', av.LabLocationList.as_view(),
         name="location-list"),

    path('locations/<str:name>', av.LabLocationAPIDetails.as_view(),
         name="location-detail"),

    path('new-download', new_download, name='new-download'),

    path('projects', sv.ProjectList.as_view(),
         name="project-list"),

    path('projects/<str:name>', sv.ProjectDetail.as_view(),
         name="project-detail"),

    path('register-file', register_file,
         name="register-file"),

    path('sessions', av.SessionAPIList.as_view(),
         name="session-list"),

    path('sessions/<uuid:pk>', av.SessionAPIDetail.as_view(),
         name="session-detail"),

    path('subjects', sv.SubjectList.as_view(),
         name="subject-list"),

    path('subjects/<str:nickname>', sv.SubjectDetail.as_view(),
         name="subject-detail"),

    path('sync-file-status', sync_file_status,
         name="sync-file-status"),

    re_path('^uploaded/(?P<img_url>.*)', mv.UploadedView.as_view(), name='uploaded'),

    path('users', user_list,
         name='user-list'),

    path('users/<str:username>', user_detail,
         name='user-detail'),

    path('water-administrations', av.WaterAdministrationAPIListCreate.as_view(),
         name="water-administration-create"),

    path('water-administrations/<uuid:pk>', av.WaterAdministrationAPIDetail.as_view(),
         name="water-administration-detail"),

    path('water-requirement/<str:nickname>', av.WaterRequirement.as_view(),
         name='water-requirement'),

    path('water-restriction', av.WaterRestrictionList.as_view(),
         name='water-restriction-list'),

    path('water-restricted-subjects', sv.WaterRestrictedSubjectList.as_view(),
         name="water-restricted-subject-list"),

    path('water-type', av.WaterTypeList.as_view(),
         name="watertype-list"),

    path('water-type/<str:name>', av.WaterTypeList.as_view(),
         name="watertype-detail"),

    path('weighings', av.WeighingAPIListCreate.as_view(),
         name="weighing-create"),

    path('weighings/<uuid:pk>', av.WeighingAPIDetail.as_view(),
         name="weighing-detail"),
]
