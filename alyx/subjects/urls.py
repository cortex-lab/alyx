from django.urls import path
import subjects.views as sv

urlpatterns = [
    path('projects', sv.ProjectList.as_view(),
         name="project-list"),

    path('projects/<str:name>', sv.ProjectDetail.as_view(),
         name="project-detail"),

    path('water-restricted-subjects', sv.WaterRestrictedSubjectList.as_view(),
         name="water-restricted-subject-list"),

    path('subjects', sv.SubjectList.as_view(),
         name="subject-list"),

    path('subjects/<str:nickname>', sv.SubjectDetail.as_view(),
         name="subject-detail"),
]
