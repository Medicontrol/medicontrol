from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Perfil, Medicamento, Tratamiento, Historial, RegistroSueno
from .forms import MedicamentoForm
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta, date
from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from io import BytesIO
import firebase_admin
from firebase_admin import credentials, messaging
import os
import json
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from twilio.rest import Client
import requests
from django.db.models import Count
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
from django.core.management import call_commands
from django.http import HttpResponse
from django.core.management import call_command


path_json = os.path.join(settings.BASE_DIR, 'firebase-auth.json')
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(path_json)
        firebase_admin.initialize_app(cred)
        print(" Firebase inicializado correctamente")
    except Exception as e:
        print(f" Error al inicializar Firebase: {e}")

def enviar_notificacion_push(token, titulo, cuerpo):
    if not token:
        print(" Sin token FCM — notificación push omitida")
        return
    try:
        msg = messaging.Message(
            notification=messaging.Notification(title=titulo, body=cuerpo),
            token=token,
        )
        response = messaging.send(msg)
        print(f" Push enviada correctamente: {response}")
    except Exception as e:
        print(f" Error al enviar push: {e}")

def enviar_whatsapp(numero, nombre_med, dosis):
    if not numero:
        print(" Sin teléfono — WhatsApp omitido")
        return
    if not numero.startswith('+'):
        numero = f"+57{numero}"
    try:
        client = Client(
            'AC3e1b6fdbba04134b803ba39f5484f66b',
            '0671ccd36184383e905f39e1bdb9fcef'
        )
        client.messages.create(
            from_='whatsapp:+14155238886',
            body=f" Es hora de tomar *{nombre_med}*\nDosis: {dosis}\n\n_MediControl te recuerda cuidar tu salud_ 🏥",
            to=f'whatsapp:{numero}'
        )
        print(f" WhatsApp enviado a {numero}")
    except Exception as e:
        print(f"Error WhatsApp: {e}")

@csrf_exempt
def guardar_token_fcm(request):
    if request.method == 'POST':
        try:
            data  = json.loads(request.body)
            token = data.get('token')
            if request.user.is_authenticated and token:
                perfil, _ = Perfil.objects.get_or_create(usuario=request.user)
                perfil.fcm_token = token
                perfil.save()
                print(f" Token FCM guardado para {request.user.username}")
                return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def verificar_tomas(request):
    ahora = timezone.now()
    notificaciones_enviadas = 0
    ultimo_titulo  = ''
    ultimo_mensaje = ''

    medicamentos = Medicamento.objects.filter(
        usuario=request.user,
        proxima_toma__gte=ahora - timedelta(minutes=11),
        proxima_toma__lte=ahora + timedelta(minutes=6),
    )

    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return JsonResponse({'status': 'ok', 'notificaciones_enviadas': 0, 'titulo': '', 'mensaje': ''})

    token    = perfil.fcm_token
    telefono = perfil.telefono
    t_id     = getattr(perfil, 'telegram_id', None) 

    for med in medicamentos:
        seg      = (med.proxima_toma - ahora).total_seconds()
        guardado = False

        if 240 <= seg <= 360 and not med.notif_previa_enviada:
            ultimo_titulo  = " Faltan pocos minutos"
            ultimo_mensaje = f"Prepárate para tomar {med.nombre}"
            enviar_notificacion_push(token, ultimo_titulo, ultimo_mensaje)
            
            if t_id:
                enviar_telegram_personalizado(t_id, f"🕒 *MediControl:* Faltan pocos min para {med.nombre}")
            
            med.notif_previa_enviada = True
            guardado = True

        elif 20 <= seg < 100 and not med.notif_toma_enviada:
            ultimo_titulo  = " Falta 1 minuto"
            ultimo_mensaje = f"Prepárate, ya es hora de tomar {med.nombre}"
            enviar_notificacion_push(token, ultimo_titulo, ultimo_mensaje)
            
            if t_id:
                enviar_telegram_personalizado(t_id, f"🔔 *MediControl:* En 1 minuto debes tomar {med.nombre}")
            
            med.notif_toma_enviada = True
            guardado = True

        elif -100 <= seg < 20 and not med.notif_3min_enviada:
            ultimo_titulo  = " ¡Es hora!"
            ultimo_mensaje = f"Toma tu {med.nombre} ahora"
            
            enviar_notificacion_push(token, ultimo_titulo, ultimo_mensaje)
            enviar_whatsapp(telefono, med.nombre, med.dosis)
            
            if t_id:
                enviar_telegram_personalizado(t_id, f"⚡ *¡HORA DE TU DOSIS!*\n💊 *Med:* {med.nombre}\n💉 *Dosis:* {med.dosis}")
            
            med.notif_3min_enviada = True
            guardado = True

        elif -360 <= seg < -240 and not med.notif_final_enviada:
            ultimo_titulo  = "⚠️ Retraso"
            ultimo_mensaje = f"Llevas 5 minutos sin tomar {med.nombre}"
            enviar_notificacion_push(token, ultimo_titulo, ultimo_mensaje)
            enviar_whatsapp(telefono, med.nombre, med.dosis)
            
            if t_id:
                enviar_telegram_personalizado(t_id, f"⚠️ *RETRASO:* No has registrado la toma de {med.nombre}")
            
            med.notif_final_enviada = True
            guardado = True

        elif seg < -600:
            ya_omitido = Historial.objects.filter(
                usuario=request.user,
                medicamento=med,
                estado='omitido',
                fecha_hora__date=timezone.now().date()
            ).exists()
            
            if not ya_omitido:
                Historial.objects.create(usuario=request.user, medicamento=med, estado='omitido')
                ultimo_titulo  = " Dosis omitida"
                ultimo_mensaje = f"{med.nombre} fue marcado como omitido"
                
                if t_id:
                    enviar_telegram_personalizado(t_id, f" *Dosis Omitida:* Se pasó el tiempo para {med.nombre}")
                
                med.proxima_toma = timezone.now() + timedelta(hours=med.frecuencia_horas)
                med.resetear_flags()
                guardado = True

        if guardado:
            med.save()
            notificaciones_enviadas += 1

    return JsonResponse({
        'status': 'ok',
        'notificaciones_enviadas': notificaciones_enviadas,
        'titulo':  ultimo_titulo,
        'mensaje': ultimo_mensaje,
    })

@login_required
@csrf_exempt
def posponer_medicamento(request, medicamento_id):
    if request.method == 'POST':
        medicamento = get_object_or_404(Medicamento, id=medicamento_id, usuario=request.user)
        try:
            data  = json.loads(request.body)
            razon = data.get('razon', '').strip() or 'Sin razón especificada'
        except Exception:
            razon = 'Sin razón especificada'

        Historial.objects.create(
            usuario=request.user,
            medicamento=medicamento,
            estado='pendiente',
            razon=razon
        )
        medicamento.proxima_toma = timezone.now() + timedelta(minutes=30)
        medicamento.resetear_flags()
        medicamento.save()
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)

@login_required
def editar_medicamento(request, id):
    med = get_object_or_404(Medicamento, id=id, usuario=request.user)
    if request.method == 'POST':
        med.dosis             = request.POST.get('dosis', med.dosis)
        med.descripcion       = request.POST.get('descripcion', med.descripcion)
        med.frecuencia_horas  = request.POST.get('frecuencia_horas', med.frecuencia_horas)
        med.stock             = request.POST.get('stock', med.stock)
        med.fecha_vencimiento = request.POST.get('fecha_vencimiento', med.fecha_vencimiento)
        med.proxima_toma      = request.POST.get('proxima_toma', med.proxima_toma)
        med.resetear_flags()
        med.save()
        messages.success(request, f" {med.nombre} actualizado correctamente")
        return redirect('crear_medicamento')
@login_required
def homePanel(request):
    ahora = timezone.now()
    hoy   = ahora.date()

   
    MAX_ITERACIONES = 100
    
    tareas_colgadas_viejas = Medicamento.objects.filter(
        usuario=request.user,
        proxima_toma__lt=ahora - timedelta(hours=1),
        fecha_vencimiento__gte=hoy
    )
    
    for med in tareas_colgadas_viejas:
        iteraciones = 0
        hora_original = med.proxima_toma
        
        while med.proxima_toma < ahora and iteraciones < MAX_ITERACIONES:
            med.proxima_toma += timedelta(hours=med.frecuencia_horas)
            iteraciones += 1
        
  
        if iteraciones > 0:
            print(f"Salvavidas: {med.nombre} movido de {hora_original} a {med.proxima_toma}")
        
        med.notif_retraso_enviada = False
        med.notif_final_enviada = False
        med.save()

  
    medicamentos_omitidos_ahora = Medicamento.objects.filter(
        usuario=request.user,
        proxima_toma__lte=ahora - timedelta(minutes=10),
        fecha_vencimiento__gte=hoy,
        notif_final_enviada=False
    )
    for med in medicamentos_omitidos_ahora:
        Historial.objects.create(
            usuario=med.usuario,
            medicamento=med,
            estado='omitido'
        )
        med.notif_final_enviada = True
        while med.proxima_toma <= ahora:
            med.proxima_toma += timedelta(hours=med.frecuencia_horas)
        med.notif_retraso_enviada = False
        med.notif_final_enviada = False
        med.save()

    total_medicamentos = Medicamento.objects.filter(usuario=request.user).count()
    pendientes_count   = Medicamento.objects.filter(
        usuario=request.user,
        fecha_vencimiento__gte=hoy
    ).count()

    historial_hoy = Historial.objects.filter(usuario=request.user, fecha_hora__date=hoy)
    tomados_hoy   = historial_hoy.filter(estado='tomado').count()
    omitidos_hoy  = historial_hoy.filter(estado='omitido').count()
    total_hoy     = tomados_hoy + omitidos_hoy
    rendimiento   = round((tomados_hoy / total_hoy) * 100) if total_hoy > 0 else 0

    if rendimiento >= 80:
        msg_rendimiento   = "¡Vas por buen camino!"
        sub_rendimiento   = "Has tomado casi todas tus dosis a tiempo hoy."
        color_rendimiento = "success"
    elif rendimiento >= 50:
        msg_rendimiento   = "¡Puedes mejorar!"
        sub_rendimiento   = "Intenta no saltarte más tomas hoy."
        color_rendimiento = "warning"
    elif total_hoy == 0:
        msg_rendimiento   = "Sin registros hoy"
        sub_rendimiento   = "Aún no tienes tomas registradas."
        color_rendimiento = "info"
    else:
        msg_rendimiento   = "¡Atención!"
        sub_rendimiento   = "Hoy has omitido varias dosis."
        color_rendimiento = "danger"

    nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    dias_labels, datos_tomados = [], []
    for i in range(6, -1, -1):
        dia    = hoy - timedelta(days=i)
        conteo = Historial.objects.filter(
            usuario=request.user, fecha_hora__date=dia, estado='tomado'
        ).count()
        dias_labels.append(nombres_dias[dia.weekday()])
        datos_tomados.append(conteo)

    proximas_tomas = Medicamento.objects.filter(
        usuario=request.user,
        fecha_vencimiento__gte=hoy,
    ).order_by('proxima_toma')

    sueno_hoy = RegistroSueno.objects.filter(
        usuario=request.user, fecha=hoy
    ).first()

    return render(request, 'principal/homePanel.html', {
        'proximas_tomas':     proximas_tomas,
        'total_medicamentos': total_medicamentos,
        'pendientes_count':   pendientes_count,
        'rendimiento':        rendimiento,
        'tomados_hoy':        tomados_hoy,
        'omitidos_hoy':       omitidos_hoy,
        'msg_rendimiento':    msg_rendimiento,
        'sub_rendimiento':    sub_rendimiento,
        'color_rendimiento':  color_rendimiento,
        'dias_semana_json':   json.dumps(dias_labels),
        'datos_semana_json':  json.dumps(datos_tomados),
        'sueno_hoy':          sueno_hoy,
    })

def index(request):
    if request.user.is_authenticated:
        return redirect('homePanel')
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )
        if user:
            auth_login(request, user)
            return redirect('homePanel')
        messages.error(request, "Usuario o contraseña incorrectos")
    return render(request, 'principal/index.html')

def register_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email    = request.POST.get('email')
        pass1    = request.POST.get('password1')
        pass2    = request.POST.get('password2')
        foto     = request.FILES.get('foto')
        tel      = request.POST.get('telefono', '').strip()

        if pass1 != pass2:
            messages.error(request, "Las contraseñas no coinciden")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Ese nombre de usuario ya está en uso")
            return redirect('register')

      
        user = User.objects.create_user(username=username, email=email, password=pass1)
        

        perfil, created = Perfil.objects.get_or_create(usuario=user)
        
        
        if foto:
            perfil.foto = foto
        perfil.telefono = tel
        perfil.save()
        
        messages.success(request, "¡Registro exitoso!")
        return redirect('index')

    return render(request, 'principal/register.html')
@login_required
def logout_view(request):
    auth_logout(request)
    return redirect('index')

@login_required
def crear_medicamento(request):
    if request.method == 'POST':
        nuevo_trat = request.POST.get('nuevo_tratamiento', '').strip()
        tratamiento_obj = None
        if nuevo_trat:
            tratamiento_obj, _ = Tratamiento.objects.get_or_create(
                nombre=nuevo_trat, usuario=request.user
            )
        form = MedicamentoForm(request.POST, user=request.user)
        if form.is_valid():
            med = form.save(commit=False)
            med.usuario = request.user
            if nuevo_trat and tratamiento_obj:
                med.tratamiento = tratamiento_obj
            med.save()
            messages.success(request, "Medicamento guardado correctamente")
            return redirect('crear_medicamento')
    else:
        form = MedicamentoForm(user=request.user)

    tratamientos_list = Tratamiento.objects.filter(
        usuario=request.user
    ).prefetch_related('medicamentos')

    hoy   = timezone.now().date()
    ahora = timezone.now()
    nombres_dias = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb']
    medicamentos_usuario = Medicamento.objects.filter(usuario=request.user)

    dias_semana = []
    for i in range(7):
        fecha         = hoy + timedelta(days=i)
        tomas_del_dia = []

        for med in medicamentos_usuario:
            toma_actual = med.proxima_toma
            while toma_actual.date() > fecha:
                toma_actual -= timedelta(hours=med.frecuencia_horas)
            while toma_actual.date() < fecha:
                toma_actual += timedelta(hours=med.frecuencia_horas)
            while toma_actual.date() == fecha:
                registro = Historial.objects.filter(
                    usuario=request.user,
                    medicamento=med,
                    fecha_hora__date=fecha,
                    fecha_hora__hour=toma_actual.hour,
                ).first()
                estado = registro.estado if registro else (
                    'pasado' if toma_actual < ahora else 'futuro'
                )
                tomas_del_dia.append({
                    'hora':   toma_actual.strftime('%H:%M'),
                    'nombre': med.nombre,
                    'dosis':  med.dosis,
                    'estado': estado,
                })
                toma_actual += timedelta(hours=med.frecuencia_horas)

        tomas_del_dia.sort(key=lambda x: x['hora'])

        dias_semana.append({
            'nombre':    nombres_dias[fecha.weekday() + 1 if fecha.weekday() < 6 else 0],
            'fecha':     fecha,
            'fecha_str': fecha.strftime('%d de %B'),
            'es_hoy':    fecha == hoy,
            'es_pasado': False,
            'tomas':     tomas_del_dia,
            'total':     len(tomas_del_dia),
        })

    return render(request, 'principal/crear.html', {
        'form':              form,
        'tratamientos_list': tratamientos_list,
        'dias_semana':       dias_semana,
        'hoy':               hoy,
    })

@login_required
def eliminar_medicamento(request, id):
    get_object_or_404(Medicamento, id=id, usuario=request.user).delete()
    messages.success(request, "Medicamento eliminado")
    return redirect('crear_medicamento')

@login_required
def tomar_medicamento(request, medicamento_id):
    med   = get_object_or_404(Medicamento, id=medicamento_id, usuario=request.user)
    ahora = timezone.now()
    seg   = (med.proxima_toma - ahora).total_seconds()

    if seg > 600:
        minutos = int(seg / 60)
        messages.error(request, f" Aún no es hora. Faltan {minutos} minutos para tomar {med.nombre}.")
        return redirect('homePanel')

    Historial.objects.create(usuario=request.user, medicamento=med, estado='tomado')

    if med.stock > 0:
        med.stock -= 1

    med.proxima_toma = timezone.now() + timedelta(hours=med.frecuencia_horas)
    med.resetear_flags()
    med.save()

    messages.success(request, f" {med.nombre} registrado como tomado")
    return redirect('homePanel')

@login_required
def historial(request):
    historial_list = Historial.objects.filter(usuario=request.user)

    estado       = request.GET.get('estado', '')
    busqueda     = request.GET.get('busqueda', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin    = request.GET.get('fecha_fin', '')

    if estado in ['tomado', 'omitido', 'pendiente']:
        historial_list = historial_list.filter(estado=estado)
    if busqueda:
        historial_list = historial_list.filter(medicamento__nombre__icontains=busqueda)
    if fecha_inicio:
        historial_list = historial_list.filter(fecha_hora__date__gte=fecha_inicio)
    if fecha_fin:
        historial_list = historial_list.filter(fecha_hora__date__lte=fecha_fin)

    historial_list = historial_list.order_by('-fecha_hora')

    hoy          = timezone.now().date()
    nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    dias, tomados_sem, omitidos_sem = [], [], []

    for i in range(6, -1, -1):
        dia  = hoy - timedelta(days=i)
        base = Historial.objects.filter(usuario=request.user, fecha_hora__date=dia)
        dias.append(nombres_dias[dia.weekday()])
        tomados_sem.append(base.filter(estado='tomado').count())
        omitidos_sem.append(base.filter(estado='omitido').count())

    return render(request, 'principal/historial.html', {
        'historial':      historial_list,
        'estado_activo':  estado,
        'busqueda':       busqueda,
        'fecha_inicio':   fecha_inicio,
        'fecha_fin':      fecha_fin,
        'total':          historial_list.count(),
        'dias_json':      json.dumps(dias),
        'tomados_json':   json.dumps(tomados_sem),
        'omitidos_json':  json.dumps(omitidos_sem),
    })

@login_required
def historial_pdf(request):
    historial_list = Historial.objects.filter(
        usuario=request.user
    ).order_by('-fecha_hora')

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=(595.27, 841.89)) 
    anchura, altura = 595.27, 841.89

    COLOR_PRIMARIO = (0.07, 0.45, 0.87)   
    COLOR_SECUNDARIO = (0.05, 0.79, 0.94) 
    COLOR_TEXTO = (0.2, 0.2, 0.2)        
    COLOR_GRIS_CLARO = (0.95, 0.95, 0.95) 

    ALTO_HEADER = 110
    p.setFillColorRGB(*COLOR_PRIMARIO)
    p.rect(0, altura - ALTO_HEADER, anchura, ALTO_HEADER, fill=True, stroke=False)
    
    p.setFillColorRGB(*COLOR_SECUNDARIO)
    p.rect(0, altura - (ALTO_HEADER + 3), anchura, 3, fill=True, stroke=False)

    ruta_avatar = r"C:\MiProyectoMedicamentos\Medicontrol\medicontrol_projecto\principal\static\principal\img\avatarpdf.png"

    if os.path.exists(ruta_avatar):
        p.drawImage(ruta_avatar, 40, altura - 52, width=55, height=35, mask='auto')
    else:
        print(f"⚠️ Alerta: No se encontró la imagen en la ruta: {ruta_avatar}")

    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(40, altura - 92, "MediControl")
    
    p.setFont("Helvetica", 10)
    p.drawRightString(anchura - 40, altura - 92, "HISTORIAL COMPLETO DE TOMAS")

    p.setFillColorRGB(*COLOR_TEXTO)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(40, altura - 145, f"Paciente: {request.user.username.upper()}")
    
    p.setFont("Helvetica", 10)
    fecha_reporte = timezone.now().strftime('%d/%m/%Y — %H:%M')
    p.drawRightString(anchura - 40, altura - 145, f"Generado el: {fecha_reporte}")
    
    p.setStrokeColorRGB(0.8, 0.8, 0.8)
    p.setLineWidth(0.5)
    p.line(40, altura - 160, anchura - 40, altura - 160)

    y = altura - 195 
    
    p.setFillColorRGB(*COLOR_GRIS_CLARO)
    p.rect(40, y, anchura - 80, 20, fill=True, stroke=False)
    
    p.setFillColorRGB(*COLOR_TEXTO)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(45, y + 6, "Fecha y Hora")
    p.drawString(160, y + 6, "Medicamento")
    p.drawString(290, y + 6, "Estado")
    p.drawString(390, y + 6, "Detalles / Razón de Omisión")

    p.setFont("Helvetica", 9)
    
    for h in historial_list:
        y -= 20
        
        if y < 60:
            p.setStrokeColorRGB(0.8, 0.8, 0.8)
            p.line(40, 40, anchura - 40, 40)
            p.setFillColorRGB(0.5, 0.5, 0.5)
            p.setFont("Helvetica-Oblique", 8)
            p.drawString(40, 25, "MediControl — Reporte.")
            
            p.showPage()
            y = altura - 60
            p.setFont("Helvetica", 9)
            p.setFillColorRGB(*COLOR_TEXTO)

        p.setStrokeColorRGB(0.9, 0.9, 0.9)
        p.line(40, y, anchura - 40, y)

        p.drawString(45, y + 5, h.fecha_hora.strftime('%d/%m/%Y %H:%M'))
        
        nombre_med = h.medicamento.nombre if h.medicamento else h.nombre_medicamento
        p.drawString(160, y + 5, nombre_med)
        
        if h.estado == 'tomado':
            p.setFillColorRGB(0.1, 0.5, 0.1)
            texto_estado = "TOMADO"
        else:
            p.setFillColorRGB(0.7, 0.1, 0.1)
            texto_estado = "OMITIDO"
            
        p.drawString(290, y + 5, texto_estado)
        p.setFillColorRGB(*COLOR_TEXTO)

        detalles_texto = f"Razón: {h.razon}" if h.razon else "Registrado correctamente"
        p.drawString(390, y + 5, detalles_texto)

    p.setStrokeColorRGB(0.8, 0.8, 0.8)
    p.line(40, 40, anchura - 40, 40)
    p.setFillColorRGB(0.5, 0.5, 0.5)
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(40, 25, "MediControl — Sistema Universitario Automatizado de Gestión de Medicamentos.")

    p.showPage()
    p.save()
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Historial_MediControl_{request.user.username}.pdf"'
    
    return response
@login_required
def historial_familiar(request, familiar_id):
    familiar = get_object_or_404(User, id=familiar_id)
    hoy = timezone.now().date()
    hace_siete_dias = hoy - timedelta(days=6)
    
    registros = Historial.objects.filter(
        usuario=familiar,
        fecha_hora__date__range=[hace_siete_dias, hoy],
        estado__in=['tomado', 'omitido']
    ).values('fecha_hora__date', 'estado').annotate(total=Count('id')).order_by('fecha_hora__date')

    dias_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    labels = []
    data_tomados = []
    data_omitidos = []

    for i in range(7):
        fecha = hace_siete_dias + timedelta(days=i)
        labels.append(dias_semana[fecha.weekday()])
        
        tomados_hoy = sum(r['total'] for r in registros if r['fecha_hora__date'] == fecha and r['estado'] == 'tomado')
        omitidos_hoy = sum(r['total'] for r in registros if r['fecha_hora__date'] == fecha and r['estado'] == 'omitido')
        
        data_tomados.append(tomados_hoy)
        data_omitidos.append(omitidos_hoy)

  
    total_tomados = sum(data_tomados)
    total_omitidos = sum(data_omitidos)

    return render(request, 'principal/historial_familiar.html', {
        'familiar': familiar,
        'labels': labels,
        'data': data_tomados,  
        'data_omitidos': data_omitidos,
        'fecha_desde': hace_siete_dias.strftime('%d/%m/%Y'),
        'fecha_hasta': hoy.strftime('%d/%m/%Y'),
        'total_tomados': total_tomados,
        'total_omitidos': total_omitidos,
    })
@login_required
def sugerutinas(request):
    alertas_stock = Medicamento.objects.filter(
        usuario=request.user, 
        stock__lte=5          
    )
    
    return render(request, 'principal/sugerutinas.html', {
        'alertas_stock': alertas_stock
    })

@login_required
@csrf_exempt
def registrar_dormir(request):
    if request.method == 'POST':
        r, _ = RegistroSueno.objects.get_or_create(
            usuario=request.user, fecha=date.today()
        )
        r.hora_dormir    = timezone.now()
        r.hora_despertar = None
        r.horas_dormidas = None
        r.save()
        return JsonResponse({'hora': r.hora_dormir.strftime('%H:%M')})
    return JsonResponse({'error': 'Método no permitido'}, status=400)

@login_required
@csrf_exempt
def registrar_despertar(request):
    if request.method == 'POST':
        try:
            r = RegistroSueno.objects.filter(
                usuario=request.user,
                hora_dormir__isnull=False,
                hora_despertar__isnull=True
            ).latest('hora_dormir')
            r.hora_despertar = timezone.now()
            mins             = int((r.hora_despertar - r.hora_dormir).total_seconds() / 60)
            r.horas_dormidas = round(mins / 60, 1)
            r.minutos_extra  = mins % 60
            r.save()
            return JsonResponse({'horas': mins // 60, 'minutos': mins % 60})
        except RegistroSueno.DoesNotExist:
            return JsonResponse({'error': 'No hay registro activo'}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=400)

def enviar_telegram_personalizado(chat_id, mensaje):
    if not chat_id:
        return
    token = "8716611179:AAFLa7kZ12VEmFUQUqvGAJ3CZYn6h6tsGrw" 
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'Markdown'})
    except Exception as e:
        print(f"Error Telegram: {e}") 

@login_required
def actualizar_telegram(request):
    if request.method == 'POST':
        nuevo_id = request.POST.get('telegram_id').strip()
        perfil = request.user.perfil
        perfil.telegram_id = nuevo_id
        perfil.save()
        messages.success(request, " ID de Telegram actualizado correctamente.")
        return redirect('homePanel') 

@login_required
def red_familiar(request):
    if request.method == 'POST':
        nombre_supervisor = request.POST.get('nombre_usuario_supervisor')
        try:
            supervisor = User.objects.get(username=nombre_supervisor)
            
            if supervisor == request.user:
                messages.error(request, "No puedes asignarte a ti mismo como supervisor.")
            else:
                perfil = request.user.perfil
                perfil.familiar_a_cargo = supervisor
                perfil.save()
                messages.success(request, f"¡Éxito! {nombre_supervisor} ahora puede supervisar tus tomas.")
            
            return redirect('red_familiar')

        except User.DoesNotExist:
            messages.error(request, f"El usuario '{nombre_supervisor}' no existe en el sistema.")
            return redirect('red_familiar')

    parientes_perfiles = Perfil.objects.filter(familiar_a_cargo=request.user)
    
    supervisados = []
    hoy = timezone.now().date()
    hace_7_dias = hoy - timedelta(days=7)
    
    for p in parientes_perfiles:
        historial = Historial.objects.filter(
            usuario=p.usuario,
            fecha_hora__date__gte=hace_7_dias,
            fecha_hora__date__lte=hoy
        ).order_by('-fecha_hora')[:20]
        
        supervisados.append({
            'familiar': p.usuario,
            'historial': historial
        })

    return render(request, 'principal/red_familiar.html', {'supervisados': supervisados})

@login_required
def desvincular_familiar(request):
    perfil = request.user.perfil
    perfil.familiar_a_cargo = None
    perfil.save()
    messages.success(request, "Ya no estás bajo supervisión.")
    return redirect('red_familiar')


@login_required
def debug_usuario(request):
    
    perfil = Perfil.objects.filter(usuario=request.user).first()
    medicamentos = Medicamento.objects.filter(usuario=request.user)
    
    return JsonResponse({
        'usuario': request.user.username,
        'tiene_perfil': perfil is not None,
        'cantidad_medicamentos': medicamentos.count(),
        'medicamentos': [{'id': m.id, 'nombre': m.nombre} for m in medicamentos],
        'historial': Historial.objects.filter(usuario=request.user).count()
    })


def test_email(request):
    try:
        send_mail(
            'Prueba MediControl',
            'Este es un correo de prueba',
            settings.DEFAULT_FROM_EMAIL,
            ['tucorreo@gmail.com'],  
            fail_silently=False,
        )
        return JsonResponse({'status': 'Correo enviado correctamente'})
    except Exception as e:
        return JsonResponse({'status': f'Error: {str(e)}'})


def run_migrations(request):
    try:
        call_command('migrate', interactive=False)
        call_command('collectstatic', interactive=False)
        return HttpResponse(" Migraciones y archivos estáticos configurados correctamente")
    except Exception as e:
        return HttpResponse(f" Error: {str(e)}")