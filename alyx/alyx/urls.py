import traceback
from django.conf.urls import include
from django.urls import path
from django.contrib import admin
from django.shortcuts import render
from rest_framework.authtoken import views as authv
from rest_framework.documentation import include_docs_urls

admin.site.site_header = 'Alyx'

urlpatterns = [
    path('', include('misc.urls')),
    path('', include('experiments.urls')),
    path('', include('jobs.urls')),
    path('', include('actions.urls')),
    path('', include('data.urls')),
    path('', include('subjects.urls')),
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('auth-token', authv.obtain_auth_token),
    path('docs/', include_docs_urls(title='Alyx REST API documentation')),
]

# this is an optional app
try:
    urlpatterns += [path('ibl_reports/', include('ibl_reports.urls')), ]
except ModuleNotFoundError:
    pass


def handler500(request):
    ctx = {
        'request': request.path,
        'traceback': traceback.format_exc()
    }
    return render(request, 'error_500.html', ctx)
