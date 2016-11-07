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
from subjects.views import SubjectViewSet

from actions import views as actions_views
from actions.views import ExperimentViewSet

from data import views as data_views
from data.views import DatasetViewSet

from misc import views as misc_views
from misc.views import UserViewSet, api_root

subject_list = subjects_views.SubjectViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
subject_detail = subjects_views.SubjectViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

action_list = actions_views.ExperimentViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
action_detail = actions_views.ExperimentViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

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

    url(r'^subjects/(?P<nickname>[-_\w].+)/weights/$', actions_views.WeighingAPIList.as_view(), name="weights-list"),
    url(r'^subjects/(?P<nickname>[-_\w].+)/water/$', actions_views.WaterAdministrationAPIList.as_view(), name="water-list"),

    url(r'^subjects/$', subject_list, name="subject-list"),
    url(r'^subjects/(?P<nickname>[-_\w].+)/$', subject_detail, name="subject-detail"),

    url(r'^datasets/$', dataset_list, name="dataset-list"),
    url(r'^datasets/(?P<pk>[-_\w].+)/$', dataset_detail, name="dataset-detail"),

    url(r'^users/$', user_list, name='user-list'),
    url(r'^users/(?P<username>[-_\w].+)/$', user_detail, name='user-detail'),

    url(r'^experiments/$', action_list, name='action-list'),
    url(r'^experiments/(?P<pk>[-_\w].+)/$', action_detail, name='action-detail'),

    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),
]
