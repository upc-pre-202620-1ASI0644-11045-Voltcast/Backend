from email.message import EmailMessage
import os

import aiosmtplib

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


async def send_email(to: str, subject: str, body_html: str) -> None:
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body_html, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        start_tls=True,
        username=SMTP_USER,
        password=SMTP_PASS,
    )


async def send_password_changed_notification(to: str, full_name: str | None) -> None:
    name = full_name or "Usuario"
    body = f"""
    <p>Hola {name},</p>
    <p>Tu contraseña fue cambiada recientemente.</p>
    <p>Si no fuiste tú, contacta al supervisor de inmediato.</p>
    """
    await send_email(to, "Contraseña cambiada", body)


async def send_new_registration_request_notification(to: str, requests: list[tuple[str, str]]) -> None:
    """`requests` are the (name, email) of the access requests waiting for review."""
    items = "".join(f"<li><b>{name}</b> ({email})</li>" for name, email in requests)
    body = f"""
    <p>Hola,</p>
    <p>Hay solicitudes de creación de cuenta pendientes de revisión:</p>
    <ul>{items}</ul>
    <p>Revísalas desde el panel de administración.</p>
    """
    await send_email(to, "Nueva solicitud de registro", body)


async def send_account_accepted_notification(to: str, full_name: str | None) -> None:
    name = full_name or "Usuario"
    body = f"""
    <p>Hola {name},</p>
    <p>Tu solicitud de acceso fue aceptada. Ya puedes iniciar sesión en VoltCast.</p>
    """
    await send_email(to, "Tu cuenta fue aceptada", body)


async def send_account_rejected_notification(to: str, full_name: str | None) -> None:
    name = full_name or "Usuario"
    body = f"""
    <p>Hola {name},</p>
    <p>Tu solicitud de acceso fue rechazada. Si crees que es un error, contacta al supervisor.</p>
    """
    await send_email(to, "Tu cuenta fue rechazada", body)


async def send_verification_code(to: str, code: str) -> None:
    body = f"""
    <p>Tu código de verificación es:</p>
    <p style="font-size:24px;letter-spacing:4px"><b>{code}</b></p>
    <p>Expira en 15 minutos.</p>
    """
    await send_email(to, "Código de verificación", body)
