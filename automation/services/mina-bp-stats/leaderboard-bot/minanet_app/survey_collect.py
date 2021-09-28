import os
from datetime import datetime, timedelta, timezone
from time import time
import json
import numpy as np
from logger_util import logger
from config import BaseConfig
from google.cloud import storage
from download_batch_files import download_batch_into_memory
import requests
import io
import psycopg2
import psycopg2.extras as extras
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

connection = psycopg2.connect(
    host=BaseConfig.POSTGRES_HOST,
    port=BaseConfig.POSTGRES_PORT,
    database=BaseConfig.POSTGRES_DB,
    user=BaseConfig.POSTGRES_USER,
    password=BaseConfig.POSTGRES_PASSWORD
)

start_time = time()
NODE_DATA_BLOCK_HEIGHT = 'nodeData.blockHeight'
NODE_DATA_BLOCK_STATE_HASH = 'nodeData.block.stateHash'
ERROR = 'Error: {0}'

def download_files(start_offset, script_start_time, ten_min_add):
    storage_client = storage.Client.from_service_account_json(BaseConfig.CREDENTIAL_PATH)
    bucket = storage_client.get_bucket(BaseConfig.GCS_BUCKET_NAME)
    blobs = storage_client.list_blobs(bucket, start_offset=start_offset)
    file_name_list_for_memory = list()
    file_json_content_list = list()
    file_names = list()
    file_created = list()
    file_updated = list()
    file_generation = list()
    file_owner = list()
    file_crc32c = list()
    file_md5_hash = list()

    for blob in blobs:
        if (blob.updated < ten_min_add) and (blob.updated > script_start_time):
            file_name_list_for_memory.append(blob.name)
            file_names.append(blob.name)
            file_updated.append(blob.updated)
            file_created.append(blob.time_created)
            file_generation.append(blob.generation)
            file_owner.append(blob.owner)
            file_crc32c.append(blob.crc32c)
            file_md5_hash.append(blob.md5_hash)
        elif blob.updated > ten_min_add:
            break
    file_count = len(file_name_list_for_memory)
    logger.info('file count for process : {0}'.format(file_count))

    if len(file_name_list_for_memory) > 0:
        start = time()
        file_contents = download_batch_into_memory(file_name_list_for_memory, bucket)
        end = time()
        logger.info('Time to downaload files: {0}'.format(end - start))
        for k, v in file_contents.items():
            file_json_content_list.append(json.loads(v))

        df = pd.json_normalize(file_json_content_list)
        #df.drop(columns_to_drop, axis=1, inplace=True)
        df.insert(0, 'file_name', file_names)
        df['file_created'] = file_created
        df['file_updated'] = file_updated
        df['file_generation'] = file_generation
        df['file_owner'] = file_owner
        df['file_crc32c'] = file_crc32c
        df['file_md5_hash'] = file_md5_hash
        df=df[['file_name', 'receivedAt', 'receivedFrom', 'blockProducerKey',
       'nodeData.version', 'nodeData.daemonStatus.blockchainLength',
       'nodeData.daemonStatus.syncStatus', 'nodeData.daemonStatus.chainId',
       'nodeData.daemonStatus.commitId',
       'nodeData.daemonStatus.highestBlockLengthReceived',
       'nodeData.daemonStatus.highestUnvalidatedBlockLengthReceived',
       'nodeData.daemonStatus.stateHash',
       'nodeData.daemonStatus.blockProductionKeys',
       'nodeData.daemonStatus.uptimeSecs', 'nodeData.block.stateHash',
       'nodeData.retrievedAt', 'nodeData.blockHeight', 'file_created',
       'file_updated', 'file_generation', 'file_owner', 'file_crc32c',
       'file_md5_hash']]
        
    else:
        df = pd.DataFrame()
    return df

def insert_uptime_file_history_batch(conn, df, page_size=100):
    tuples = [tuple(x) for x in df.to_numpy()]
    query = """INSERT INTO uptime_file_history(file_name, receivedAt, receivedFrom, blockProducerKey, 
        nodeData_version, nodeData_daemonStatus_blockchainLength, nodeData_daemonStatus_syncStatus, 
        nodeData_daemonStatus_chainId, nodeData_daemonStatus_commitId, nodeData_daemonStatus_highestBlockLengthReceived, 
        nodeData_daemonStatus_highestUnvalidatedBlockLengthReceived, nodeData_daemonStatus_stateHash, 
        nodeData_daemonStatus_blockProductionKeys, nodeData_daemonStatus_uptimeSecs, nodeData_block_stateHash, 
        nodeData_retrievedAt, nodeData_blockHeight, file_created_at, file_modified_at, file_generation, file_owner, file_crc32c, file_md5_hash) 
    VALUES(%s ,%s ,%s ,%s ,%s ,%s ,%s , %s ,%s ,%s ,%s ,%s , %s ,%s ,%s , %s , %s ,%s, %s, %s , %s ,%s, %s ) """
    
    try:
        cursor = conn.cursor()
        extras.execute_batch(cursor, query, tuples, page_size)
        
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return 1
    finally:
        cursor.close()
        return 0

def execute_node_record_batch(conn, df, page_size=100):
    tuples = [tuple(x) for x in df.to_numpy()]
    query = """INSERT INTO nodes ( block_producer_key,updated_at) 
            VALUES ( %s,  %s ) ON CONFLICT (block_producer_key) DO NOTHING """
    cursor = conn.cursor()
    try:
        extras.execute_batch(cursor, query, tuples, page_size)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return 1
    finally:
        cursor.close()
    return 0


def execute_point_record_batch(conn, df, page_size=100):
    tuples = [tuple(x) for x in df.to_numpy()]
    query = """INSERT INTO points ( file_name,file_timestamps,blockchain_epoch, node_id, blockchain_height,
                amount,created_at,bot_log_id) 
            VALUES ( %s, %s,  %s, (SELECT id FROM nodes WHERE block_producer_key= %s), %s, %s, %s,  %s )"""
    try:
        cursor = conn.cursor()
        extras.execute_batch(cursor, query, tuples, page_size)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return 1
    finally:
        cursor.close()
    return 0


def create_bot_log(conn, values):
    # files_processed file_timestamps state_hash batch_start_epoch batch_end_epoch

    query = """INSERT INTO bot_logs(files_processed,file_timestamps, state_hash,
    batch_start_epoch,batch_end_epoch) values ( %s, %s, %s, %s, %s) RETURNING id """
    try:
        cursor = conn.cursor()
        cursor.execute(query, values)
        result = cursor.fetchone()
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return result[0]


def connect_to_spreadsheet():
    os.environ["PYTHONIOENCODING"] = "utf-8"
    creds = ServiceAccountCredentials.from_json_keyfile_name(BaseConfig.SPREADSHEET_JSON, BaseConfig.SPREADSHEET_SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open(BaseConfig.SPREADSHEET_NAME)
    sheet_instance = sheet.get_worksheet(0)
    records_data = sheet_instance.get_all_records()
    table_data = pd.DataFrame(records_data)
    return table_data


def update_email_discord_status(conn, page_size=100):
    # 4 - block_producer_key,  3 - block_producer_email , # 2 - discord_id
    spread_df = connect_to_spreadsheet()
    spread_df = spread_df.iloc[:, [2, 3, 4]]
    tuples = [tuple(x) for x in spread_df.to_numpy()]

    try:
        
        sql = """update nodes set application_status = true, discord_id =%s, block_producer_email =%s
             where block_producer_key= %s """
        cursor = conn.cursor()
        extras.execute_batch(cursor, sql, tuples, page_size)
        sql = "select block_producer_key from nodes"
        bot_cursor = conn.cursor()
        bot_cursor.execute("select block_producer_key from nodes")
        result = bot_cursor.fetchall()
        nodes = pd.DataFrame(result, columns=['block_producer_key'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return nodes


def get_provider_accounts():
    # read csv
    mina_foundation_df = pd.read_csv(BaseConfig.PROVIDER_ACCOUNT_PUB_KEYS_FILE, header=None)
    mina_foundation_df.columns = ['block_producer_key']
    return mina_foundation_df


def update_scoreboard(conn, score_till_time):
    sql = """with vars  (snapshot_date, start_date) as( values (%s AT TIME ZONE 'UTC', 
			(%s - interval '%s' day) AT TIME ZONE 'UTC')
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
         where file_timestamps between start_date and snapshot_date
         group by node_id
     )
     , scores as (
         select node_id, total_points, surveys,  round( ((total_points::decimal*100) / surveys),2) as score_perc
         from lastboard l , b_logs t
     )
    update nodes nrt set score = s.total_points, score_percent=s.score_perc  from scores s where nrt.id=s.node_id"""
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (score_till_time, score_till_time, BaseConfig.UPTIME_DAYS_FOR_SCORE,))
    
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return 0


def gcs_main(read_file_interval):
    existing_nodes = update_email_discord_status(connection)
    process_loop_count = 0
    bot_cursor = connection.cursor()
    bot_cursor.execute("SELECT batch_end_epoch FROM bot_logs ORDER BY batch_end_epoch DESC limit 1")
    result = bot_cursor.fetchone()
    batch_end_epoch = result[0]
    script_start_time = datetime.fromtimestamp(batch_end_epoch, timezone.utc)
    script_end_time = datetime.now(timezone.utc)
    # read the mina foundation accounts
    foundation_df = get_provider_accounts()
    do_process = True
    while do_process :
        # get 10 min time for fetching the files
        script_start_epoch = str(script_start_time.timestamp())

        ten_min_add = script_start_time + timedelta(minutes=read_file_interval)
        next_interval_epoch = str(ten_min_add.timestamp())

        # common str for offset
        script_start_time_final = str(script_start_time.date()) + '.' + str(script_start_time.timestamp())
        ten_min_add_final = str(ten_min_add.date()) + '.' + str(ten_min_add.timestamp())
        logger.info('runing for batch: {0} - {1}'.format(script_start_time_final,ten_min_add_final))

        # change format for comparison
        script_end_time_var = datetime.strftime(script_end_time, '%Y-%m-%d %H:%M:%S')
        ten_min_add_time_var = datetime.strftime(ten_min_add, '%Y-%m-%d %H:%M:%S')
        if ten_min_add_time_var > script_end_time_var:
            logger.info('all files are processed till date')
            break
        else:
            common_str = os.path.commonprefix([script_start_epoch, next_interval_epoch])
            script_offset = str(script_start_time.date()) + '.' + common_str

            # processing code logic
            master_df = download_files(script_offset, script_start_time, ten_min_add)
            #insert_uptime_file_history_batch(connection, master_df)
            columns_to_drop = ['receivedFrom', 'nodeData.version', 'nodeData.daemonStatus.blockchainLength',
                           'nodeData.daemonStatus.syncStatus', 'nodeData.daemonStatus.chainId', 
                           'nodeData.daemonStatus.commitId', 'nodeData.daemonStatus.highestBlockLengthReceived',
                           'nodeData.daemonStatus.highestUnvalidatedBlockLengthReceived',
                           'nodeData.daemonStatus.stateHash', 'nodeData.daemonStatus.blockProductionKeys', 
                           'nodeData.daemonStatus.uptimeSecs', 'nodeData.retrievedAt','file_created', 
                           'file_generation', 'file_owner', 'file_crc32c', 'file_md5_hash']
            master_df.drop(columns_to_drop, axis=1, inplace=True)
            if master_df.columns.values.tolist()[-1] != NODE_DATA_BLOCK_HEIGHT:
                master_df = master_df[['file_name', 'file_updated', 'receivedAt', 'blockProducerKey', 'nodeData.block.stateHash',
                        'nodeData.blockHeight']]
            
            master_df = master_df.rename(columns={'file_updated': 'file_timestamps','blockProducerKey':'blockproducerkey',
                        'nodeData.block.stateHash':'nodedata_block_statehash', 'nodeData.blockHeight':'blockchain_height'})
            
            all_file_count = master_df.shape[0]

            if all_file_count>0:
                # remove the Mina foundation account from the master_df
                master_df = master_df[~master_df['blockproducerkey'].isin(foundation_df['block_producer_key'])]

                # Filter duplicate entries keyed on (block-producer-pubkey+state_hash)
                unique_statehash_df = master_df.drop_duplicates(['blockproducerkey', 'nodedata_block_statehash'])

                # Find the most common state hash in unique_statehash
                most_common_statehash = unique_statehash_df['nodedata_block_statehash'].value_counts().idxmax()

                point_record_df = master_df.loc[master_df['nodedata_block_statehash'] == most_common_statehash] 
                try:
                    # get the id of bot_log to insert in Point_record
                    # last Epoch time & last filename
                    if not point_record_df.empty:
                        file_timestamp = master_df.iloc[-1]['file_timestamps']
                    else:
                        file_timestamp = 0
                    values =  all_file_count, file_timestamp, most_common_statehash, script_start_time.timestamp(), ten_min_add.timestamp()
                    #always add bot_log, even if no data for 10min window
                    bot_log_id = create_bot_log(connection, values)
                    if not point_record_df.empty:
                        # data insertion to nodes
                        node_to_insert = point_record_df[['blockproducerkey']]
                        node_to_insert = node_to_insert.rename(columns={'blockproducerkey': 'block_producer_key'})
                        # remove existing nodes from df
                        node_to_insert = (node_to_insert.merge(existing_nodes, on='block_producer_key', how='left', indicator=True)
                            .query('_merge == "left_only"')
                            .drop('_merge', 1))
                        
                        node_to_insert['updated_at'] = datetime.now(timezone.utc)
                        if node_to_insert.shpae[0]>0:
                            execute_node_record_batch(connection, node_to_insert, 100)
                        
                        #file_name,file_timestamps,blockchain_epoch, node_id, blockchain_height, amount,created_at,bot_log_id
                        point_record_df = point_record_df.drop('nodedata_block_statehash', axis=1)
                        point_record_df['amount'] = 1
                        point_record_df['created_at'] = datetime.now(timezone.utc)
                        point_record_df['bot_log_id'] = bot_log_id

                        execute_point_record_batch(connection, point_record_df)
                except Exception as error:
                    connection.rollback()
                    logger.error(ERROR.format(error))
                finally:
                    connection.commit()
                process_loop_count += 1
                logger.info('Processed it loop count : {0}'.format(process_loop_count))
            else:
                logger.info('Finished processing data from table.')
                do_process = False
            script_start_time = ten_min_add
            
            if script_start_time >= script_end_time:
                do_process = False
    try:
        update_scoreboard(connection, script_start_time)
    except Exception as error:
        connection.rollback()
        logger.error(ERROR.format(error))
    finally:
        connection.commit()
            


if __name__ == '__main__':
    time_interval = BaseConfig.SURVEY_INTERVAL_MINUTES
    try:
        gcs_main(time_interval)
    except Exception as err:
        logger.error(ERROR.format(err))