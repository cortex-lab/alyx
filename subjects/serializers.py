from rest_framework import serializers
from .models import Subject
from django.contrib.auth.models import User

class SubjectSerializer(serializers.ModelSerializer):

    responsible_user = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username'
     )

    class Meta:
        model = Subject
        fields = ('__all__')
        lookup_field = 'nickname'


class UserSerializer(serializers.ModelSerializer):
    subjects_responsible = serializers.SlugRelatedField(many=True, queryset=Subject.objects.all(), slug_field='nickname')

    class Meta:
        model = User
        fields = ('id', 'username', 'subjects_responsible')
