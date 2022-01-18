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
