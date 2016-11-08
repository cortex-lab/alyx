from django.shortcuts import render

from .models import *

from .serializers import *
from rest_framework import generics, permissions, renderers, viewsets

# class SubjectViewSet(viewsets.ModelViewSet):
#     """
#     From here, you can use REST `list`, `create`, `retrieve`,`update` and `destroy` actions on subjects.
#     """
#     queryset = Subject.objects.all()
#     serializer_class = SubjectSerializer


class SubjectList(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectListSerializer
    permission_classes = (permissions.IsAuthenticated,)


class SubjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field='nickname'