from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from subjects.models import Subject
from misc.models import Lab, Note, LabMember
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

    class Meta:
        model = Note
        fields = ('id', 'user', 'date_time', 'content_type', 'object_id', 'text', 'image')


class UserSerializer(serializers.ModelSerializer):
    subjects_responsible = serializers.SlugRelatedField(
        many=True, queryset=Subject.objects.all(), slug_field='nickname')

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.prefetch_related('subjects_responsible')
        return queryset

    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'email', 'subjects_responsible', 'lab')


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
