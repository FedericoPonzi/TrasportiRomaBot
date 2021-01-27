from datetime import datetime


def time_left(diff_delta):
    '''
    :param diff_delta: date- datetime.now()
    :return: diff_delta as a telegram message formatted string.
    '''
    m = ""
    diff_minutes = int(diff_delta.seconds / 60)
    hours = int(diff_minutes / 60)
    minutes = diff_minutes % 60

    if diff_delta.days == 1:
        m += "un giorno e "
    if diff_delta.days > 1:
        m += str(diff_delta.days) + " giorni e "
    if hours == 1:
        m += "un'ora "
    if hours > 1:
        m += str(hours) + " ore"
    if minutes == 1:
        m += " un minuto."
    if minutes > 1:
        m += str(minutes) + " minuti."
    return m
