"""alyx URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import include, url
from django.contrib import admin
from rest_framework.authtoken import views as av
from rest_framework import renderers

from subjects import views as subjects_views

from actions import views as actions_views

from data import views as data_views
from data.views import DatasetViewSet, FileRecordViewSet

from misc import views as misc_views
from misc.views import UserViewSet, api_root

dataset_list = data_views.DatasetViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
dataset_detail = data_views.DatasetViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

filerecord_list = data_views.FileRecordViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
filerecord_detail = data_views.FileRecordViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

user_list = misc_views.UserViewSet.as_view({
    'get': 'list'
})
user_detail = misc_views.UserViewSet.as_view({
    'get': 'retrieve'
})

admin.site.site_header = 'Alyx'

urlpatterns = [
    url(r'^$', misc_views.api_root),
    url(r'^auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^auth-token/', av.obtain_auth_token),

    url(r'^weighings/$', actions_views.WeighingAPICreate.as_view(), name="weighing-create"),
    url(r'^weighings/(?P<pk>[-_\w].+)/$', actions_views.WeighingAPIDetail.as_view(), name="weighing-detail"),

    url(r'^water-administrations/$', actions_views.WaterAdministrationAPICreate.as_view(), name="water-administration-create"),
    url(r'^water-administrations/(?P<pk>[-_\w].+)/$', actions_views.WaterAdministrationAPIDetail.as_view(), name="water-administration-detail"),

    url(r'^subjects/$', subjects_views.SubjectList.as_view(), name="subject-list"),
    url(r'^subjects/(?P<nickname>[^/].+)/$', subjects_views.SubjectDetail.as_view(), name="subject-detail"),

    url(r'^experiments/$', actions_views.ExperimentAPIList.as_view(), name="experiment-list"),
    url(r'^experiments/(?P<pk>[-_\w].+)/$', actions_views.ExperimentAPIDetail.as_view(), name="experiment-detail"),

    url(r'^datasets/$', dataset_list, name="dataset-list"),
    url(r'^datasets/(?P<pk>[-_\w].+)/$', dataset_detail, name="dataset-detail"),

    url(r'^files/$', filerecord_list, name="filerecord-list"),
    url(r'^files/(?P<pk>[-_\w].+)/$', filerecord_detail, name="filerecord-detail"),

    url(r'^users/$', user_list, name='user-list'),
    url(r'^users/(?P<username>[-_\w].+)/$', user_detail, name='user-detail'),

    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),
]
