
from .models import *
from .serializers import *
from rest_framework import generics, permissions
import django_filters
from django_filters.rest_framework import FilterSet


class SubjectFilter(FilterSet):
    alive = django_filters.BooleanFilter(name='death_date', lookup_expr='isnull')
    responsible_user = django_filters.CharFilter(name='responsible_user__username')

    class Meta:
        model = Subject
        exclude = ['json']


class SubjectList(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = SubjectFilter


class SubjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'nickname'
