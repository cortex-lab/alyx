from django.shortcuts import render
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic.list import MultipleObjectMixin
from django.views.generic.detail import SingleObjectMixin
from subjects.models import Subject, Action

from .forms import SubjectForm

# Create your views here.

def post_new(request):
    if request.method == "POST":
        form = SubjectForm(request.POST)
        if form.is_valid():

            # commit=False means the form doesn't save at this time.
            # commit defaults to True which means it normally saves.
            model_instance = form.save(commit=False)
            model_instance.timestamp = timezone.now()
            model_instance.save()
            return redirect('victory')
    else:
        form = SubjectForm()

    return render(request, "subject.html", {'form': form})

class SubjectView(DetailView):
	model=Subject
	template_name='subject.html'
	slug_field='nickname'

class SubjectsList(ListView):
	model=Subject
	template_name='subjects_list.html'
	title='Subjects'

class Overview(ListView):
	model=Subject
	template_name='index.html'