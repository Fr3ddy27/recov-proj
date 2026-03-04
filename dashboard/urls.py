from django.urls import path
from . import views
from .views import create_project
#AUTHENTICATION
from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import create_project, DashboardLoginView
from django.contrib.auth.views import LogoutView
# FILE UPLOAD
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    #MAIN
    path('', views.overview, name='overview'),
    path('projects/', views.projects, name='projects'),
    path('location/', views.location, name='location'),
    path('timeline/', views.timeline, name='timeline'),
    #ATTACHEMENT DOWNLOAD
    path("gip/<int:pk>/download/", views.download_gip, name="download_gip"),
    #AUTHENTICATION
    path("login/", DashboardLoginView.as_view(), name="login"),
    path("logout/",LogoutView.as_view(next_page="overview"),name="logout",),
    #AREA COUNCIL
    path('api/area-councils/', views.area_councils_json, name='area_councils_json'),
    #DATA ENTRY
    path("data-entry/", create_project, name="data-entry"),
    #DATA UPDATE
    path("data-update/", views.recovery_projects_table, name="data-update"),
    path("api/recovery-projects/", views.recovery_projects_api_list, name="recovery_projects_api_list"),
    path("api/recovery-projects/<int:pk>/", views.recovery_projects_api_detail, name="recovery_projects_api_detail"),
    # CHILD TABLES API
    path("api/project-locations/list/<int:project_id>/", views.project_locations_api_list, name="project_locations_api_list"),
    path("api/project-locations/<int:pk>/", views.project_locations_api_detail, name="project_locations_api_detail"),
    path("api/project-locations/create/<int:project_id>/", views.project_locations_api_create, name="project_locations_api_create"),
    path("api/project-status-indicators/list/<int:project_id>/", views.project_status_indicators_api_list, name="project_status_indicators_api_list"),
    path("api/project-status-indicators/<int:pk>/", views.project_status_indicators_api_detail, name="project_status_indicators_api_detail"),
    path("api/project-status-indicators/create/<int:project_id>/", views.project_status_indicators_api_create, name="project_status_indicators_api_create"),
]
# MEDIA UPLOAD
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)