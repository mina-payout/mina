from flask import Flask, request
import psycopg2
from flask import jsonify
from logger_util import logger
from config import BaseConfig


def get_conn():
    try:
        connection = psycopg2.connect(
            host=BaseConfig.POSTGRES_HOST,
            port=BaseConfig.POSTGRES_PORT,
            database=BaseConfig.POSTGRES_DB,
            user=BaseConfig.POSTGRES_USER,
            password=BaseConfig.POSTGRES_PASSWORD
        )
    except (Exception, psycopg2.OperationalError) as error:
        logger.error(ERROR.format(error))
        raise ValueError('System is down. Please try again later.')
    return connection


ERROR = 'Error: {0}'

# create app instance
app = Flask(__name__)


def validate_user_details(email, pubkey):
    conn = get_conn()
    query = "SELECT EXISTS (SELECT id FROM nodes WHERE email_id = %s and block_producer_key =%s ) "
    cursor = conn.cursor()
    try:
        cursor.execute(query, (email, pubkey))
        result = cursor.fetchall()
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.close()
    return result[0][0]


@app.route('/userkyc/', methods=['GET'])
def validate_user():

    # getting parameters from query_string
    query_parameters = request.args
    email_id = query_parameters.get('email')
    public_key = query_parameters.get('pubkey')

    isvalid = validate_user_details(email_id, public_key)

    if isvalid == -1:
        response = {
            "Error": 'Something went wrong',
            "Error_message": "Please try again with different parameters"
        }
        return jsonify(response), 500

    return jsonify(isvalid)


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
    app.run(host=BaseConfig.API_HOST, port=BaseConfig.API_PORT, debug=BaseConfig.DEBUG)
