from rest_framework import serializers
from .models import (Allele, Line, Litter, Source, Species, Strain, Subject, Zygosity,
                     Project)
from actions.serializers import (WeighingDetailSerializer,
                                 WaterAdministrationDetailSerializer,
                                 )
from django.contrib.auth import get_user_model
from misc.models import Lab

SUBJECT_LIST_SERIALIZER_FIELDS = ('nickname', 'url', 'id', 'responsible_user', 'birth_date',
                                  'age_weeks', 'death_date', 'species', 'sex', 'litter', 'strain',
                                  'source', 'line', 'projects', 'session_projects',
                                  'lab', 'genotype', 'description',
                                  'alive', 'reference_weight', 'last_water_restriction',
                                  'expected_water', 'remaining_water')


class _WaterRestrictionBaseSerializer(serializers.HyperlinkedModelSerializer):
    def get_expected_water(self, obj):
        return obj.water_control.expected_water()

    def get_remaining_water(self, obj):
        return obj.water_control.remaining_water()

    def get_reference_weight(self, obj):
        return obj.water_control.reference_weight()

    def get_last_water_restriction(self, obj):
        return obj.water_control.water_restriction_at()

    expected_water = serializers.SerializerMethodField()
    remaining_water = serializers.SerializerMethodField()
    reference_weight = serializers.SerializerMethodField()
    last_water_restriction = serializers.SerializerMethodField()


class WaterRestrictedSubjectListSerializer(_WaterRestrictionBaseSerializer):
    class Meta:
        model = Subject
        fields = ('nickname', 'url',
                  'expected_water',
                  'remaining_water',
                  'reference_weight',
                  'last_water_restriction',
                  )

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


class SubjectListSerializer(_WaterRestrictionBaseSerializer):
    genotype = serializers.ListField(
        source='zygosity_strings',
        required=False)

    responsible_user = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=get_user_model().objects.all(),
        required=False,
        default=serializers.CurrentUserDefault())

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

    session_projects = serializers.SlugRelatedField(
        read_only=True,
        slug_field='name',
        many=True,
        required=False,)

    source = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Source.objects.all(),
        allow_null=True,
        required=False)

    lab = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Lab.objects.all(),
        many=False,
        required=True,)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related(
            'responsible_user', 'species', 'strain', 'line', 'litter')
        queryset = queryset.prefetch_related('zygosity_set', 'zygosity_set__allele')
        return queryset

    class Meta:
        model = Subject
        fields = SUBJECT_LIST_SERIALIZER_FIELDS
        lookup_field = 'nickname'
        extra_kwargs = {'url': {'view_name': 'subject-detail', 'lookup_field': 'nickname'}}


class SubjectDetailSerializer(SubjectListSerializer, _WaterRestrictionBaseSerializer):
    weighings = WeighingDetailSerializer(many=True, read_only=True)
    water_administrations = WaterAdministrationDetailSerializer(many=True, read_only=True)
    genotype = ZygosityListSerializer(source='zygosity_set', many=True, read_only=True)

    class Meta:
        model = Subject
        fields = list(SUBJECT_LIST_SERIALIZER_FIELDS)
        fields.extend(['weighings', 'water_administrations'])
        lookup_field = 'nickname'
        extra_kwargs = {'url': {'view_name': 'subject-detail', 'lookup_field': 'nickname'}}


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    users = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=get_user_model().objects.all(),
        many=True,
        required=False,
        default=serializers.CurrentUserDefault(),)

    class Meta:
        model = Project
        fields = ('name', 'description', 'users')
        lookup_field = 'name'
        extra_kwargs = {'url': {'view_name': 'project-detail', 'lookup_field': 'name'}}
