import logging
import datetime
import os

class BaseConfig(object):
    DEBUG = False
    LOGGING_LEVEL = logging.INFO
    LOGGING_LOCATION = str(os.environ['LOGGING_LOCATION']).strip()

    POSTGRES_HOST = str(os.environ['POSTGRES_HOST']).strip()
    POSTGRES_PORT = int(os.environ['POSTGRES_PORT'])
    POSTGRES_USER = str(os.environ['POSTGRES_USER']).strip()
    POSTGRES_PASSWORD = str(os.environ['POSTGRES_PASSWORD']).strip()
    POSTGRES_DB = str(os.environ['POSTGRES_DB']).strip()

    CREDENTIAL_PATH = str(os.environ['CREDENTIAL_PATH']).strip()
    GCS_BUCKET_NAME = str(os.environ['GCS_BUCKET_NAME']).strip()
    PROVIDER_ACCOUNT_PUB_KEYS_FILE = str(os.environ['PROVIDER_ACCOUNT_PUB_KEYS_FILE']).strip()
    SURVEY_INTERVAL_MINUTES = int(os.environ['SURVEY_INTERVAL_MINUTES'])
    UPTIME_DAYS_FOR_SCORE = int(os.environ['UPTIME_DAYS_FOR_SCORE'])
    FROM_EMAIL = str(os.environ['FROM_EMAIL']).strip()
    TO_EMAILS = str(os.environ['TO_EMAILS']).strip()
    SUBJECT = str(os.environ['SUBJECT']).strip()
    PLAIN_TEXT = str(os.environ['PLAIN_TEXT']).strip()
    SENDGRID_API_KEY = str(os.environ['SENDGRID_API_KEY']).strip()
    SPREADSHEET_SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    SPREADSHEET_NAME = str(os.environ['SPREADSHEET_NAME']).strip()
    SPREADSHEET_JSON = str(os.environ['SPREADSHEET_JSON']).strip()
    MAX_THREADS_TO_DOWNLOAD_FILES= str(os.environ['MAX_THREADS_TO_DOWNLOAD_FILES']).strip()
    SUBMISSION_DIR = str(os.environ['SUBMISSION_DIR']).strip()
    BLOCK_DIR = str(os.environ['BLOCK_DIR']).strip()
    ROOT_DIR = str(os.environ['ROOT_DIR']).strip()
    MAX_VERIFIER_INSTANCES = int(os.environ['MAX_VERIFIER_INSTANCES'])
    MAX_CPU_PER_INNSTANCE = int(os.environ['MAX_CPU_PER_INNSTANCE'])
    START_SCRIPT_EPOCH = int(os.environ['START_SCRIPT_EPOCH'])
    END_SCRIPT_EPOCH = int(os.environ['END_SCRIPT_EPOCH'])
    PERCENT_PARAM = float(os.environ['PERCENT_PARAM'])
    MAX_DEPTH_INCLUDE=int(os.environ['MAX_DEPTH_INCLUDE'])