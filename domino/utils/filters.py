import uuid
from datetime import datetime

from pendulum import DateTime


def to_bkk(dt: DateTime | None) -> DateTime | None:
    """Convert pendulum.DateTime object to Asia/Bangkok timezone.

    Args:
        dt (DateTime | None): A pendulum.DateTime object.

    Returns:
        DateTime | None: A pendulum.DateTime object with Asia/Bangkok timezone
            or None if dt is None.
    """
    if dt is None:
        return None
    return dt.in_timezone("Asia/Bangkok")


def to_utc(dt: DateTime | None) -> DateTime | None:
    """Convert pendulum.DateTime object to UTC timezone.

    Args:
        dt (DateTime | None): A pendulum.DateTime object.

    Returns:
        DateTime | None: A pendulum.DateTime object with UTC timezone or
            None if dt is None.
    """
    if dt is None:
        return None
    return dt.in_timezone("UTC")


def date_add(
    dt: DateTime | None,
    years: int = 0,
    months: int = 0,
    weeks: int = 0,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: float = 0,
    microseconds: int = 0,
) -> DateTime | None:
    """Add time delta to pendulum.DateTime object.

    Args:
        dt (DateTime | None): A pendulum.DateTime object.
        years (int): Number of years to add.
        months (int): Number of months to add.
        weeks (int): Number of weeks to add.
        days (int): Number of days to add.
        hours (int): Number of hours to add.
        minutes (int): Number of minutes to add.
        seconds (float): Number of seconds to add.
        microseconds (int): Number of microseconds to add.

    Returns:
        DateTime | None: A pendulum.DateTime object with added one day or
            None if dt is None.
    """
    if dt is None:
        return None
    return dt.add(
        years=years,
        months=months,
        weeks=weeks,
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        microseconds=microseconds,
    )


def change_tz(dt: DateTime | None, tz: str = "UTC") -> DateTime | None:
    """Change timezone to pendulum.DateTime object.

    Args:
        dt (DateTime | None): A pendulum.DateTime object.
        tz (str): A timezone name that use to change.

    Returns:
        DateTime | None: A pendulum.DateTime object with changed timezone or
            None if dt is None.
    """
    if dt is None:
        return None
    return dt.in_timezone(tz)


def format_dt(
    dt: datetime | DateTime | None, fmt: str = "%Y-%m-%d %H:00:00%z"
) -> str | None:
    """Format string value on pendulum.DateTime or datetime object.

    Args:
        dt (datetime | DateTime | None): A datetime or pendulum.DateTime object.
        fmt (str): A format string that use with strftime method.

    Returns:
        str | None: A formatted string value or None if dt is None.
    """
    if dt is None:
        return None
    return dt.strftime(fmt)


def random_str(n: int = 6) -> str:
    """Random string charactor with specific length.

    Args:
        n (int): A length of random string.

    Returns:
        str: A random string charactor that generated from UUID4 and cut to n
            length.
    """
    return uuid.uuid4().hex[:n].lower()
