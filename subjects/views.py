from django.shortcuts import render
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic.list import MultipleObjectMixin
from django.views.generic.detail import SingleObjectMixin
from .models import Subject, Action, Weighing
from django.contrib.auth.models import User

from .serializers import SubjectSerializer, ActionSerializer, WeighingSerializer, UserSerializer

from rest_framework import generics, permissions, renderers, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view, detail_route
from rest_framework.reverse import reverse

@api_view(['GET'])
def api_root(request, format=None):
    """
    Welcome to Alyx's API! At the moment, there is read-only support for
    unauthenticated user lists, and authenticated read-write subject metadata
    and weighings. This should be reasonably self-documented; standard REST options
    are supported by sending an `OPTIONS /api/subjects/` for example. This is in alpha
    and endpoints are subject to change at short notice!
    """
    return Response({
        'users': reverse('user-list', request=request, format=format),
        'subjects': reverse('subject-list', request=request, format=format),
        'actions': reverse('action-list', request=request, format=format)
    })

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lists all users with the subjects which they are responsible for.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field='username'

class SubjectViewSet(viewsets.ModelViewSet):
    """
    From here, you can use REST `list`, `create`, `retrieve`,`update` and `destroy` actions on subjects.
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field='nickname'

class ActionViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` actions.
    This API will probably change.
    """
    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    permission_classes = (permissions.IsAuthenticated,)

class ActionAPIList(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Action.objects.all()
    serializer_class = ActionSerializer

class ActionAPIDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Action.objects.all()
    serializer_class = ActionSerializer

class WeighingAPIList(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WeighingSerializer

    def get_queryset(self):
    	queryset = Weighing.objects.all()
    	queryset = queryset.filter(subject__nickname=self.kwargs['nickname']).order_by('start_date_time')
    	return queryset

    def perform_create(self, serializer):
        # Lookup UUID of subject's nickname
        subject = Subject.objects.get(nickname=self.kwargs['nickname'])
        serializer.save(subject_id=subject.id)

#
#  Main site views
#

class Overview(ListView):
    model=Subject
    template_name='index.html'

class SubjectsList(ListView):
    model=Subject
    template_name='subjects_list.html'
    title='Subjects'

class SubjectView(DetailView):
    model=Subject
    template_name='subject.html'
    slug_field='nickname'

class Overview(ListView):
    model=Subject
    template_name='index.html'
