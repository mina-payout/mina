# pip install flask -------- required module

from tokenize import String
from flask import Flask, request
import psycopg2
from config import BaseConfig
from logger_util import logger
from flask import jsonify
from datetime import datetime, timedelta, timezone
from flask_caching import Cache

from flasgger import Swagger
from flasgger import swag_from

# create database connections

ERROR = 'Error: {0}'

def get_snark_conn():
    connection_snark = psycopg2.connect(
        host=BaseConfig.SNARK_HOST,
        port=BaseConfig.SNARK_PORT,
        database=BaseConfig.SNARK_DB,
        user=BaseConfig.SNARK_USER,
        password=BaseConfig.SNARK_PASSWORD
    )
    return connection_snark

def get_sidecar_conn():
    connection_sd = psycopg2.connect(
        host=BaseConfig.SIDECAR_HOST,
        port=BaseConfig.SIDECAR_PORT,
        database=BaseConfig.SIDECAR_DB,
        user=BaseConfig.SIDECAR_USER,
        password=BaseConfig.SIDECAR_PASSWORD
    )
    return connection_sd

config = {
    "DEBUG": True,  # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": BaseConfig.CACHE_TIMEOUT
}

# create app instance
app = Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)
swagger = Swagger(app)


#  get data from table
@cache.memoize(timeout=BaseConfig.CACHE_TIMEOUT)
def get_json_data_current(conn=get_snark_conn()):
    query = """SELECT block_producer_key , score ,score_percent FROM nodes WHERE application_status = true and score 
    is not null ORDER BY score DESC """
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in cursor.fetchall()]
        logger.info("fetch data for flask app...")
    except (Exception, psycopg2.DatabaseError) as error:
        logger.info(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result

#  get score at specific time
@cache.memoize(timeout=BaseConfig.CACHE_TIMEOUT)
def get_json_data(conn=get_snark_conn(), score_at=None):
    if 'current'==score_at:
        return get_json_data_current(conn)
    
    score_time = datetime.strptime(score_at, '%Y-%m-%dT%H:%M:%SZ')
    query = """with vars  (end_date, start_date) as( values (%s::timestamp , 
			(%s::timestamp)- interval '60' day )
	)
	, epochs as(
		select extract('epoch' from end_date) as end_epoch,
		extract('epoch' from start_date) as start_epoch from vars
	)
	, b_logs as(
		select (count(1) ) as surveys
		from bot_logs b , vars e
		where b.file_timestamps between start_date and end_date
	)
	, scores as (
		select p.node_id, count(p.bot_log_id) bp_points
		from points_summary p join bot_logs b on p.bot_log_id =b.id, vars
		where b.file_timestamps between start_date and end_date
		group by 1
	)
	select n.block_producer_key , bp_points, surveys, 
		trunc( ((bp_points::decimal*100) / surveys),2) as score_percent
	from scores l join nodes n on l.node_id=n.id, b_logs t
	order by 2 desc	; """
    try:
        cursor = conn.cursor()
        cursor.execute(query, (score_time, score_time))
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in cursor.fetchall()]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.info(ERROR.format(error))
        cursor.close()
        conn.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result




#path params 1
@app.route('/uptimeScore/', endpoint='without_data_type_score_at')
@app.route('/uptimeScore/<path:dataType>', endpoint='without_score_at')
@app.route('/uptimeScore/<path:dataType>/<path:scoreAt>', endpoint='all')
@swag_from('api_spec_without_data_type_score_at.yml', endpoint='without_data_type_score_at')
@swag_from('api_spec_without_score_at.yml', endpoint='without_score_at')
@swag_from('api_spec.yml', endpoint='all')
def get_score(dataType='snarkwork', scoreAt='current'):
    data = None
    logger.info('dt: {0}, time:{1}'.format(dataType, scoreAt))
    if 'snarkwork' == dataType:
        data = get_json_data(get_snark_conn(), scoreAt)
    elif 'sidecar' == dataType:
        data = get_json_data(get_sidecar_conn(), scoreAt)
    
    return jsonify(data)



if __name__ == '__main__':
    app.run(host=BaseConfig.API_HOST, port=BaseConfig.API_PORT, debug=False)
