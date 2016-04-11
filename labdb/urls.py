"""labdb URL Configuration

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
from subjects import views

admin.site.site_header = 'Alyx'

urlpatterns = [
    url(r'^$', views.Overview.as_view(), name='overview'),
    url(r'^list$', views.SubjectsList.as_view(), name='subjectlistview'),
    url(r'^subject/(?P<slug>[-_\w].+)/$', views.SubjectView.as_view(), name='subjectview'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^api/subjects/(?P<nickname>[-_\w].+)/weighings/$', views.WeighingAPIList.as_view()),
    url(r'^api/subjects/$', views.SubjectAPIList.as_view()),
    url(r'^api/subjects/(?P<nickname>[-_\w].+)/$', views.SubjectAPIDetail.as_view()),
    url(r'^api/actions/$', views.ActionAPIList.as_view()),
    url(r'^api/actions/(?P<pk>[-_\w].+)/$', views.ActionAPIDetail.as_view()),

]
