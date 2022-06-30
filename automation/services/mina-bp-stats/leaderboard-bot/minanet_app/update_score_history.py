from datetime import datetime, timedelta, timezone
from time import time
import psycopg2
import psycopg2.extras as extras
import pandas as pd
from config import BaseConfig
import itertools
from logger_util import logger

connection = psycopg2.connect(
    host=BaseConfig.POSTGRES_HOST,
    port=BaseConfig.POSTGRES_PORT,
    database=BaseConfig.POSTGRES_DB,
    user=BaseConfig.POSTGRES_USER,
    password=BaseConfig.POSTGRES_PASSWORD
)

def get_date_list(conn=connection):
    cursor = conn.cursor()
    try:
        sql_select = """
        select to_timestamp(batch_end_epoch) end_date from bot_logs bl 
        where id>1 ORDER BY 1 
        """
        cursor.execute(sql_select)
        rows = cursor.fetchall()
        result_list = list(itertools.chain(*rows))

    except (Exception, psycopg2.DatabaseError) as error:
        
        cursor.close()
        return -1
    finally:
        cursor.close()
    return result_list


def update_scoreboard(conn, score_till_time):
    sql = """with vars  (snapshot_date, start_date) as( values (%s AT TIME ZONE 'UTC', 
			(%s - interval '%s' day) AT TIME ZONE 'UTC')
	)
	, epochs as(
		select extract('epoch' from snapshot_date) as end_epoch,
		extract('epoch' from start_date) as start_epoch from vars
	)
	, b_logs as(
		select (count(1) ) as surveys
		from bot_logs b , epochs e
		where  id>1 and b.batch_end_epoch between start_epoch and end_epoch
	)
	, scores as (
		select p.node_id, count(distinct p.bot_log_id) bp_points
		from points_summary p join bot_logs b on p.bot_log_id =b.id, epochs
		where b.batch_end_epoch between start_epoch and end_epoch
		group by 1
	)
	insert into score_history (node_id, score_at, score, score_percent)
	select node_id, snapshot_date, bp_points, 
		trunc( ((bp_points::decimal*100) / surveys),2) as score_perc
	from scores l join nodes n on l.node_id=n.id, b_logs t, vars
	
	 """

    history_sql="""insert into score_history (node_id, score_at, score, score_percent)
        SELECT id as node_id, %s, score, score_percent from nodes where score is not null """
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (score_till_time, score_till_time, BaseConfig.UPTIME_DAYS_FOR_SCORE,))
        
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(error)
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.commit()
    return 0


def main():
    dates = get_date_list()
    for d in dates:
        update_scoreboard(connection, d)

if __name__ == '__main__':
    main()