from rest_framework import serializers
from subjects.models import Subject, Action, Weighing

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