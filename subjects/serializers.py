from rest_framework import serializers
from .models import Subject, Action, Weighing
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

class ActionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Action
        fields = ('__all__')

class WeighingSerializer(serializers.ModelSerializer):

    users = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username',
        many=True
     )

    subject = serializers.SlugRelatedField(
        slug_field='nickname',
        read_only=True)

    class Meta:
        model = Weighing
        fields = ('__all__')


class UserSerializer(serializers.ModelSerializer):
    subjects = serializers.PrimaryKeyRelatedField(many=True, queryset=Subject.objects.all())

    class Meta:
        model = User
        fields = ('id', 'username', 'snippets')
