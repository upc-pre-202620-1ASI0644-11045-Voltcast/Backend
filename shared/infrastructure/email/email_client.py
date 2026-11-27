from datetime import date
from email.message import EmailMessage
from html import escape
import os

import aiosmtplib

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


async def send_email(to: str, subject: str, body_html: str) -> None:
    """Send an HTML email through SMTP."""
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
    """Email a user that their password was changed."""
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
    """Email a user that their access request was accepted."""
    name = full_name or "Usuario"
    body = f"""
    <p>Hola {name},</p>
    <p>Tu solicitud de acceso fue aceptada. Ya puedes iniciar sesión en VoltCast.</p>
    """
    await send_email(to, "Tu cuenta fue aceptada", body)


async def send_account_rejected_notification(to: str, full_name: str | None) -> None:
    """Email a user that their access request was rejected."""
    name = full_name or "Usuario"
    body = f"""
    <p>Hola {name},</p>
    <p>Tu solicitud de acceso fue rechazada. Si crees que es un error, contacta a un supervisor.</p>
    """
    await send_email(to, "Tu cuenta fue rechazada", body)


def _threshold(limit: float | None) -> str:
    """Describe the voltage limit in Spanish for an email."""
    return f"el umbral de {limit:.2f} V" if limit is not None else "el umbral"


def _day_items(days: list[tuple[date, list[str]]]) -> str:
    """`days` are the (date, cell names) pairs, one list item per date."""
    return "".join(
        f"<li><b>{day:%d/%m/%Y}</b>: {', '.join(escape(name) for name in sorted(cells))}</li>" for day, cells in days
    )


async def send_voltage_forecast_notification(
    to: str, generated_on: date, limit: float | None, days: list[tuple[date, list[str]]]
) -> None:
    """US026: `days` are the first date each group of cells goes above the limit in the forecast generated on `generated_on`."""
    body = f"""
    <p>Con el pronóstico generado el {generated_on:%d/%m/%Y}, estas son las primeras fechas en que cada grupo de celdas superaría {_threshold(limit)}:</p>
    <ul>{_day_items(days)}</ul>
    <p>Te recomendamos tomar nota de las fechas y celdas mencionadas.</p>
    <p>Te volveremos a avisar sobre cualquier sobrecarga de voltaje 2 días y 1 día antes de cada fecha.</p>
    """
    subject = f"Pronósticos nuevos: celdas sobre {_threshold(limit)}" if limit is not None else "Pronósticos nuevos: celdas sobre el umbral"
    await send_email(to, subject, body)


async def send_near_date_notification(
    to: str, subject: str, limit: float | None, days: list[tuple[date, list[str]]]
) -> None:
    """US028: reminder of the cells that exceed the limit on dates that are close; `subject` is the title of the alert."""
    body = f"""
    <p>Estas celdas superarían {_threshold(limit)} en las fechas indicadas:</p>
    <ul>{_day_items(days)}</ul>
    <p>Revisa estas celdas.</p>
    """
    await send_email(to, subject, body)


async def send_verification_code(to: str, code: str) -> None:
    """Email the password reset verification code."""
    body = f"""
    <p>Tu código de verificación es:</p>
    <p style="font-size:24px;letter-spacing:4px"><b>{code}</b></p>
    <p>Expira en 15 minutos.</p>
    """
    await send_email(to, "Código de verificación", body)
