

import logging
import datetime
import os

class BaseConfig(object):
    DEBUG = True
    LOGGING_LEVEL = logging.INFO
    LOGGING_LOCATION = str(os.environ['LOGGING_LOCATION']).strip()
    POSTGRES_HOST = str(os.environ['POSTGRES_HOST']).strip()
    POSTGRES_USER = str(os.environ['POSTGRES_USER']).strip()
    POSTGRES_PORT = int(os.environ['POSTGRES_PORT'])
    POSTGRES_PASSWORD = str(os.environ['POSTGRES_PASSWORD']).strip()
    POSTGRES_DB = str(os.environ['POSTGRES_DB']).strip()
    API_HOST =  str(os.environ['API_HOST']).strip()
    API_PORT = int(os.environ['API_PORT'])