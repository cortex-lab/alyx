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

admin.site.site_header = 'LabDB'

urlpatterns = [
    url(r'^$', views.SubjectsCards.as_view(), name='subjectcardsview'),
    url(r'^list$', views.SubjectsList.as_view(), name='subjectlistview'),
    url(r'^gantt$', views.SubjectsGantt.as_view(), name='subjectganttview'),
    url(r'^subject/(?P<slug>[-_\w]+)/$', views.SubjectView.as_view(), name='itemview'),
    url(r'^admin/', include(admin.site.urls)),
]
