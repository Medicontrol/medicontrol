from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.models import User

def index(request):
    # Si el usuario ya está inicio, lo mandamos al panel automáticamente
    if request.user.is_authenticated:
        return redirect('homePanel')
    
    if request.method == 'POST':
   
        usuario = request.POST.get('username') 
        clave = request.POST.get('password')
        
        user = authenticate(request, username=usuario, password=clave)

        if user is not None:
            auth_login(request, user)
            messages.success(request, f"¡Bienvenido, {user.username}!")
            return redirect('homePanel') 
        else:
            messages.error(request, "Usuario o contraseña incorrectos")
        
            return redirect('/#login-section')

    context = {
        'proyecto_nombre': 'MediControl',
        'mision': 'Ayudar a las personas a llevar un control preciso de sus tratamientos médicos.',
    }
    return render(request, 'principal/index.html', context)

def homePanel(request):
  
    if not request.user.is_authenticated:
        return redirect('index') 
    
    return render(request, 'principal/homePanel.html')

def logout_view(request):
    auth_logout(request)
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('index')

from .models import Perfil 

def register_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
      
        foto = request.FILES.get('foto') 

        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden')
            return redirect('register')
            
        if User.objects.filter(username=username).exists():
            messages.error(request, 'El usuario ya existe')
            return redirect('register')
            
        # Creamos el usuario 
        nuevo_usuario = User.objects.create_user(username=username, email=email, password=password1)
        
        # perfil con foto
        Perfil.objects.create(usuario=nuevo_usuario, foto=foto)

        messages.success(request, 'Cuenta creada con éxito. Ahora puedes iniciar sesión')
        return redirect('index')
        
    return render(request, 'principal/register.html')