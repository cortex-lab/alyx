from django.urls import path
import actions.views as av

urlpatterns = [
    path('admin-actions/weighing-plot/<uuid:subject_id>',
         av.weighing_plot,
         name='weighing-plot',
         ),

    path('admin-actions/water-history/<uuid:subject_id>',
         av.WaterHistoryListView.as_view(),
         name='water-history',
         ),

    path('admin-actions/training/',
         av.TrainingListView.as_view(),
         name='training',
         ),

    path('admin-actions/training/<date>',
         av.TrainingListView.as_view(),
         name='training',
         ),

    path('admin-actions/subject-history/<uuid:subject_id>',
         av.SubjectHistoryListView.as_view(),
         name='subject-history',
         ),

    path('locations', av.LabLocationList.as_view(), name="location-list"),

    path('locations/<str:name>', av.LabLocationAPIDetail.as_view(),
         name="location-detail"),

    path('procedures', av.ProcedureTypeList.as_view(), name="procedures-list"),

    path('sessions', av.SessionAPIList.as_view(), name="session-list"),

    path('sessions/<uuid:pk>', av.SessionAPIDetail.as_view(),
         name="session-detail"),

    path('surgeries', av.SurgeriesList.as_view(), name='surgeries-list'),

    path('surgeries/<uuid:pk>', av.SurgeriesAPIDetail.as_view(), name='surgeries-detail'),

    path('water-administrations', av.WaterAdministrationAPIListCreate.as_view(),
         name="water-administration-create"),

    path('water-administrations/<uuid:pk>', av.WaterAdministrationAPIDetail.as_view(),
         name="water-administration-detail"),

    path('water-requirement/<str:nickname>', av.WaterRequirement.as_view(),
         name='water-requirement'),

    path('water-restriction', av.WaterRestrictionList.as_view(),
         name='water-restriction-list'),

    path('water-type', av.WaterTypeList.as_view(),
         name="watertype-list"),

    path('water-type/<str:name>', av.WaterTypeList.as_view(),
         name="watertype-detail"),

    path('weighings', av.WeighingAPIListCreate.as_view(),
         name="weighing-create"),

    path('weighings/<uuid:pk>', av.WeighingAPIDetail.as_view(),
         name="weighing-detail"),


]
