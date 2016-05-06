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
from actions.views import ActionViewSet

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

action_list = actions_views.ActionViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
action_detail = actions_views.ActionViewSet.as_view({
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

    url(r'^subjects/(?P<nickname>[-_\w].+)/weighings/$', actions_views.WeighingAPIList.as_view()),

    url(r'^subjects/$', subject_list, name="subject-list"),
    url(r'^subjects/(?P<nickname>[-_\w].+)/$', subject_detail, name="subject-detail"),

    url(r'^users/$', user_list, name='user-list'),
    url(r'^users/(?P<username>[-_\w].+)/$', user_detail, name='user-detail'),

    url(r'^actions/$', action_list, name='action-list'),
    url(r'^actions/(?P<pk>[-_\w].+)/$', action_detail, name='action-detail'),

    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^docs/', include('rest_framework_docs.urls')),
]
