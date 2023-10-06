import logging
from config import BaseConfig
from logging.handlers import RotatingFileHandler

log_file = BaseConfig.LOGGING_LOCATION + 'leaderboard.log'
logging.basicConfig(
        handlers=[RotatingFileHandler(filename=log_file, maxBytes=52428800, backupCount=100)],
        format="[%(asctime)s] %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt='%Y-%m-%dT%H:%M:%S')
# Creating an object
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.ERROR)

