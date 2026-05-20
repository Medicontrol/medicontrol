from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Perfil, Medicamento, Tratamiento # Asegúrate de incluir Tratamiento

admin.site.register(Tratamiento)
admin.site.register(Medicamento)
admin.site.register(Perfil)