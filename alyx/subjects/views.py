from django.shortcuts import render

from .models import *

from .serializers import SubjectSerializer
from rest_framework import generics, permissions, renderers, viewsets

class SubjectViewSet(viewsets.ModelViewSet):
    """
    From here, you can use REST `list`, `create`, `retrieve`,`update` and `destroy` actions on subjects.
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field='nickname'
