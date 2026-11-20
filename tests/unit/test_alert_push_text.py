from datetime import date

from notification_management.domain.model.aggregates.Notification import (
    DATE_NEAR,
    VOLTAGE_EXCEEDED,
    alert_push_text,
)

DAY = date(2026, 11, 20)


class TestAlertPushText:
    def test_one_cell(self):
        assert alert_push_text(DATE_NEAR, DAY, ["A1"], 3.1) == "Para el 20/11/2026 la celda A1 superará el umbral de 3.10 V"

    def test_up_to_three_cells_are_all_named(self):
        assert alert_push_text(DATE_NEAR, DAY, ["A3", "A1", "A2"], 3.1) == (
            "Para el 20/11/2026 las celdas A1, A2, A3 superarán el umbral de 3.10 V"
        )

    def test_more_than_three_cells_say_how_many_more_and_point_to_the_email(self):
        text = alert_push_text(DATE_NEAR, DAY, ["A1", "A2", "A3", "A4", "A5"], 3.1)
        assert text == (
            "Para el 20/11/2026 las celdas A1, A2, A3 y 2 más superarán el umbral de 3.10 V. "
            "Revisa tu correo electrónico para ver el detalle"
        )

    def test_the_new_forecasts_push_only_points_to_the_email(self):
        assert alert_push_text(VOLTAGE_EXCEEDED, None, ["A1"], 3.1) == (
            "Se han recibido nuevos pronósticos, revisa tu correo electrónico."
        )
