from django.http import HttpResponse

from django.template import loader


import datetime

def current_datetime(request):
    now = datetime.datetime.now()
    template = loader.get_template('reports/simple.html')
    context = {'now': now}
    return HttpResponse(template.render(context, request))
