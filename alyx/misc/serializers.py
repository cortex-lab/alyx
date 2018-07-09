from rest_framework import serializers
from subjects.models import Subject
from django.contrib.auth import get_user_model


class UserSerializer(serializers.ModelSerializer):
    subjects_responsible = serializers.SlugRelatedField(
        many=True, queryset=Subject.objects.all(), slug_field='nickname')

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.prefetch_related('subjects_responsible')
        return queryset

    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'email', 'subjects_responsible')
