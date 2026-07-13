from apscheduler.triggers.cron import CronTrigger
from croniter import croniter


def cron_trigger(expression: str) -> CronTrigger:
    """Build an APScheduler trigger using standard cron weekday numbering."""
    fields = expression.strip().split()
    weekdays = croniter.expand(expression)[0][4]
    if weekdays != ['*']:
        names = ('sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat')
        fields[4] = ','.join(names[day] for day in weekdays)
    return CronTrigger.from_crontab(' '.join(fields))
