"""

    mtg.lib.time
    ~~~~~~~~~~~~
    Time-related utilities.

    @author: mazz3rr

"""
import logging
from datetime import UTC, date, datetime, timedelta
from functools import wraps
from typing import Callable

import dateutil.parser
from contexttimer import Timer
from dateutil.relativedelta import relativedelta

from mtg.constants import FILENAME_TIMESTAMP_FORMAT, READABLE_TIMESTAMP_FORMAT

_log = logging.getLogger(__name__)


def seconds_to_readable(seconds: float) -> str:
    seconds = round(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h:{minutes:02}m:{seconds:02}s"


def _get_precision(seconds: float) -> int:
    if seconds < 1:
        return 4
    if seconds < 10:
        return 3
    elif seconds < 60:
        return 2
    elif seconds < 120:
        return 1
    return 0


def get_formatted_time(seconds: float, precision: int | None = None) -> str:
    """Return pre-formatted time string for the passed seconds.

    Examples: '0h:03m:23s' (precision=0) or '29.75 second(s)' (precision=2). Precision,
    if not supplied, is decided automatically, based on the passed time.
    """
    if precision is not None and precision < 0:
        precision = 0
    precision = _get_precision(seconds) if precision is None else precision
    if not precision:
        return seconds_to_readable(seconds)
    return f"{seconds:.{precision}f} second(s)"


def timed(operation="", precision: int | None = None) -> Callable:
    """Add time measurement to a decorated operation.

    Not specifying 'precision' means it will be set automatically according to elapsed time.
    Specifying 'precision' as zero renders a human-readable time suitable for long periods.
    Specifying a numbers renders time in seconds with the specified precision.

    Args:
        operation: name of the time-measured operation (default is function's name)
        precision: precision of the time measurement in seconds (default: automatic)

    Returns:
        the decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with Timer() as t:
                result = func(*args, **kwargs)
            activity = operation or f"'{func.__name__}()'"
            _log.info(f"Completed {activity} in {get_formatted_time(t.elapsed, precision)}")
            return result
        return wrapper
    return decorator


def get_date_from_ago_text(ago_text: str) -> date | None:
    """Parse 'ago' text (e.g. '2 days ago') into a Date object.
    """
    if not ago_text:
        return None
    dt = date.today()
    if "second" in ago_text or "minut" in ago_text:
        return dt
    ago_text = ago_text.replace(" few ", "")
    if "yesterday" in ago_text:
        return dt - timedelta(days=1)
    ago_text = ago_text.removesuffix(" ago")
    amount, time = ago_text.split()
    amount = 1 if amount in ("a", "an") else int(amount)
    if time in ("days", "day"):
        return dt - timedelta(days=amount)
    elif time in ("months", "month"):
        return dt - relativedelta(months=amount)
    elif time in ("years", "year"):
        return date(dt.year - amount, dt.month, dt.day)
    return None


def get_date_from_french_ago_text(ago_text: str) -> date | None:
    """Parse French 'ago' text (e.g. '3 jours par') into a Date object.

    This aligns with Magic-Ville decklist pages.
    """
    if not ago_text:
        return None
    dt = date.today()
    if "hier" in ago_text:
        return dt - timedelta(days=1)
    if ":" in ago_text:
        return dt
    ago_text = ago_text.removesuffix(" par")
    amount, time = ago_text.split()
    amount = 1 if amount == "a" else int(amount)
    if time in ("jour", "jours"):
        return dt - timedelta(days=amount)
    elif time in ("semaine", "semaines", "sem."):
        return dt - relativedelta(weeks=amount)
    elif time == "mois":
        return dt - relativedelta(months=amount)
    elif time in ("années", "année"):
        return date(dt.year - amount, dt.month, dt.day)
    return None


def get_date_from_month_text(month_text: str) -> date | None:
    """Parse 'month' text (e.g. 'June 27th') into a Date object.

    Month text may or may not include a valid year, e.g. 'June 27th 2021' or 'June 27th'. In case
    it's missing a current year is assumed.
    """
    current_year = naive_utc_now().year
    # clean the input string by removing ordinal suffixes
    cleaned_month_text = month_text.replace(
        'st', '').replace('nd', '').replace('rd', '').replace('th', '')

    parsed_date = dateutil.parser.parse(
        cleaned_month_text, default=datetime(current_year, 1, 1))
    return parsed_date.date()


def naive_utc_now() -> datetime:
    """Return a naive UTC datetime object of now.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def get_timestamp(filename=True, dt: datetime | None = None) -> str:
    """Return timestamp string in either a more human-readable format or one suitable for filenames.

    Args:
        filename: if True, returns a filename-suitable string, and human-readable one otherwise
        dt: datetime to be formatted (default: a naive UTC datetime of now)
    """
    fmt = FILENAME_TIMESTAMP_FORMAT if filename else READABLE_TIMESTAMP_FORMAT
    dt = dt or naive_utc_now()
    return dt.strftime(fmt)


def date_from_unixtime(unixtime: int, divisor=1000) -> date:
    """Return a `datetime.date` object from integer Unix time.
    """
    return datetime.fromtimestamp(unixtime / divisor, UTC).date()


def datetime_from_unixtime(unixtime: int, divisor=1000) -> datetime:
    """Return a `datetime.datetime` object from integer Unix time.
    """
    return datetime.fromtimestamp(unixtime / divisor, UTC)


def parse_date(text: str) -> date:
    """Parse `datetime.date` object from text.
    """
    return dateutil.parser.parse(text.strip()).date()
