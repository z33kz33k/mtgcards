"""

    mtgcards.utils.py
    ~~~~~~~~~~~~~~~~~
    Utilities.

    @author: z33k

"""
import logging
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Iterable, Optional, Type
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from contexttimer import Timer

from mtgcards.const import FILENAME_TIMESTAMP_FORMAT, T
from mtgcards.utils.check_type import type_checker, uniform_type_checker

_log = logging.getLogger(__name__)


def seconds2readable(seconds: float) -> str:
    seconds = round(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h:{minutes:02}m:{seconds:02}s"


def timed(operation="", precision=3) -> Callable:
    """Add time measurement to the decorated operation.

    Args:
        operation: name of the time-measured operation (default is function's name)
        precision: precision of the time measurement in seconds (decides output text formatting)

    Returns:
        the decorated function
    """
    if precision < 0:
        precision = 0

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with Timer() as t:
                result = func(*args, **kwargs)
            activity = operation or f"'{func.__name__}()'"
            time = seconds2readable(t.elapsed)
            if not precision:
                _log.info(f"Completed {activity} in {time}")
            elif precision == 1:
                _log.info(f"Completed {activity} in {t.elapsed:.{precision}f} "
                          f"second(s) ({time})")
            else:
                _log.info(f"Completed {activity} in {t.elapsed:.{precision}f} "
                          f"second(s)")
            return result
        return wrapper
    return decorator


def getrepr(class_: Type, *name_value_pairs: tuple[str, Any]) -> str:
    """Return ``__repr__`` string format: 'ClassName(name=value, ..., name_n=value_n)'

    Args:
        class_: class to get repr for
        name_value_pairs: variable number of (name, value) tuples
    """
    reprs = [f"{name}={value!r}" for name, value in name_value_pairs]
    return f"{class_.__name__}({', '.join(reprs)})"


@type_checker(str)
def extract_float(text: str) -> float:
    """Extract floating point number from text.
    """
    num = "".join([char for char in text if char.isdigit() or char in ",."])
    if not num:
        raise ParsingError(f"No digits or decimal point in text: {text!r}")
    return float(num.replace(",", "."))


@type_checker(str)
def extract_int(text: str) -> int:
    """Extract an integer from text.
    """
    num = "".join([char for char in text if char.isdigit()])
    if not num:
        raise ParsingError(f"No digits in text: {text!r}")
    return int(num)


@type_checker(str)
def get_ago_date(date_text: str) -> date | None:
    """Parse 'ago' text (e.g. '2 days ago') into a Date object.
    """
    if not date_text:
        return None
    date_text = date_text.removesuffix(" ago")
    amount, time = date_text.split()
    amount = int(amount)
    dt = date.today()
    if time in ("days", "day"):
        return dt - timedelta(days=amount)
    elif time in ("months", "month"):
        return dt - relativedelta(months=amount)
    elif time in ("years", "year"):
        return date(dt.year - amount, dt.month, dt.day)
    return None


@type_checker(str, none_allowed=True)
def getfloat(string: str | None) -> float | None:
    """Interpret string as floating point number or, if not possible, return None.
    """
    if not string:
        return None
    try:
        return extract_float(string)
    except ValueError:
        return None


@type_checker(str, none_allowed=True)
def getint(string: str | None) -> int | None:
    """Interpret string as integer or, if not possible, return None.
    """
    if not string:
        return None
    try:
        return extract_int(string)
    except ValueError:
        return None


@type_checker(str, none_allowed=True)
def getbool(string: str | None) -> bool | None:
    """Interpret string as boolean value or, if not possible, return None
    """
    if not string:
        return None
    if string.lower() == "false":
        return False
    elif string.lower() == "true":
        return True
    return None


@type_checker(str)
def camel_case_split(text: str) -> list[str]:
    """Do camel-case split on ``text``.

    Taken from:
        https://stackoverflow.com/a/58996565/4465708

    Args:
        text: text to be split

    Returns:
        a list of parts
    """
    bools = [char.isupper() for char in text]
    # mark change of case
    upper_chars_indices = [0]  # e.g.: [0, 8, 8, 17, 17, 25, 25, 28, 29]
    for (i, (first_char_is_upper, second_char_is_upper)) in enumerate(zip(bools, bools[1:])):
        if first_char_is_upper and not second_char_is_upper:  # "Cc"
            upper_chars_indices.append(i)
        elif not first_char_is_upper and second_char_is_upper:  # "cC"
            upper_chars_indices.append(i + 1)
    upper_chars_indices.append(len(text))
    # for "cCc", index of "C" will pop twice, have to filter that
    return [text[x:y] for x, y in zip(upper_chars_indices, upper_chars_indices[1:]) if x < y]


def totuple(lst: list) -> tuple:
    """Convert ``lst`` and any list it contains (no matter the nesting level) recursively to tuple.

    Taken from:
        https://stackoverflow.com/a/27050037/4465708
    """
    return tuple(totuple(i) if isinstance(i, list) else i for i in lst)


def tolist(tpl: tuple) -> list:
    """Convert ``tpl`` and any tuple it contains (no matter the nesting level) recursively to list.

    Taken from and made in reverse:
        https://stackoverflow.com/a/27050037/4465708
    """
    return list(tolist(i) if isinstance(i, tuple) else i for i in tpl)


def cleardir(obj: object) -> list[str]:
    """Return ``dir(obj)`` without extraneous fluff.
    """
    return [attr for attr in dir(obj) if not attr.startswith("_")]


def from_iterable(iterable: Iterable[T], predicate: Callable[[T], bool]) -> Optional[T]:
    """Return item from ``iterable`` based on ``predicate`` or ``None``, if it cannot be found.
    """
    return next((item for item in iterable if predicate(item)), None)


@uniform_type_checker(str)
def breadcrumbs(*crumbs: str) -> str:
    """Return a breadcrumb string based on ``crumbs`` supplied.

    Example:
        `/foo/bar/fiz/baz`
    """
    return "/" + "/".join(crumbs)


def timestamp(format_=FILENAME_TIMESTAMP_FORMAT) -> str:
    """Return timestamp string according to the datetime ``format_`` supplied.
    """
    return datetime.now().strftime(format_)


class ParsingError(ValueError):
    """Raised on unexpected states of parsed data.
    """
