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
    return Response({
        # 'users': reverse('user-list', request=request, format=format),
        'subjects': reverse('subject-list', request=request, format=format)
    })

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class SubjectViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field='nickname'

    @detail_route(renderer_classes=[renderers.StaticHTMLRenderer])
    def highlight(self, request, *args, **kwargs):
        subject = self.get_object()
        return Response(subject.highlighted)

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
