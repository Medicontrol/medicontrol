from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    foto = models.ImageField(upload_to='perfiles/', null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True, verbose_name="Teléfono WhatsApp")
    fcm_token = models.TextField(blank=True, null=True, verbose_name="Token de Firebase")
    fecha_registro = models.DateTimeField(auto_now_add=True)
    telegram_id = models.CharField(max_length=20, blank=True, null=True)
    
    familiar_a_cargo = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='familiares_bajo_supervision',
        verbose_name="Familiar Supervisor"
    )

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"


class Tratamiento(models.Model):
    nombre = models.CharField(max_length=100)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre


class Medicamento(models.Model):
    usuario     = models.ForeignKey(User, on_delete=models.CASCADE)
    tratamiento = models.ForeignKey(
        Tratamiento, on_delete=models.CASCADE,
        related_name='medicamentos', null=True, blank=True
    )
    nombre            = models.CharField(max_length=100)
    descripcion       = models.TextField(blank=True, null=True)
    dosis             = models.CharField(max_length=50)
    stock             = models.IntegerField(default=0)
    fecha_vencimiento = models.DateField()
    frecuencia_horas  = models.IntegerField()
    proxima_toma      = models.DateTimeField()
    
    notif_previa_enviada  = models.BooleanField(default=False)
    notif_toma_enviada    = models.BooleanField(default=False)
    notif_3min_enviada    = models.BooleanField(default=False)
    notif_final_enviada   = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.nombre} ({self.usuario.username})"

    def resetear_flags(self):
        self.notif_previa_enviada = False
        self.notif_toma_enviada   = False
        self.notif_3min_enviada   = False
        self.notif_final_enviada  = False


class Historial(models.Model):
    ESTADOS = [
        ('tomado',    'Tomado'),
        ('pendiente', 'Pendiente'),
        ('omitido',   'Omitido'),
    ]

    usuario     = models.ForeignKey(User, on_delete=models.CASCADE)
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE)
    fecha_hora  = models.DateTimeField(auto_now_add=True)
    estado      = models.CharField(max_length=10, choices=ESTADOS)
    razon       = models.TextField(blank=True, null=True, verbose_name="Razón de posponer")

    def __str__(self):
        return f"{self.usuario.username} - {self.medicamento.nombre} - {self.estado}"


class RegistroSueno(models.Model):
    usuario        = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha          = models.DateField()
    hora_dormir    = models.DateTimeField(null=True, blank=True)
    hora_despertar = models.DateTimeField(null=True, blank=True)
    horas_dormidas = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    minutos_extra  = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.usuario.username} - {self.fecha}"

    class Meta:
        ordering = ['-fecha']



def crear_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.get_or_create(usuario=instance)

post_save.connect(crear_perfil, sender=User)