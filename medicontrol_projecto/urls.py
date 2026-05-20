"""
URL configuration for medicontrol_projecto project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
import os
 
# Vista que sirve el Service Worker directamente (sin redirección)
# RedirectView no funciona para Service Workers — el navegador los rechaza
def firebase_sw(request):
    sw_path = os.path.join(
        settings.BASE_DIR,
        'principal', 'static', 'principal', 'js', 'firebase-messaging-sw.js'
    )
    with open(sw_path, 'r') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/javascript')
 
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('principal.urls')),
    path('firebase-messaging-sw.js', firebase_sw, name='firebase-messaging-sw.js'),
]
 
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
 