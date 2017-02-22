
from .models import *

from .serializers import *
from rest_framework import generics, permissions
import django_filters
from django_filters.rest_framework import FilterSet


def _autoname_number(model, auto_name, field, interfix=''):
    objects = model.objects.filter(**{'%s__istartswith' % field:
                                      (auto_name + '_' + interfix)})
    names = sorted([getattr(obj, field) for obj in objects])
    if not names:
        i = 1
    else:
        i = int(names[-1].split('_')[-1]) + 1
    return i


def _autoname(model, auto_name, field, interfix=''):
    i = _autoname_number(model, auto_name, field, interfix)
    return '%s_%s%d' % (auto_name, interfix, i)


class SubjectFilter(FilterSet):
    alive = django_filters.BooleanFilter(name='alive')

    class Meta:
        model = Subject
        exclude = ['json']


class SubjectList(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = SubjectFilter
    filter_fields = ['__all__', 'alive']


class SubjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'nickname'
