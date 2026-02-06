from rest_framework import generics
import django_filters

from django.utils import timezone

from alyx.base import BaseFilterSet, rest_permission_classes
from .models import Subject, Project
from .serializers import (SubjectListSerializer,
                          SubjectDetailSerializer,
                          WaterRestrictedSubjectListSerializer,
                          ProjectSerializer,
                          )


class SubjectFilter(BaseFilterSet):
    alive = django_filters.BooleanFilter('death_date', method='filter_alive')
    responsible_user = django_filters.CharFilter('responsible_user__username')
    stock = django_filters.BooleanFilter('responsible_user', method='filter_stock')
    water_restricted = django_filters.BooleanFilter(method='filter_water_restricted')
    lab = django_filters.CharFilter('lab__name')
    project = django_filters.CharFilter('projects__name')

    def filter_alive(self, queryset, name, value):
        if value is True:
            return queryset.exclude(death_date__lte=timezone.now().date())
        else:
            return queryset.filter(death_date__lte=timezone.now().date())

    def filter_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(responsible_user__is_stock_manager=True)
        else:
            return queryset.exclude(responsible_user__is_stock_manager=True)

    def filter_water_restricted(self, queryset, name, value):
        if value is True:
            qs = queryset.extra(where=['''
                subjects_subject.id IN
                (SELECT subject_id FROM actions_waterrestriction
                WHERE end_time IS NULL)
                '''])
        else:
            qs = queryset.extra(where=['''
                subjects_subject.id NOT IN
                (SELECT subject_id FROM actions_waterrestriction
                WHERE end_time IS NULL)
                '''])
        return qs.exclude(death_date__lte=timezone.now().date())

    class Meta:
        model = Subject
        exclude = []


class SubjectList(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    queryset = SubjectListSerializer.setup_eager_loading(queryset)
    serializer_class = SubjectListSerializer
    permission_classes = rest_permission_classes()
    filterset_class = SubjectFilter


class SubjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectDetailSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'nickname'


class ProjectList(generics.ListCreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


class ProjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


class WaterRestrictedSubjectList(generics.ListAPIView):
    queryset = Subject.objects.all().extra(where=['''
        subjects_subject.id IN
        (SELECT subject_id FROM actions_waterrestriction
         WHERE end_time IS NULL)'''])
    serializer_class = WaterRestrictedSubjectListSerializer
    permission_classes = rest_permission_classes()
