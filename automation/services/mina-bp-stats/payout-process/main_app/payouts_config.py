import datetime
import logging
import os

class BaseConfig(object):
    LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOGGING_LEVEL = logging.INFO
    LOGGING_LOCATION = str(os.environ['LOGGING_LOCATION']).strip()
    POSTGRES_ARCHIVE_HOST = str(os.environ['POSTGRES_ARCHIVE_HOST']).strip()
    POSTGRES_ARCHIVE_PORT = int(os.environ['POSTGRES_ARCHIVE_PORT'])
    POSTGRES_ARCHIVE_USER =  str(os.environ['POSTGRES_ARCHIVE_USER']).strip()
    POSTGRES_ARCHIVE_PASSWORD = str(os.environ['POSTGRES_ARCHIVE_PASSWORD']).strip()
    POSTGRES_ARCHIVE_DB = str(os.environ['POSTGRES_ARCHIVE_DB']).strip()

    POSTGRES_PAYOUT_HOST = str(os.environ['POSTGRES_PAYOUT_HOST']).strip()
    POSTGRES_PAYOUT_PORT = int(os.environ['POSTGRES_PAYOUT_PORT'])
    POSTGRES_PAYOUT_USER = str(os.environ['POSTGRES_PAYOUT_USER']).strip()
    POSTGRES_PAYOUT_PASSWORD = str(os.environ['POSTGRES_PAYOUT_PASSWORD']).strip()
    POSTGRES_PAYOUT_DB = str(os.environ['POSTGRES_PAYOUT_DB']).strip()

    POSTGRES_LEADERBOARD_HOST = str(os.environ['POSTGRES_LEADERBOARD_HOST']).strip()
    POSTGRES_LEADERBOARD_PORT = int(os.environ['POSTGRES_LEADERBOARD_PORT'])
    POSTGRES_LEADERBOARD_USER = str(os.environ['POSTGRES_LEADERBOARD_USER']).strip()
    POSTGRES_LEADERBOARD_PASSWORD = str(os.environ['POSTGRES_LEADERBOARD_PASSWORD']).strip()
    POSTGRES_LEADERBOARD_DB = str(os.environ['POSTGRES_LEADERBOARD_DB']).strip()

    COINBASE = int(os.environ['COINBASE'])
    SLOT_WINDOW_VALUE = int(os.environ['SLOT_WINDOW_VALUE'])
    
    CREDENTIAL_PATH = str(os.environ['CREDENTIAL_PATH']).strip()
    GCS_BUCKET_NAME = str(os.environ['GCS_BUCKET_NAME']).strip()
    SPREADSHEET_SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    SPREADSHEET_NAME = 'Mina Foundation Delegation Application (Responses)'
    GENESIS_DATE = datetime.datetime(2021, 3, 17)
    DELEGATION_ADDRESSS_CSV = str(os.environ['DELEGATION_ADDRESSS_CSV']).strip()
    CALCULATION_CSV_FILE=str(os.environ['CALCULATION_CSV_FILE']).strip()
    VALIDATION_CSV_FILE=str(os.environ['VALIDATION_CSV_FILE']).strip()
    
    SEND_EMAIL_TO_BP = str(os.environ['SEND_EMAIL_TO_BP'])
    SEND_SECOND_EMAIL_TO_BP = str(os.environ['SEND_SECOND_EMAIL_TO_BP'])
    SEND_SUMMARY_EMAIL = str(os.environ['SEND_SUMMARY_EMAIL'])
    OVERRIDE_EMAIL=os.environ['OVERRIDE_EMAIL']
    FROM_EMAIL = str(os.environ['FROM_EMAIL'])
    PROVIDER_EMAIL =os.environ['PROVIDER_EMAIL'].split(',')
    SUBJECT = 'LeaderBoard Stats As of{0}'.format(datetime.datetime.utcnow())
    PLAIN_TEXT = 'Report for Leaderboard as of {0}'.format(datetime.datetime.utcnow())
    CALCULATE_EMAIL_TEMPLATE = str(os.environ['CALCULATE_EMAIL_TEMPLATE']).strip()
    VALIDATE_EMAIL_TEMPLATE = str(os.environ['VALIDATE_EMAIL_TEMPLATE']).strip()
    SENDGRID_API_KEY =str(os.environ['SENDGRID_API_KEY']).strip()
    ADDRESS_SUBJECT = str(os.environ['ADDRESS_SUBJECT']).strip()