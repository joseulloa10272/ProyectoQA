""" # prueba rápida del canal SMTP
from Persistencia.notificacionesEmail import enviar_prueba
print(enviar_prueba())  # devuelve (True, "Correo enviado correctamente.") si todo está bien

# envío del resumen de vencimientos al correo del usuario autenticado
from Persistencia.contratosPersistencia import enviarAlertasVencimiento_por_correo
print(enviarAlertasVencimiento_por_correo(usuario="Eddye"))

# envío forzado a un destinatario alterno (útil para validar sin depender del usuario)
print(enviarAlertasVencimiento_por_correo(usuario="Eddye", destinatario="destino@ejemplo.com")) """

from Persistencia.contratosPersistencia import enviarAlertasVencimiento_por_correo
enviarAlertasVencimiento_por_correo(usuario="Eddye", destinatario="joseulloa10272@gmail.com")