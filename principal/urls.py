from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'), 
    path('panel/', views.homePanel, name='homePanel'), 
    path('logout/', views.logout_view, name='logout'),
    path('registrarse/', views.register_user, name='register'),
]