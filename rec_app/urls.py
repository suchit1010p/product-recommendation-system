from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search_view, name='search'),
    path('ajax_search/', views.ajax_search, name='ajax_search'),
]
