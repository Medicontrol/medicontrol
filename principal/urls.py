from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('homePanel/', views.homePanel, name='homePanel'),
    path('crear/', views.crear_medicamento, name='crear_medicamento'),
    path('eliminar/<int:id>/', views.eliminar_medicamento, name='eliminar_medicamento'),
    path('register/', views.register_user, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('tomar/<int:medicamento_id>/', views.tomar_medicamento, name='tomar_medicamento'),
    path('posponer/<int:medicamento_id>/', views.posponer_medicamento, name='posponer_medicamento'),
    path('historial/', views.historial, name='historial'),
    path('historial/pdf/', views.historial_pdf, name='historial_pdf'),
    path('guardar-token/', views.guardar_token_fcm, name='guardar_token_fcm'),
    path('verificar-tomas/', views.verificar_tomas, name='verificar_tomas'),
    path('editar/<int:id>/', views.editar_medicamento, name='editar_medicamento'),
    path('sugerencias/', views.sugerutinas, name='sugerutinas'),
    path('registrar-dormir/', views.registrar_dormir, name='registrar_dormir'),
    path('registrar-despertar/', views.registrar_despertar, name='registrar_despertar'),
    path('red-familiar/', views.red_familiar, name='red_familiar'),
    path('actualizar-telegram/', views.actualizar_telegram, name='actualizar_telegram'),
    path('historial-familiar/<int:familiar_id>/', views.historial_familiar, name='historial_familiar'),
    path('desvincular-familiar/', views.desvincular_familiar, name='desvincular_familiar'),
    path('debug/', views.debug_usuario, name='debug_usuario'),
    path('test-email/', views.test_email, name='test_email'),
  
    path('reset_password/', 
         auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"), 
         name='password_reset'),
    
    path('reset_password_sent/', 
         auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), 
         name='password_reset_done'),
    
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"), 
         name='password_reset_confirm'),
    
    path('reset_password_complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), 
         name='password_reset_complete'),

    path('accounts/', include('allauth.urls')),
]