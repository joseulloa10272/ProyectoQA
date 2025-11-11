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

# Persistencia/notificacionesEmail.py
import os, ssl, smtplib, mimetypes
from email.message import EmailMessage
# … deja intactas _HAS_ST, _credenciales(), etc.

def _smtp_debug_on(smtp: smtplib.SMTP | smtplib.SMTP_SSL):
    try:
        if os.getenv("SMTP_DEBUG", "").strip() == "1":
            smtp.set_debuglevel(1)  # imprime diálogo SMTP en terminal
    except Exception:
        pass

def enviar_email(asunto: str,
                 cuerpo: str,
                 destinatarios: list[str] | str,
                 cc: list[str] | None = None,
                 bcc: list[str] | None = None,
                 archivos: list[str] | None = None,
                 reply_to: str | None = None) -> tuple[bool, str]:

    try:
        remitente, password = _credenciales()
        if isinstance(destinatarios, str):
            destinatarios = [destinatarios]
        cc  = cc  or []
        bcc = bcc or []
        todos = destinatarios + cc + bcc
        if not todos:
            return False, "Sin destinatarios."

        msg = EmailMessage()
        msg["Subject"] = asunto
        msg["From"]    = f"Gestemed Notificaciones <{remitente}>"
        msg["To"]      = ", ".join(destinatarios)
        if cc:
            msg["Cc"]  = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to
        msg["X-Mailer"] = "Gestemed/SMTP"
        msg.set_content(cuerpo)

        for path in (archivos or []):
            try:
                ctype, _ = mimetypes.guess_type(path)
                maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
                with open(path, "rb") as f:
                    msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path))
            except Exception as e:
                return False, f"Adjunto inválido ({path}): {e}"

        context = ssl.create_default_context()

        # Intento 1: SSL 465
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                _smtp_debug_on(smtp)
                smtp.login(remitente, password)
                smtp.send_message(msg, to_addrs=todos)
            return True, f"Correo enviado a: {', '.join(todos)} via SSL:465"
        except Exception as e1:
            # Intento 2: STARTTLS 587
            try:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
                    _smtp_debug_on(smtp)
                    smtp.ehlo()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                    smtp.login(remitente, password)
                    smtp.send_message(msg, to_addrs=todos)
                return True, f"Correo enviado a: {', '.join(todos)} via STARTTLS:587"
            except Exception as e2:
                return False, f"SMTP falló. SSL465: {repr(e1)} | STARTTLS587: {repr(e2)}"
    except Exception as e:
        return False, f"Fallo al enviar correo: {repr(e)}"