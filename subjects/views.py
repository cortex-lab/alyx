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

class SubjectsGantt(ListView):
	model=Subject
	template_name='subjects_gantt.html'
	title='Subjects Gantt'

class SubjectsList(ListView):
	model=Subject
	template_name='subjects_list.html'

class SubjectsCards(ListView):
	model=Subject
	template_name='subjects_cards.html'