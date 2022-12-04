import datetime
import signal


def get_KST_date() -> str:
    """
    get date string for naming

    Returns:
        date string (format: '_%04d-%02d-%02d_%02d:%02d')
    """
    KST = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(tz=KST)
    return "_%04d-%02d-%02d_%02d:%02d" % (
        now.year,
        now.month,
        now.day,
        now.hour,
        now.minute,
    )

def TimedInput(caption: str, default="no\n", timeout=5) -> str:
    """
    Input() with timeout and default value

    Args:
        caption: displayed message
        default: default answer
        timeout: timeout

    Returns:
        answer or default
    """

    def timeout_error(*_):
        raise TimeoutError

    signal.signal(signal.SIGALRM, timeout_error)
    signal.alarm(timeout)
    try:
        answer = input(caption)
        signal.alarm(0)
        return answer
    except TimeoutError:
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        return default