# Persistencia/notificacionesEmail.py
import os, ssl, smtplib, mimetypes
from email.message import EmailMessage

try:
    import streamlit as st  # para leer st.secrets cuando se ejecute dentro de Streamlit
    _HAS_ST = True
except Exception:
    _HAS_ST = False


def _credenciales():
    """
    Obtiene usuario y contraseña de aplicaciones desde st.secrets o variables de entorno.
    Prioridad: st.secrets → entorno. Lanza ValueError si faltan.
    """
    user = None
    pwd = None

    if _HAS_ST:
        try:
            user = st.secrets.get("GMAIL_USER", None)
            pwd  = st.secrets.get("GMAIL_APP_PASSWORD", None)
        except Exception:
            pass

    if not user:
        user = os.getenv("GMAIL_USER")
    if not pwd:
        pwd = os.getenv("GMAIL_APP_PASSWORD")

    if not user or not pwd:
        raise ValueError("Faltan credenciales de correo: defina GMAIL_USER y GMAIL_APP_PASSWORD en st.secrets o variables de entorno.")
    return user, pwd


def enviar_email(asunto: str,
                 cuerpo: str,
                 destinatarios: list[str] | str,
                 cc: list[str] | None = None,
                 bcc: list[str] | None = None,
                 archivos: list[str] | None = None,
                 reply_to: str | None = None) -> tuple[bool, str]:
    """
    Envía un correo por SMTP Gmail (SSL 465). Retorna (ok, mensaje).
    Los adjuntos se pasan como rutas de archivo; se detecta su MIME automáticamente.
    """
    try:
        remitente, password = _credenciales()
        if isinstance(destinatarios, str):
            destinatarios = [destinatarios]
        cc  = cc  or []
        bcc = bcc or []

        msg = EmailMessage()
        msg["Subject"] = asunto
        msg["From"]    = f"Gestemed Notificaciones <{remitente}>"
        msg["To"]      = ", ".join(destinatarios)
        if cc:
            msg["Cc"]  = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to

        msg.set_content(cuerpo)

        # Adjuntos
        for path in (archivos or []):
            try:
                ctype, encoding = mimetypes.guess_type(path)
                maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
                with open(path, "rb") as f:
                    msg.add_attachment(f.read(),
                                       maintype=maintype,
                                       subtype=subtype,
                                       filename=os.path.basename(path))
            except Exception as e:
                return False, f"Adjunto inválido ({path}): {e}"

        # Envío
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
            smtp.login(remitente, password)
            smtp.send_message(msg, to_addrs=destinatarios + cc + bcc)

        return True, "Correo enviado correctamente."
    except Exception as e:
        return False, f"Fallo al enviar correo: {e}"


def enviar_prueba(destino: str | None = None) -> tuple[bool, str]:
    """
    Envía un correo de prueba a 'destino' o al propio remitente si no se indica.
    """
    user, _ = _credenciales()
    to = destino or user
    asunto = "Prueba de notificación Gestemed"
    cuerpo = "Este es un mensaje de prueba del módulo de notificaciones. Si lo ves, el canal SMTP está correcto."
    return enviar_email(asunto, cuerpo, [to])