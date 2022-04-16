# pip install flask -------- required module

from tokenize import String
from flask import Flask, request
import psycopg2
from config import BaseConfig
from logger_util import logger
from flask import jsonify
from datetime import datetime, timedelta, timezone


from flasgger import Swagger
from flasgger import swag_from

# create database connections
connection_sd = psycopg2.connect(
    host=BaseConfig.SIDECAR_HOST,
    port=BaseConfig.SIDECAR_PORT,
    database=BaseConfig.SIDECAR_DB,
    user=BaseConfig.SIDECAR_USER,
    password=BaseConfig.SIDECAR_PASSWORD
)
connection_snark = psycopg2.connect(
    host=BaseConfig.SNARK_HOST,
    port=BaseConfig.SNARK_PORT,
    database=BaseConfig.SNARK_DB,
    user=BaseConfig.SNARK_USER,
    password=BaseConfig.SNARK_PASSWORD
)

ERROR = 'Error: {0}'


#  get data from table
def get_json_data_current(conn=connection_snark):
    query = """SELECT block_producer_key , score ,score_percent FROM nodes WHERE application_status = true and score 
    is not null ORDER BY score DESC """
    try:
        cursor = connection_sd.cursor()
        cursor.execute(query)
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in cursor.fetchall()]
        connection_sd.commit()
        logger.info("fetch data for flask app...")
    except (Exception, psycopg2.DatabaseError) as error:
        logger.info(ERROR.format(error))
        connection_sd.rollback()
        cursor.close()
        return -1
    finally:
        connection_sd.commit()
        cursor.close()
    return result


# create app instance
app = Flask(__name__)
swagger = Swagger(app)


#path params 1
@app.route('/uptimeScore/', endpoint='without_data_type_score_at')
@app.route('/uptimeScore/<path:dataType>', endpoint='without_score_at')
@app.route('/uptimeScore/<path:dataType>/<path:scoreAt>', endpoint='all')
@swag_from('api_spec_without_data_type_score_at.yml', endpoint='without_data_type_score_at')
@swag_from('api_spec_without_score_at.yml', endpoint='without_score_at')
@swag_from('api_spec.yml', endpoint='all')
def get_score(dataType, scoreAt):
    data = None
    logger.info('dt: {0}, time:{1}'.format(dataType, scoreAt))
    if 'snarkwork' == dataType:
        data = get_json_data_current(connection_snark)
    elif 'sidecar' == dataType:
        data = get_json_data_current(connection_sd)
    return jsonify(data)



if __name__ == '__main__':
    app.run(host=BaseConfig.API_HOST, port=BaseConfig.API_POST, debug=True)
