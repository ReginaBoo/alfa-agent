from datetime import datetime, timedelta


def get_metric_period(period_days: int = 30):
    """
    Возвращает стабильный период.

    Например:
    2026-04-11 00:00:00
    2026-05-11 00:00:00

    Без секунд/миллисекунд.
    """

    now = datetime.utcnow()

    period_end = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    period_start = period_end - timedelta(days=period_days)

    return period_start, period_end