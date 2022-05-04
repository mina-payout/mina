import datetime
import datefinder
from datetime import datetime, timedelta
import sys
import time
from apscheduler.schedulers.blocking import BlockingScheduler


def current_time_and_date():
    now = datetime.now()
    current_date_time = now.strftime("%Y-%m-%d %H:%M:%S%z")
    current_date_time = datetime.strptime(current_date_time, "%Y-%m-%d %H:%M:%S")
    return current_date_time


def find_genesis_time():
    file = open("genesis_time.txt", 'r')
    content = file.read()

    # datefinder will find the dates for us
    matches = list(datefinder.find_dates(content))

    if len(matches) > 0:
        for genesis_t in matches:
            print(genesis_t)
    else:
        print("Found no dates.")

    return genesis_t


def find_next_job_time(genesis_t, minutes_to_add):
    next_job_time = genesis_t + timedelta(minutes=minutes_to_add)
    return next_job_time


def log_file_creation(next_job_time, formatted_next_job_time):
    old_stdout = sys.stdout
    log_file = open("message.log", "w")
    sys.stdout = log_file
    print(next_job_time)
    print(formatted_next_job_time)
    sys.stdout = old_stdout
    log_file.close()


def main():
    current_date = current_time_and_date()
    genesis_t = find_genesis_time()
    final_date = current_date.timestamp()
    start_date = genesis_t.timestamp()

    MPHR = 60  # Minutes per hour
    minutes = (final_date - start_date) // MPHR
    minute_per_epoch = 21420
    next_epoch_number = ((minutes // minute_per_epoch) + 1)
    minutes_to_add = ((minute_per_epoch * next_epoch_number) + 100)
    next_job_time = find_next_job_time(genesis_t, minutes_to_add)

    formatted_next_job_time = next_job_time.strftime("%Y-%m-%d %H:%M:%S")
    print(formatted_next_job_time)
    log_file_creation(next_job_time, formatted_next_job_time)

    def job(text):
        t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        print('{} --- {}'.format(text, t))

    scheduler = BlockingScheduler()

    # In 2019-08-29 22:15:00 To 2019-08-29 22:17:00 Period, run every 1 minute 30 seconds job Method

    scheduler.add_job(job, 'interval', minutes=0, seconds=0, start_date=formatted_next_job_time, args=['job2'])

    scheduler.start()


if __name__ == '__main__':
    main()