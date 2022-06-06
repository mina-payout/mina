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
    try:
        connection_snark = psycopg2.connect(
            host=BaseConfig.SNARK_HOST,
            port=BaseConfig.SNARK_PORT,
            database=BaseConfig.SNARK_DB,
            user=BaseConfig.SNARK_USER,
            password=BaseConfig.SNARK_PASSWORD
        )
    except (Exception, psycopg2.OperationalError) as error:
        logger.error(ERROR.format(error))
        raise ValueError('System is down. Please try again later.')
    return connection_snark


def get_sidecar_conn():
    try:
        connection_sd = psycopg2.connect(
            host=BaseConfig.SIDECAR_HOST,
            port=BaseConfig.SIDECAR_PORT,
            database=BaseConfig.SIDECAR_DB,
            user=BaseConfig.SIDECAR_USER,
            password=BaseConfig.SIDECAR_PASSWORD
        )
    except (Exception, psycopg2.OperationalError) as error:
        logger.error(ERROR.format(error))
        raise ValueError('System is down. Please try again later.')
    return connection_sd


config = {
    "DEBUG": True,  # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": BaseConfig.CACHE_TIMEOUT
}

# # ![MINA logo](https://cdn-fagpn.nitrocdn.com/nvawPUgmLuenSpEkZxPTWilYhwRGNGyf/assets/static/optimized/rev-e46fd70/wp-content/themes/minaprotocol/img/mina-wordmark-light.svg)
template = {
  "swagger": "2.0",
  "info": {
    "title": "MINA Open API for Uptime Data",
    "description": 
        "API for Sidecar and SNARK uptime data for MINA leaderboard \n ##"
        ,
    "termsOfService": "https://minaprotocol.com/tos",
    "version": "1.0.1"
  },
  "host": BaseConfig.SWAGGER_HOST,  # overrides localhost:500
  "basePath": "/uptimescore",  # base bash for blueprint registration
  "schemes": [
    "http",
    "https"
  ],
  "operationId": "uptimescore"
}


# create app instance
app = Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)
swagger = Swagger(app, template=template)

# 1
def get_current_snark_data_for_all():
    conn=get_snark_conn()
    query = """SELECT block_producer_key , score ,score_percent FROM nodes WHERE application_status = true and score 
    is not null ORDER BY score DESC """
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in
                  cursor.fetchall()]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result
# 2
def get_current_snark_data_for_one(filter_pub_key):
    conn=get_snark_conn()
    query = """select n.block_producer_key , sh.score , sh.score_percent 
        from score_history sh join nodes n on n.id =sh.node_id 
        where n.block_producer_key = %s
        order by score_at desc limit 1	; """
    try:
        cursor = conn.cursor()
        cursor.execute(query, (filter_pub_key,))
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in
                  cursor.fetchall()]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result
# 3
def get_historic_snark_data_for_all(score_at):
    conn=get_snark_conn()
    query = """with recent_time as(
                select score_at
                from score_history sh 
                where sh.score_at < %s
                order by sh.score_at desc limit 1
            )
            select n.block_producer_key , sh.score , sh.score_percent 
            from recent_time r join score_history sh on r.score_at=sh.score_at ; """
    try:
        cursor = conn.cursor()
        cursor.execute(query, (score_at,))
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in
                  cursor.fetchall()]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result

# 4
def get_historic_snark_data_for_one(score_at, filter_pub_key):
    conn=get_snark_conn()
    query = """with recent_time as(
                select score_at
                from score_history sh 
                where sh.score_at < %s
                order by sh.score_at desc limit 1
            )
            select n.block_producer_key , sh.score , sh.score_percent 
            from recent_time r join score_history sh on r.score_at=sh.score_at
            join nodes n on n.id =sh.node_id and n.block_producer_key =%s; """
    try:
        cursor = conn.cursor()
        cursor.execute(query, (score_at,filter_pub_key))
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in
                  cursor.fetchall()]
        print(result)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result


# 5
def get_current_sidecar_data_for_all():
    conn=get_sidecar_conn()
    query = """SELECT block_producer_key , score ,score_percent FROM nodes WHERE application_status = true and score 
    is not null ORDER BY score DESC; """
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in
                  cursor.fetchall()]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result

# 6
def get_current_sidecar_data_for_one( filter_pub_key):
    conn=get_sidecar_conn()
    query = """SELECT block_producer_key , score ,score_percent FROM nodes 
        WHERE block_producer_key= %s and application_status = true and score is not null ORDER BY score DESC; """
    try:
        cursor = conn.cursor()
        cursor.execute(query, (filter_pub_key,))
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in
                  cursor.fetchall()]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result

# 7
def get_historic_sidecar_data_for_all(score_time):
    conn=get_sidecar_conn()
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
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in
                  cursor.fetchall()]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result

# 8
def get_historic_sidecar_data_for_one(score_time, filter_pub_key):
    conn=get_sidecar_conn()
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
		from nodes n join points_summary p on n.id=p.node_id
            join bot_logs b on p.bot_log_id =b.id, vars
		where n.block_producer_key= %s and b.file_timestamps between start_date and end_date
		group by 1
	)
	select n.block_producer_key , bp_points, surveys, 
		trunc( ((bp_points::decimal*100) / surveys),2) as score_percent
	from scores l join nodes n on l.node_id=n.id, b_logs t
	order by 2 desc	; """
 
    try:
        cursor = conn.cursor()
        cursor.execute(query, (score_time, score_time, filter_pub_key))
        result = [dict((cursor.description[i][0], str(value)) for i, value in enumerate(row)) for row in
                  cursor.fetchall()]
        print(result)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result



# path params 1
@app.route('/uptimescore/', endpoint='without_data_type_score_at')
@app.route('/uptimescore/<path:pubkey>', endpoint='with_pubkey')
@app.route('/uptimescore/<path:pubkey>/<path:dataType>/', endpoint='without_score_at')
@app.route('/uptimescore/<path:pubkey>/<path:dataType>/<path:scoreAt>/', endpoint='all')
@swag_from('api_spec_withpubkey.yml', endpoint='with_pubkey')
@swag_from('api_spec_without_data_type_score_at.yml', endpoint='without_data_type_score_at')
@swag_from('api_spec_without_score_at.yml', endpoint='without_score_at')
@swag_from('api_spec.yml', endpoint='all')
def get_score(pubkey='',dataType='snarkwork', scoreAt='current'):
    pubkey = pubkey.replace("/","")
    dataType = dataType.replace("/","")
    scoreAt = scoreAt.replace("/","")
    
    print('dt: {0}, time:{1}, pubkey:{2}'.format(dataType, scoreAt, pubkey))
    logger.info('dt: {0}, time:{1}'.format(dataType, scoreAt))
    score_time = None
    if scoreAt != 'current':
        try:
            datetime.strptime(scoreAt, '%Y-%m-%dT%H:%M:%SZ')
            score_time = datetime.strptime(scoreAt, '%Y-%m-%dT%H:%M:%SZ')
        except Exception as e:
            response = {
                "Error": 'Invalid Date Format',
                "Error_message": "Please make sure you use Valid Date in Format:2022-04-30T08:30:00Z"
            }
            return jsonify(response), 404

    filter_pub_key= None

    if pubkey.startswith('B62') and len(pubkey)==55:
        filter_pub_key = pubkey
    elif pubkey in ['snarkwork', 'sidecar']:
        dataType=pubkey
    elif len(pubkey)>0:
        response = {
            "Error": 'Invalid public key',
            "Error_message": "Please provide correct public key"
        }
        return jsonify(response), 404
  
    if dataType not in ['snarkwork', 'sidecar']:
        response = {
            "Error": 'Invalid datatype',
            "Error_message": "Please provide datatype as snarkwork or sidecar"
        }
        return jsonify(response), 404
    data = None
    try:
        if 'snarkwork' == dataType and score_time is None and filter_pub_key is None:
            print(get_current_snark_data_for_all)
            data = get_current_snark_data_for_all()
        elif 'snarkwork' == dataType and score_time is None and filter_pub_key is not None:
            print(get_current_snark_data_for_one)
            data = get_current_snark_data_for_one(filter_pub_key)
        elif 'snarkwork' == dataType and score_time is not None and filter_pub_key is None:
            print(get_historic_snark_data_for_all)
            data = get_historic_snark_data_for_all(score_time)
        elif 'snarkwork' == dataType and score_time is not None and filter_pub_key is not None:
            print(get_historic_snark_data_for_one)
            data = get_historic_snark_data_for_one(score_time, filter_pub_key)

        elif 'sidecar' == dataType and score_time is None and filter_pub_key is None:
            print(get_current_sidecar_data_for_all)
            data = get_current_sidecar_data_for_all()
        elif 'sidecar' == dataType and score_time is None and filter_pub_key is not None:
            print(get_current_sidecar_data_for_one)
            data = get_current_sidecar_data_for_one(filter_pub_key)
        elif 'sidecar' == dataType and score_time is not None and filter_pub_key is None:
            print(get_historic_sidecar_data_for_all)
            data = get_historic_sidecar_data_for_all(score_time)
        elif 'sidecar' == dataType and score_time is not None and filter_pub_key is not None:
            print(get_historic_sidecar_data_for_one)
            data = get_historic_sidecar_data_for_one(score_time, filter_pub_key)
        else:
            response = {
                "Error": 'Something went wrong',
                "Error_message": "Please try again with different parameters"
            }
            return jsonify(response), 500
    except ValueError as e:
            response = {
                "Error": 'Something went wrong',
                "Error_message": "System is down. Please try again later."
            }
            return jsonify(response), 500
    if not data:
        response = {
            "Error": 'No data found',
            "Error_message": "Please try again with different parameters"
        }
        return jsonify(response), 404
    return jsonify(data)


@app.errorhandler(404)
def handle_exception(e):
    response = {
        "Error": 'Page Not Found',
        "Error_message": "Please make sure you use Correct URL"
    }
    return jsonify(response), 404


@app.errorhandler(500)
def handle_exception(e):
    response = {
        "error": 'Internal Server Error',
        "error_message": "Something went wrong we are working on it."
    }
    return jsonify(response), 500


if __name__ == '__main__':
    app.run(host=BaseConfig.API_HOST, port=BaseConfig.API_PORT, debug=True)
