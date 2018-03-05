from rest_framework import generics, permissions
import django_filters
from django_filters.rest_framework import FilterSet

from .models import Subject, Project
from .serializers import (SubjectListSerializer,
                          SubjectDetailSerializer,
                          WaterRestrictedSubjectListSerializer,
                          ProjectSerializer,
                          )


class SubjectFilter(FilterSet):
    alive = django_filters.BooleanFilter(name='death_date', lookup_expr='isnull')
    responsible_user = django_filters.CharFilter(name='responsible_user__username')
    stock = django_filters.BooleanFilter(name='responsible_user', method='filter_stock')
    water_restricted = django_filters.BooleanFilter(method='filter_water_restricted')

    def filter_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(responsible_user__id=5)
        else:
            return queryset.exclude(responsible_user__id=5)

    def filter_water_restricted(self, queryset, name, value):
        if value is True:
            return queryset.extra(where=['''
                subjects_subject.id IN
                (SELECT subject_id FROM actions_waterrestriction
                WHERE end_time IS NULL)
                '''])
        else:
            return queryset.extra(where=['''
                subjects_subject.id NOT IN
                (SELECT subject_id FROM actions_waterrestriction
                WHERE end_time IS NULL)
                '''])

    class Meta:
        model = Subject
        exclude = ['json']


class SubjectList(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    queryset = SubjectListSerializer.setup_eager_loading(queryset)
    serializer_class = SubjectListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = SubjectFilter


class SubjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'nickname'


class ProjectList(generics.ListCreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class ProjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class WaterRestrictedSubjectList(generics.ListAPIView):
    queryset = Subject.objects.all().extra(where=['''
        subjects_subject.id IN
        (SELECT subject_id FROM actions_waterrestriction
         WHERE end_time IS NULL)'''])
    serializer_class = WaterRestrictedSubjectListSerializer
    permission_classes = (permissions.IsAuthenticated,)
