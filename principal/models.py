from django.db import models
from django.contrib.auth.models import User


class Perfil(models.Model):

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    

    foto = models.ImageField(upload_to='perfiles/', null=True, blank=True)

    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"