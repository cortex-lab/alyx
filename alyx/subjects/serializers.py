from rest_framework import serializers
from .models import Subject, Species, Cage
from django.contrib.auth.models import User

class SubjectSerializer(serializers.ModelSerializer):

    responsible_user = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=User.objects.all())

    species = serializers.SlugRelatedField(
    	read_only=False,
    	slug_field='display_name',
    	queryset=Species.objects.all(),
    	allow_null = True)

    cage = serializers.SlugRelatedField(
    	read_only=False,
    	slug_field='cage_label',
    	queryset=Cage.objects.all(),
    	allow_null = True)

    class Meta:
        model = Subject
        fields = ('__all__')
        lookup_field = 'nickname'


