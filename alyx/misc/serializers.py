from rest_framework import serializers
from subjects.models import Subject
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    subjects_responsible = serializers.SlugRelatedField(
        many=True, queryset=Subject.objects.all(), slug_field='nickname')

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'subjects_responsible')
