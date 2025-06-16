import datetime

_SQL_FORMAT = "%Y-%m-%d %H:%M:%S"
_UTC = datetime.timezone.utc     # convenience alias

def now_dt():
    return datetime.datetime.now(_UTC)

def dt_to_sql_timestamp(dt: datetime.datetime) -> str:
    """
    Convert a timezone-aware or naive UTC datetime → SQLite TIMESTAMP string.
    Result matches CURRENT_TIMESTAMP: 'YYYY-MM-DD HH:MM:SS'.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)        # assume already UTC
    return dt.astimezone(_UTC).strftime(_SQL_FORMAT)

def sql_timestamp_to_dt(ts: str) -> datetime.datetime:
    """
    Parse 'YYYY-MM-DD HH:MM:SS' → timezone-aware UTC datetime.
    """
    return datetime.datetime.strptime(ts, _SQL_FORMAT).replace(tzinfo=_UTC)