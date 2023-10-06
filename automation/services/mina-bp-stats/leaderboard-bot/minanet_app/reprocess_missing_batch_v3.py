import os
from datetime import datetime, timedelta, timezone
from time import time
import time as tm
import json
import calendar
import numpy as np
from config import BaseConfig
import psycopg2
import psycopg2.extras as extras
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from logger_util import logger
import shutil
from multiprocessing import processing_batch_files
import networkx as nx

import warnings
from survey_collect_v3 import get_relation_list, download_uptime_files, create_empty_folders
from survey_collect_v3 import download_dat_files, get_state_hash_df, get_existing_nodes, get_previous_statehash
from survey_collect_v3 import find_new_values_to_insert, create_statehash, create_node_record
from survey_collect_v3 import create_uptime_file_history, filter_state_hash_percentage, create_graph, update_scoreboard
from survey_collect_v3 import apply_weights, bfs, create_bot_log, insert_state_hash_results, create_point_record

warnings.filterwarnings('ignore')

connection = psycopg2.connect(
    host=BaseConfig.POSTGRES_HOST,
    port=BaseConfig.POSTGRES_PORT,
    database=BaseConfig.POSTGRES_DB,
    user=BaseConfig.POSTGRES_USER,
    password=BaseConfig.POSTGRES_PASSWORD
)
ERROR = 'Error: {0}'


def get_missing_batch(conn=connection):
    cursor = conn.cursor()
    try:
        # default values
        bot_log_id = 0
        batch_start_epoch = 0
        batch_end_epoch = 0

        query = """
            WITH recursive missing_bots AS (
        (SELECT b.id, file_timestamps,  batch_start_epoch , batch_end_epoch  
        FROM bot_logs b
        where batch_start_epoch =  (select max(batch_start_epoch) from bot_logs bl)
        order by batch_start_epoch asc
        )
        union all
        SELECT b.id, b.file_timestamps, b.batch_start_epoch , b.batch_end_epoch  
        FROM bot_logs b inner join missing_bots m on b.batch_end_epoch =m.batch_start_epoch
        )
        select (select id from bot_logs bl where batch_end_epoch=m.batch_start_epoch -1200) as prev_bl_id,
        batch_start_epoch -1200 as new_start, batch_start_epoch as new_end
        from missing_bots m
        order by batch_end_epoch asc
        limit 1
        """
        cursor.execute(query)
        result = cursor.fetchone()
        # check the result contains values
        if result:
            bot_log_id = result[0]
            batch_start_epoch = datetime.fromtimestamp(result[1], timezone.utc)
            batch_end_epoch = datetime.fromtimestamp(result[2], timezone.utc)

    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return bot_log_id, batch_start_epoch, batch_end_epoch

def check_for_last_90_days(batch_start_date):
    return batch_start_date <datetime.timedelta(days = 90)

def main():
    process = True
    process_count = 0
    while process:
        bot_log_id, batch_start_epoch, batch_end_epoch = get_missing_batch()
        if not batch_start_epoch and datetime.today()-batch_start_epoch >timedelta(days = 90):
            process = False
            logger.info('no missing batch to process and processed for last 90 days')
            break

        relation_df, p_selected_node_df = get_previous_statehash(bot_log_id)
        p_map = get_relation_list(relation_df)
        existing_state_df = get_state_hash_df(connection)
        existing_nodes = get_existing_nodes(connection)
        create_empty_folders()
        logger.info(
            "processing missing batch script start at {0}  end at {1}".format(batch_start_epoch, batch_end_epoch))
        logger.info('running for batch: {0} - {1}'.format(batch_start_epoch, batch_end_epoch))
        script_offset = os.path.commonprefix([str(batch_start_epoch.strftime("%Y-%m-%dT%H:%M:%SZ")),
                                              str(batch_end_epoch.strftime("%Y-%m-%dT%H:%M:%SZ"))])
        # get the batch data
        master_df = download_uptime_files(script_offset, batch_start_epoch, batch_end_epoch)
        all_file_count = master_df.shape[0]
        if all_file_count > 0:
            count = download_dat_files(list(master_df.block_hash))
            if count <= 0:
                logger.info("No dat files in BLOCKS directory")
                break

            start = time()
            state_hash_df, threads_used = processing_batch_files(list(master_df['file_name']),
                                                                 BaseConfig.MAX_VERIFIER_INSTANCES)

            end = time()
            logger.info('Time to validate {0} files: {1} seconds'.format(all_file_count, end - start))
            if not state_hash_df.empty:
                master_df['state_hash'] = state_hash_df['state_hash']
                master_df['blockchain_height'] = state_hash_df['height']
                master_df['slot'] = pd.to_numeric(state_hash_df['slot'])
                master_df['parent_state_hash'] = state_hash_df['parent']

                state_hash = pd.unique(master_df[['state_hash', 'parent_state_hash']].values.ravel('k'))
                state_hash_to_insert = find_new_values_to_insert(existing_state_df,
                                                                 pd.DataFrame(state_hash, columns=['statehash']))

                # comment- insert unique statehash into statehash table
                if not state_hash_to_insert.empty:
                    create_statehash(connection, state_hash_to_insert)

                nodes_in_cur_batch = pd.DataFrame(master_df['submitter'].unique(), columns=['block_producer_key'])
                node_to_insert = find_new_values_to_insert(existing_nodes, nodes_in_cur_batch)
                # comment- insert unique block_producer_key into nodes table
                if not node_to_insert.empty:
                    node_to_insert['updated_at'] = datetime.now(timezone.utc)
                    create_node_record(connection, node_to_insert, 100)

                # comment - insert batch data into uptime_file_history table
                create_uptime_file_history(connection, master_df)

                if 'snark_work' in master_df.columns:
                    master_df.drop('snark_work', axis=1, inplace=True)

                columns_to_drop = ['remote_addr', 'file_created', 'file_generation', 'file_owner', 'file_crc32c',
                                   'file_md5_hash']

                master_df.drop(columns=columns_to_drop, axis=1, inplace=True, errors='ignore')
                master_df = master_df.rename(
                    columns={'file_updated': 'file_timestamps', 'submitter': 'block_producer_key'})

                c_selected_node = filter_state_hash_percentage(master_df)
                batch_graph = create_graph(master_df, p_selected_node_df, c_selected_node, p_map)
                weighted_graph, g_pos = apply_weights(batch_graph=batch_graph, c_selected_node=c_selected_node,
                                                      p_selected_node=p_selected_node_df)
                queue_list = list(p_selected_node_df['state_hash'].values) + c_selected_node
                batch_state_hash = list(master_df['state_hash'].unique())

                shortlisted_state_hash_df = bfs(graph=weighted_graph, queue_list=queue_list, node=queue_list[0],
                                                batch_statehash=batch_state_hash, g_pos=g_pos)
                g_pos = None

                point_record_df = master_df[
                    master_df['state_hash'].isin(shortlisted_state_hash_df['state_hash'].values)]

                for index, row in shortlisted_state_hash_df.iterrows():
                    if not row['state_hash'] in batch_state_hash:
                        shortlisted_state_hash_df.drop(index, inplace=True, axis=0)

                # comment - get the parent_state_hash of shortlisted list
                parent_hash = []
                for s in shortlisted_state_hash_df['state_hash'].values:
                    p_hash = master_df[master_df['state_hash'] == s]['parent_state_hash'].values[0]
                    parent_hash.append(p_hash)
                shortlisted_state_hash_df['parent_state_hash'] = parent_hash

                try:
                    if not point_record_df.empty:
                        file_timestamp = master_df.iloc[-1]['file_timestamps']
                    else:
                        file_timestamp = batch_end_epoch
                        logger.info('empty point record for start epoch {0} end epoch {1} '.format(
                            batch_start_epoch.timestamp(), batch_end_epoch.timestamp()))
                    values = all_file_count, file_timestamp, batch_start_epoch.timestamp(), batch_end_epoch.timestamp(), end - start, threads_used
                    bot_log_id = create_bot_log(connection, values)

                    shortlisted_state_hash_df['bot_log_id'] = bot_log_id
                    insert_state_hash_results(shortlisted_state_hash_df)

                    if not point_record_df.empty:
                        point_record_df['amount'] = 1
                        point_record_df['created_at'] = datetime.now(timezone.utc)
                        point_record_df['bot_log_id'] = bot_log_id
                        point_record_df = point_record_df[
                            ['file_name', 'file_timestamps', 'blockchain_epoch', 'block_producer_key',
                             'blockchain_height', 'amount', 'created_at', 'bot_log_id',
                             'state_hash']]

                        create_point_record(connection, point_record_df)
                except Exception as error:
                    connection.rollback()
                    logger.error(ERROR.format(error))

                finally:
                    connection.commit()

                process_count += 1
                logger.info('Processed it loop count : {0}'.format(process_count))
            else:
                logger.info('Finished processing data from table.')


if __name__ == '__main__':
    main()
