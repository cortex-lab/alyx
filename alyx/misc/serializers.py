from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from subjects.fields import SubjectField
from misc.models import (CageType, Enrichment, Food, Housing, HousingSubject, Lab, LabMember,
                         Note)
from data.models import DataRepository
from alyx.base import BaseSerializerContentTypeField


class NoteSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(
        read_only=False, slug_field='username', queryset=LabMember.objects.all())

    content_type = BaseSerializerContentTypeField(
        read_only=False, slug_field='model',
        queryset=ContentType.objects.filter(
            app_label__in=['actions', 'data', 'experiments', 'jobs', 'subjects']),
    )
    image = serializers.ImageField(use_url=True, required=False)

    def _check_related_object_exists(self):
        # makes sure the object referred to actually exists in the database
        ct = self.validated_data['content_type']
        ct.model_class().objects.get(id=self.validated_data['object_id'])

    def save(self, **kwargs):
        self._check_related_object_exists()
        # get optional parameter width of image in the request
        image_width = self.context['request'].data.get('width', None)
        if self.instance is not None:
            self.instance = self.update(self.instance, self.validated_data)
            assert self.instance is not None, '`update()` did not return an object instance.'
        else:
            self.instance = self.create(self.validated_data, image_width=image_width)
            assert self.instance is not None, '`create()` did not return an object instance.'
        return self.instance

    def create(self, validated_data, image_width=None):
        self._check_related_object_exists()
        obj = self.Meta.model.objects.create(**validated_data)
        obj.save(image_width=image_width)
        return obj

    class Meta:
        model = Note
        fields = ('id', 'user', 'date_time', 'content_type', 'object_id', 'text', 'image', 'json')


class UserSerializer(serializers.ModelSerializer):
    subjects_responsible = SubjectField(many=True)
    allowed_users = serializers.SlugRelatedField(
        many=True, queryset=LabMember.objects.all(), slug_field='username')

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.prefetch_related('subjects_responsible')
        return queryset

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'email', 'subjects_responsible',
            'lab', 'allowed_users', 'is_stock_manager'
        )


class LabSerializer(serializers.HyperlinkedModelSerializer):

    repositories = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=DataRepository.objects.all(),
        many=True,
        required=False)

    class Meta:
        model = Lab
        fields = ('name', 'institution', 'address', 'timezone', 'repositories',
                  'reference_weight_pct', 'zscore_weight_pct', 'json')
        lookup_field = 'name'
        extra_kwargs = {'url': {'view_name': 'lab-detail', 'lookup_field': 'name'}}


class HousingConditionsMixin(metaclass=serializers.SerializerMetaclass):
    """Housing conditions, by name for the related tables: a change creates a new Housing."""

    cage_type = serializers.SlugRelatedField(
        slug_field='name', queryset=CageType.objects.all(), allow_null=True, required=False)
    enrichment = serializers.SlugRelatedField(
        slug_field='name', queryset=Enrichment.objects.all(), allow_null=True, required=False)
    food = serializers.SlugRelatedField(
        slug_field='name', queryset=Food.objects.all(), allow_null=True, required=False)
    cage_cleaning_frequency_days = serializers.IntegerField(allow_null=True, required=False)
    light_cycle = serializers.ChoiceField(
        choices=Housing._meta.get_field('light_cycle').choices, allow_null=True, required=False)


CONDITION_FIELDS = ('cage_type', 'enrichment', 'food', 'cage_cleaning_frequency_days',
                    'light_cycle')


class HousingSerializer(HousingConditionsMixin, serializers.ModelSerializer):
    """
    A housing is a set of conditions for a cage. Patching the conditions of a housing with
    current subjects closes it and creates a new housing for those subjects: the response
    is then the new housing, with a new id.
    """

    url = serializers.HyperlinkedIdentityField(view_name='housing-detail')
    subjects = serializers.SerializerMethodField(help_text='Nicknames of the current subjects')
    lab = serializers.SerializerMethodField()

    def get_subjects(self, obj):
        return sorted(hs.subject.nickname for hs in obj.housing_subjects.all()
                      if hs.subject and hs.end_datetime is None)

    def get_lab(self, obj):
        lab = next((hs.subject.lab for hs in obj.housing_subjects.all()
                    if hs.subject and hs.subject.lab), None)
        return lab.name if lab else None

    def validate(self, attrs):
        if self.instance is not None and not self.instance.subjects_current().exists():
            raise serializers.ValidationError(
                'This housing has no current subjects and is a historical record.')
        return attrs

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related('cage_type', 'enrichment', 'food').prefetch_related(
            'housing_subjects__subject__lab')

    class Meta:
        model = Housing
        fields = ('url', 'id', 'cage_name', *CONDITION_FIELDS, 'subjects', 'lab', 'name', 'json')
        read_only_fields = ('cage_name',)


class HousingSubjectSerializer(serializers.ModelSerializer):
    subject = SubjectField(read_only=True)
    cage_name = serializers.CharField(source='housing.cage_name', read_only=True)
    lab = serializers.SlugRelatedField(source='subject.lab', slug_field='name', read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related('subject__lab', 'housing')

    class Meta:
        model = HousingSubject
        fields = ('id', 'housing', 'cage_name', 'subject', 'lab', 'start_datetime',
                  'end_datetime')
        read_only_fields = fields


class HousingSubjectCreateSerializer(HousingConditionsMixin, serializers.Serializer):
    """
    Puts subjects in a cage from a date. The current housing of that cage (in the lab of the
    subjects) is reused, or created if the cage has none. If conditions are given and differ
    from the current housing, it is closed and a new one is created, as when editing it.
    """

    cage_name = serializers.CharField(max_length=64)
    subjects = SubjectField(many=True, allow_empty=False)
    start_datetime = serializers.DateTimeField()
    lab = serializers.SlugRelatedField(
        slug_field='name', queryset=Lab.objects.all(), required=False,
        help_text='Only needed to disambiguate subjects sharing a nickname')

    def validate_subjects(self, subjects):
        if len({s.lab_id for s in subjects}) > 1:
            raise serializers.ValidationError('Subjects of a cage must be in the same lab.')
        if len({s.pk for s in subjects}) != len(subjects):
            raise serializers.ValidationError('Duplicate subjects.')
        return subjects

    @transaction.atomic
    def create(self, validated_data):
        subjects = validated_data['subjects']
        conditions = {k: validated_data[k] for k in CONDITION_FIELDS if k in validated_data}
        housing = Housing.objects.filter(
            cage_name=validated_data['cage_name'],
            housing_subjects__end_datetime__isnull=True,
            housing_subjects__subject__lab_id=subjects[0].lab_id,
        ).order_by('-housing_subjects__start_datetime').first()
        if housing is None:
            housing = Housing.objects.create(cage_name=validated_data['cage_name'], **conditions)
        elif any(getattr(housing, k) != v for k, v in conditions.items()):
            for k, v in conditions.items():
                setattr(housing, k, v)
            housing.save()  # closes the housing and creates a new one, see Housing.save
        current = set(housing.subjects_current().values_list('pk', flat=True))
        for subject in subjects:
            if subject.pk not in current:
                # this closes any other open assignment of the subject
                HousingSubject.objects.create(
                    subject=subject, housing=housing, start_datetime=validated_data['start_datetime'])
        return housing
