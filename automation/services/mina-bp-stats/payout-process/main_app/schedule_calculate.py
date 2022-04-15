import datefinder
from datetime import datetime, timedelta, date
import time
from apscheduler.schedulers.blocking import BlockingScheduler
import subprocess as sp
import pytz
from dateutil.relativedelta import relativedelta

utc = pytz.UTC


def find_epoch_no():
    print("Starting Of python Script")
    script_output = sp.getoutput('python payouts_calculate.py')
    script_output = script_output.splitlines()[0]
    return script_output


def extract_date_from_text_file():
    file = open("genesis.txt", 'r')
    content = file.read()
    matches = list(datefinder.find_dates(content))
    if len(matches) > 0:
        for genesis_t in matches:
            print(genesis_t)
    else:
        print("Found no dates.")
    return genesis_t


def find_out_current_date():
    current_date = datetime.today()
    current_date = current_date.replace(tzinfo=utc)
    return current_date


def find_next_job_time(genesis_t, minutes_to_add):
    next_job_time = genesis_t + timedelta(minutes=minutes_to_add)
    next_job_time = next_job_time.replace(tzinfo=utc)
    return next_job_time


def main():
    script_output = find_epoch_no()
    script_output = int(script_output)

    if script_output <= 1:
        minutes_to_add = 1

    else:
        minute_per_epoch = 21420
        next_epoch_number = script_output + 2
        minutes_to_add = minute_per_epoch * next_epoch_number
        minutes_to_add = minutes_to_add + 300

    genesis_t = extract_date_from_text_file()
    next_job_time = find_next_job_time(genesis_t, minutes_to_add)

    current_date = find_out_current_date()

    if current_date > next_job_time:
        str_minutes = 10
        next_job_time = current_date + timedelta(minutes=str_minutes)

    next_day = next_job_time + timedelta(days=1)

    next_day = next_day.date()

    # Scheduling task
    next_day = next_day + relativedelta(minutes=30)

    def job(text):
        t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        print('{} --- {}'.format(text, t))

    scheduler = BlockingScheduler()

    scheduler.add_job(job, 'interval', hours=0, minutes=0, seconds=0, start_date=next_day,
                      args=['calculation'])
    scheduler.start()


if __name__ == '__main__':
    main()
