from django.conf.urls import include, url
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

user_list = mv.UserViewSet.as_view({
    'get': 'list'
})

user_detail = mv.UserViewSet.as_view({
    'get': 'retrieve'
})

admin.site.site_header = 'Alyx'

urlpatterns = [
    url(r'^$', mv.api_root),

    # Built-in docs:
    # url(r'^docs/', include_docs_urls(title='Alyx REST API documentation')),
    url(r'^docs/', include('rest_framework_docs.urls')),

    url(r'^auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^auth-token', authv.obtain_auth_token),


    url(r'^weighings$', av.WeighingAPIListCreate.as_view(),
        name="weighing-create"),

    url(r'^weighings/(?P<pk>[-_\w].+)$', av.WeighingAPIDetail.as_view(),
        name="weighing-detail"),


    url(r'^water-administrations$', av.WaterAdministrationAPIListCreate.as_view(),
        name="water-administration-create"),

    url(r'^water-administrations/(?P<pk>[-_\w].+)$', av.WaterAdministrationAPIDetail.as_view(),
        name="water-administration-detail"),


    url(r'^subjects$', sv.SubjectList.as_view(),
        name="subject-list"),

    url(r'^subjects/(?P<nickname>[-._~\w]+)$', sv.SubjectDetail.as_view(),
        name="subject-detail"),


    url(r'^projects$', sv.ProjectList.as_view(),
        name="project-list"),

    url(r'^projects/(?P<name>[-_\w].*)$', sv.ProjectDetail.as_view(),
        name="project-detail"),


    url(r'^sessions$', av.SessionAPIList.as_view(),
        name="session-list"),

    url(r'^sessions/(?P<pk>[-_\w].+)$', av.SessionAPIDetail.as_view(),
        name="session-detail"),


    url(r'^exp-metadata$', dv.ExpMetadataList.as_view(),
        name="exp-metadata-list"),

    url(r'^exp-metadata/(?P<pk>[-_\w].+)$', dv.ExpMetadataDetail.as_view(),
        name="exp-metadata-detail"),


    url(r'^data-repository-type$', dv.DataRepositoryTypeList.as_view(),
        name="datarepositorytype-list"),

    url(r'^data-repository-type/(?P<name>[-_\w].*)$', dv.DataRepositoryTypeDetail.as_view(),
        name="datarepositorytype-detail"),


    url(r'^data-repository$', dv.DataRepositoryList.as_view(),
        name="datarepository-list"),

    url(r'^data-repository/(?P<name>[-_\w].*)$', dv.DataRepositoryDetail.as_view(),
        name="datarepository-detail"),


    url(r'^data-formats$', dv.DataFormatList.as_view(),
        name="dataformat-list"),

    url(r'^data-formats/(?P<name>[-_\w].*)$', dv.DataFormatDetail.as_view(),
        name="dataformat-detail"),


    url(r'^dataset-types$', dv.DatasetTypeList.as_view(),
        name="datasettype-list"),

    url(r'^dataset-types/(?P<name>[-_\w].*)$', dv.DatasetTypeDetail.as_view(),
        name="datasettype-detail"),


    url(r'^datasets$', dv.DatasetList.as_view(),
        name="dataset-list"),

    url(r'^datasets/(?P<pk>[-_\w].+)$', dv.DatasetDetail.as_view(),
        name="dataset-detail"),


    url(r'^files$', dv.FileRecordList.as_view(),
        name="filerecord-list"),

    url(r'^files/(?P<pk>[-_\w].+)$', dv.FileRecordDetail.as_view(),
        name="filerecord-detail"),


    url(r'^timescales$', dv.TimescaleList.as_view(),
        name="timescale-list"),

    url(r'^timescales/(?P<pk>[-_\w].+)$', dv.TimescaleDetail.as_view(),
        name="timescale-detail"),


    url(r'^register-file$', register_file,
        name="register-file"),


    url(r'^users$', user_list,
        name='user-list'),

    url(r'^users/(?P<username>[-_\w].*)$', user_detail,
        name='user-detail'),


    url(r'^water-restricted-subjects$', sv.WaterRestrictedSubjectList.as_view(),
        name="water-restricted-subject-list"),

    url(r'^water-requirement/$', av.WaterRequirement.as_view(),
        name='water-requirement'),

    url(r'^water-requirement/(?P<nickname>[-._~\w]+)$', av.WaterRequirement.as_view(),
        name='water-requirement-detail'),


    url(r'^admin/', include(admin.site.urls)),
    url(r'^admin-subjects/', include('subjects.urls')),
    url(r'^admin-actions/', include('actions.urls')),

]
