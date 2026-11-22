import asyncio
from datetime import date

from notification_management.domain.model.aggregates.Notification import DATE_NEAR, alert_push_text
from shared.infrastructure.email import email_client

DAY = date(2026, 11, 22)
CELLS = ["A1", "A2", "A3", "A4", "A5"]
LIMIT = 3.1
PUSH = "Para el 22/11/2026 las celdas A1, A2, A3 y 2 más superarán el umbral de 3.10 V. Revisa tu email"


def test_five_cells_push_points_to_an_email_that_lists_all_of_them(monkeypatch):
    sent = []

    async def fake_send(to, subject, body_html):
        sent.append((to, subject, body_html))

    monkeypatch.setattr(email_client, "send_email", fake_send)

    push = alert_push_text(DATE_NEAR, DAY, CELLS, LIMIT)
    asyncio.run(email_client.send_near_date_notification(
        "ingeniero@example.com", "Revisa la celda: voltaje excesivo próximo", LIMIT, [(DAY, CELLS)]
    ))
    [(_, subject, body)] = sent

    print(f"\nPUSH   : {push}\nASUNTO : {subject}\nCORREO : {body}")
    assert push == PUSH
    assert "<li><b>22/11/2026</b>: A1, A2, A3, A4, A5</li>" in body  # the two cells the push hides are in the email
    assert "el umbral de 3.10 V" in body
