from django.urls import path
import data.views as dv


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

check_protected = dv.ProtectedFileViewSet.as_view({
    'get': 'list'
})

urlpatterns = [
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

    path('revisions', dv.RevisionList.as_view(),
         name="revision-list"),

    path('revisions/<str:name>', dv.RevisionDetail.as_view(),
         name="revision-detail"),

    path('tags', dv.TagList.as_view(),
         name="tag-list"),

    path('tags/<str:name>', dv.TagDetail.as_view(),
         name="tag-detail"),

    path('datasets', dv.DatasetList.as_view(),
         name="dataset-list"),

    path('datasets/<uuid:pk>', dv.DatasetDetail.as_view(),
         name="dataset-detail"),

    path('dataset-types', dv.DatasetTypeList.as_view(),
         name="datasettype-list"),

    path('dataset-types/<str:name>', dv.DatasetTypeDetail.as_view(),
         name="datasettype-detail"),

    path('downloads', dv.DownloadList.as_view(),
         name="download-list"),

    path('downloads/<uuid:pk>', dv.DownloadDetail.as_view(),
         name="download-detail"),

    path('files', dv.FileRecordList.as_view(),
         name="filerecord-list"),

    path('files/<uuid:pk>', dv.FileRecordDetail.as_view(),
         name="filerecord-detail"),

    path('new-download', new_download, name='new-download'),

    path('register-file', register_file,
         name="register-file"),

    path('sync-file-status', sync_file_status,
         name="sync-file-status"),

    path('check-protected', check_protected,
         name="check-protected"),

]
