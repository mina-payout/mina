import logging
import datetime
import os

class BaseConfig(object):
    DEBUG = False
    TESTING = False
    LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOGGING_LEVEL = logging.WARN
    LOGGING_LOCATION = '/var/log/minanet/'

    POSTGRES_HOST = str(os.environ['POSTGRES_HOST']).strip()
    POSTGRES_PORT = int(os.environ['POSTGRES_PORT'])
    POSTGRES_USER = str(os.environ['POSTGRES_USER']).strip()
    POSTGRES_PASSWORD = str(os.environ['POSTGRES_PASSWORD']).strip()
    POSTGRES_DB = str(os.environ['POSTGRES_DB']).strip()

    CREDENTIAL_PATH = 'mina-mainnet-303900-45050a0ba37b.json'
    GCS_BUCKET_NAME = 'block-producer-stats'
    PROVIDER_ACCOUNT_PUB_KEYS_FILE = 'Mina_Foundation_Addresses.csv'
    SURVEY_INTERVAL_MINUTES = 10
    UPTIME_DAYS_FOR_SCORE = 60
    FROM_EMAIL = ''
    TO_EMAILS = ['', '']
    SUBJECT = 'Ontab-key LeaderBoard positions As of {0}'.format(datetime.datetime.utcnow())
    PLAIN_TEXT = 'Report for Leaderboard as of {0}'.format(datetime.datetime.utcnow())
    SENDGRID_API_KEY = ''
    SPREADSHEET_SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    SPREADSHEET_NAME = 'Mina Foundation Delegation Application (Responses)'
    SPREADSHEET_JSON = 'mina-foundation-delegation-app-b889c28d5b9b.json'
    MAX_THREADS_TO_DOWNLOAD_FILES= 128
