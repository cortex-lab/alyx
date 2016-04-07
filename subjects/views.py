from django.shortcuts import render
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic.list import MultipleObjectMixin
from django.views.generic.detail import SingleObjectMixin
from subjects.models import Subject, Action, Weighing

from .forms import SubjectForm

from subjects.serializers import SubjectSerializer, ActionSerializer, WeighingSerializer
from rest_framework import generics

# Create your views here.

# def post_new(request):
#     if request.method == "POST":
#         form = SubjectForm(request.POST)
#         if form.is_valid():

#             # commit=False means the form doesn't save at this time.
#             # commit defaults to True which means it normally saves.
#             model_instance = form.save(commit=False)
#             model_instance.timestamp = timezone.now()
#             model_instance.save()
#             return redirect('victory')
#     else:
#         form = SubjectForm()

#     return render(request, "subject_edit.html", {'form': form})

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

class SubjectAPIList(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer

class SubjectAPIDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    lookup_field='nickname'

class ActionAPIList(generics.ListCreateAPIView):
    queryset = Action.objects.all()
    serializer_class = ActionSerializer

class ActionAPIDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Action.objects.all()
    serializer_class = ActionSerializer

class WeighingAPIList(generics.ListCreateAPIView):
    serializer_class = WeighingSerializer

    def get_queryset(self):
    	queryset = Weighing.objects.all()
    	queryset = queryset.filter(subject__nickname=self.kwargs['nickname']).order_by('start_date_time')
    	return queryset