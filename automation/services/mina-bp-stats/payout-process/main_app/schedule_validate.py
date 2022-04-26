import subprocess
import datefinder
from datetime import datetime, timedelta
import time
from apscheduler.schedulers.blocking import BlockingScheduler
import pytz
from dateutil.relativedelta import relativedelta
import warnings
warnings.filterwarnings("ignore")
from logger_util import logger

utc = pytz.UTC


def find_epoch_no():
    logger.info("Starting Of python Script")
    script_output = subprocess.call(['python3', 'payouts_validate.py'])
    return script_output


def extract_date_from_text_file():
    file = open("genesis_time.txt", 'r')
    content = file.read()
    matches = list(datefinder.find_dates(content))
    if len(matches) > 0:
        for genesis_t in matches:
            logger.info(genesis_t)
    else:
        logger.info("Found no dates.")
    return genesis_t


def find_out_current_date():
    current_date = datetime.today()
    return current_date


def find_next_job_time(genesis_t, minutes_to_add):
    next_job_time = genesis_t + timedelta(minutes=minutes_to_add)
    next_job_time = next_job_time.replace(tzinfo=None)
    return next_job_time


def main():
    script_output = find_epoch_no()
    if script_output <= 1:
        minutes_to_add = 10

    else:
        minute_per_epoch = 21420
        next_epoch_number = script_output + 2
        minutes_to_add = minute_per_epoch * next_epoch_number
        minutes_to_add = (minutes_to_add + (3500 * 3))

    genesis_t = extract_date_from_text_file()
    next_job_time = find_next_job_time(genesis_t, minutes_to_add)

    current_date = find_out_current_date()

    if current_date > next_job_time:
        str_minutes = 10
        next_job_time = current_date + timedelta(minutes=str_minutes)

    next_day = next_job_time + timedelta(days=1)
    next_day = next_day.date()
    next_day = next_day + relativedelta(minutes=30)
    print(next_day)

    # Scheduling task
    def job(text):
        t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        print('{} --- {}'.format(text, t))

    scheduler = BlockingScheduler()

    scheduler.add_job(job, 'interval', minutes=0, seconds=0, start_date=next_day, args=['job2'])
    scheduler.start()


if __name__ == '__main__':
    main()
