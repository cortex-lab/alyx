from rest_framework import serializers
from .models import Subject

class SubjectSerializer(serializers.ModelSerializer):

    responsible_user = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username'
     )

    species = serializers.SlugRelatedField(
    	read_only=True,
    	slug_field='display_name')

    cage = serializers.SlugRelatedField(
    	read_only=True,
    	slug_field='cage_label')

    class Meta:
        model = Subject
        fields = ('__all__')
        lookup_field = 'nickname'


