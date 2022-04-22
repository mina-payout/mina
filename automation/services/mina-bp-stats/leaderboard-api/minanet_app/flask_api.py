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
def get_json_data_current(conn=connection_snark):
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
    return result

#  get score at specific time
@cache.memoize(timeout=BaseConfig.CACHE_TIMEOUT)
def get_json_data(conn=connection_snark, score_at=None):
    if 'current'==score_at:
        return get_json_data_current(conn)
    
    score_time = datetime.strptime(score_at, '%Y-%m-%dT%H:%M:%SZ')
    query = """with vars  (snapshot_date, start_date) as( values (%s::timestamp , 
			(%s::timestamp)- interval '60' day )
	)
	, epochs as(
			select extract('epoch' from snapshot_date) as end_epoch, 
		extract('epoch' from start_date) as start_epoch from vars
	)
	,  b_logs as(
		select (count(1) ) as surveys 
		from bot_logs b , epochs e
		where b.batch_start_epoch between start_epoch and end_epoch 
	)
	,lastboard as (
         select node_id,count(distinct bot_log_id) total_points
         from  points prt , vars 
         where (file_timestamps + (330 * interval '1 minute')) between start_date and snapshot_date
         group by node_id
     )
         select node_id, n.block_producer_key , total_points, surveys,  trunc( ((total_points::decimal*100) / surveys),2) as score_perc
         from lastboard l join nodes n on l.node_id=n.id, b_logs t 
         order by 3 desc """
    try:
        cursor = conn.cursor()
        cursor.execute(query, (score_time, score_time))
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in cursor.fetchall()]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.info(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
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
        data = get_json_data(connection_snark, scoreAt)
    elif 'sidecar' == dataType:
        data = get_json_data(connection_sd, scoreAt)
    
    return jsonify(data)



if __name__ == '__main__':
    app.run(host=BaseConfig.API_HOST, port=BaseConfig.API_PORT, debug=True)
