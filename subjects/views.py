from django.shortcuts import render
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic.list import MultipleObjectMixin
from django.views.generic.detail import SingleObjectMixin
from subjects.models import Subject, Action

# Create your views here.

class SubjectView(DetailView):
	model=Subject
	template_name='subject.html'
	slug_field='nickname'

class SubjectGantt(ListView):
	model=Subject
	template_name='subjects_gantt.html'