import datetime
import json
import uuid
from django.db import connection
from django.http import HttpResponse


def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]


def custom_sql(query):
    with connection.cursor() as cursor:
        cursor.execute(query)
        return {"result": dictfetchall(cursor)}


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return obj.hex
        elif isinstance(obj, datetime.date):
            serial = obj.isoformat()
            return serial
        return json.JSONEncoder.default(self, obj)


def raw_views(request):
    if not request.user.is_authenticated:
        return HttpResponse("")
    q = request.GET.get('q', None)
    r = custom_sql(q)
    data = json.dumps(r, cls=CustomEncoder)
    return HttpResponse(data)
