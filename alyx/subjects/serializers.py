from rest_framework import serializers
from .models import (Allele, Line, Litter, Source, Species, Strain, Subject, Zygosity,
                     Project)
from actions.serializers import (WeighingDetailSerializer,
                                 WaterAdministrationDetailSerializer,
                                 )
from django.contrib.auth import get_user_model
from actions import water
from data.models import DataRepository
from misc.models import Lab


class _WaterRestrictionBaseSerializer(serializers.HyperlinkedModelSerializer):

    def get_water_requirement_total(self, obj):
        return water.water_requirement_total(obj)

    def get_water_requirement_remaining(self, obj):
        return water.water_requirement_remaining(obj)

    def get_reference_weight(self, obj):
        w = water.reference_weighing(subject=obj)
        if w:
            return w.weight

    def get_last_water_restriction(self, obj):
        return water.last_water_restriction(subject=obj)


class WaterRestrictedSubjectListSerializer(_WaterRestrictionBaseSerializer):
    water_requirement_total = serializers.SerializerMethodField()
    water_requirement_remaining = serializers.SerializerMethodField()
    reference_weight = serializers.SerializerMethodField()
    last_water_restriction = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ('nickname', 'url', 'water_requirement_total', 'water_requirement_remaining',
                  'reference_weight', 'last_water_restriction')

        lookup_field = 'nickname'
        extra_kwargs = {'url': {'view_name': 'subject-detail', 'lookup_field': 'nickname'}}


class ZygosityListSerializer(serializers.ModelSerializer):
    ZYGOSITY_TYPES = (
        (0, 'Absent'),
        (1, 'Heterozygous'),
        (2, 'Homozygous'),
        (3, 'Present'),
    )

    zygosity = serializers.ChoiceField(choices=ZYGOSITY_TYPES)
    allele = serializers.SlugRelatedField(
        read_only=False,
        slug_field='nickname',
        queryset=Allele.objects.all(),
        required=False)

    class Meta:
        model = Zygosity
        fields = ('allele', 'zygosity')


class SubjectListSerializer(serializers.HyperlinkedModelSerializer):
    genotype = serializers.ListField(
        source='zygosity_strings',
        required=False)

    responsible_user = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=get_user_model().objects.all(),
        required=False)

    species = serializers.SlugRelatedField(
        read_only=False,
        slug_field='nickname',
        queryset=Species.objects.all(),
        allow_null=True,
        required=False)

    strain = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Strain.objects.all(),
        allow_null=True,
        required=False)

    line = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Line.objects.all(),
        allow_null=True,
        required=False)

    litter = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Litter.objects.all(),
        allow_null=True,
        required=False)

    projects = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Project.objects.all(),
        many=True,
        required=False,)

    lab = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Lab.objects.all(),
        many=False,
        required=False,)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related(
            'responsible_user', 'species', 'strain', 'line', 'litter')
        queryset = queryset.prefetch_related('zygosity_set', 'zygosity_set__allele')
        return queryset

    class Meta:
        model = Subject
        fields = ('nickname', 'id', 'url', 'responsible_user', 'birth_date', 'death_date',
                  'species', 'sex', 'litter', 'strain', 'line', 'description', 'lab',
                  'genotype', 'alive', 'projects')
        lookup_field = 'nickname'
        extra_kwargs = {'url': {'view_name': 'subject-detail', 'lookup_field': 'nickname'}}


class SubjectDetailSerializer(SubjectListSerializer, _WaterRestrictionBaseSerializer):
    weighings = WeighingDetailSerializer(many=True, read_only=True)
    water_administrations = WaterAdministrationDetailSerializer(many=True, read_only=True)
    genotype = ZygosityListSerializer(source='zygosity_set', many=True, read_only=True)

    projects = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Project.objects.all(),
        many=True,
        required=False,
    )

    water_requirement_total = serializers.SerializerMethodField()
    water_requirement_remaining = serializers.SerializerMethodField()
    reference_weight = serializers.SerializerMethodField()
    last_water_restriction = serializers.SerializerMethodField()

    def get_water_requirement_total(self, obj):
        return water.water_requirement_total(obj)

    def get_water_requirement_remaining(self, obj):
        return water.water_requirement_remaining(obj)

    source = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Source.objects.all(),
        allow_null=True,
        required=False)

    class Meta:
        model = Subject
        fields = ('nickname', 'url', 'id', 'responsible_user', 'birth_date', 'age_weeks',
                  'projects', 'lab',
                  'death_date', 'species', 'sex', 'litter', 'strain', 'source', 'line',
                  'description', 'weighings', 'water_administrations',
                  'genotype', 'water_requirement_total', 'water_requirement_remaining',
                  'reference_weight', 'last_water_restriction')
        lookup_field = 'nickname'
        extra_kwargs = {'url': {'view_name': 'subject-detail', 'lookup_field': 'nickname'}}


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    users = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=get_user_model().objects.all(),
        many=True,
        required=False)

    repositories = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=DataRepository.objects.all(),
        many=True,
        required=False)

    class Meta:
        model = Project
        fields = ('name', 'description', 'repositories', 'users')
        lookup_field = 'name'
        extra_kwargs = {'url': {'view_name': 'project-detail', 'lookup_field': 'name'}}
