from rest_framework import serializers
from .models import *
from actions.serializers import *
from django.contrib.auth.models import User

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
        slug_field='informal_name',
        queryset=Allele.objects.all(),
        required=False)

    class Meta:
        model = Zygosity
        fields = ('allele', 'zygosity')


class SubjectListSerializer(serializers.HyperlinkedModelSerializer):

    genotype = serializers.ListField(source='zygosity_strings')

    responsible_user = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=User.objects.all(),
        required=False)

    species = serializers.SlugRelatedField(
        read_only=False,
        slug_field='display_name',
        queryset=Species.objects.all(),
        allow_null=True,
        required=False)

    cage = serializers.SlugRelatedField(
        read_only=False,
        slug_field='cage_label',
        queryset=Cage.objects.all(),
        allow_null=True,
        required=False)

    strain = serializers.SlugRelatedField(
        read_only=False,
        slug_field='descriptive_name',
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
        slug_field='descriptive_name',
        queryset=Litter.objects.all(),
        allow_null=True,
        required=False)

    class Meta:
        model = Subject
        fields = ('nickname', 'url', 'responsible_user', 'birth_date', 'death_date',
                  'species', 'cage', 'sex', 'litter', 'strain', 'line', 'notes', 'genotype', 'alive')
        lookup_field = 'nickname'
        extra_kwargs = {'url': {'view_name': 'subject-detail', 'lookup_field': 'nickname'}}


class SubjectDetailSerializer(SubjectListSerializer):

    weighings = WeighingListSerializer(many=True, read_only=True)
    water_administrations = WaterAdministrationListSerializer(many=True, read_only=True)
    actions_experiments = ExperimentListSerializer(many=True, read_only=True)
    genotype = ZygosityListSerializer(source='zygosity_set', many=True, read_only=True)

    source = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Source.objects.all(),
        allow_null=True,
        required=False)

    alive = serializers.BooleanField()

    class Meta:
        model = Subject
        fields = ('nickname', 'url', 'responsible_user', 'birth_date', 'age_weeks', 'death_date',
                  'species', 'cage', 'sex', 'litter', 'strain', 'source', 'line', 'notes',
                  'actions_experiments', 'weighings', 'water_administrations', 'genotype', 'alive')
        lookup_field = 'nickname'
        extra_kwargs = {'url': {'view_name': 'subject-detail', 'lookup_field': 'nickname'}}



