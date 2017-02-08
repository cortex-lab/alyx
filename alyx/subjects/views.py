import uuid
from dal import autocomplete

from .models import *

from .serializers import *
from rest_framework import generics, permissions, renderers, viewsets


class SubjectList(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectListSerializer
    permission_classes = (permissions.IsAuthenticated,)


class SubjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'nickname'


class SubjectAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        print("hey")
        if not self.request.user.is_authenticated():
            return Subject.objects.none()

        qs = Subject.objects.all()

        line = self.forwarded.get('line', None)

        if line:
            qs = qs.filter(line=line)

        if self.q:
            qs = qs.filter(nickname__istartswith=self.q)

        return qs

    def get_result_value(self, result):
        # Bug fix:
        # https://github.com/yourlabs/django-autocomplete-light/pull/799
        out = super(SubjectAutocomplete, self).get_result_value(result)
        # Serialize the UUID field.
        if isinstance(out, uuid.UUID):
            out = str(out)
        return out
