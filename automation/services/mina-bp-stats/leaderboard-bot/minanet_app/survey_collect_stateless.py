import os
from datetime import datetime, timedelta, timezone
from time import time
import time as tm
import json
import numpy as np
from config import BaseConfig
from google.cloud import storage
from download_batch_files import download_batch_into_memory
import psycopg2
import psycopg2.extras as extras
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from logger_util import logger
import subprocess
import shutil

connection = psycopg2.connect(
    host=BaseConfig.POSTGRES_HOST,
    port=BaseConfig.POSTGRES_PORT,
    database=BaseConfig.POSTGRES_DB,
    user=BaseConfig.POSTGRES_USER,
    password=BaseConfig.POSTGRES_PASSWORD
)

ERROR = 'Error: {0}'


def connect_to_spreadsheet():
    os.environ["PYTHONIOENCODING"] = "utf-8"
    creds = ServiceAccountCredentials.from_json_keyfile_name(BaseConfig.SPREADSHEET_JSON, BaseConfig.SPREADSHEET_SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open(BaseConfig.SPREADSHEET_NAME)
    sheet_instance = sheet.get_worksheet(0)
    records_data = sheet_instance.get_all_records()
    table_data = pd.DataFrame(records_data)
    logger.info("connected to applications excel")
    return table_data


def update_email_discord_status(conn, page_size=100):
    # 4 - block_producer_key,  3 - block_producer_email , # 2 - discord_id
    spread_df = connect_to_spreadsheet()
    spread_df = spread_df.iloc[:, [2, 3, 4]]
    tuples = [tuple(x) for x in spread_df.to_numpy()]
    bot_cursor = conn.cursor()
    cursor = conn.cursor()
    try:

        sql = """update nodes set application_status = true, discord_id =%s, block_producer_email =%s
             where block_producer_key= %s """

        extras.execute_batch(cursor, sql, tuples, page_size)

        bot_cursor.execute("select block_producer_key from nodes")
        result = bot_cursor.fetchall()
        nodes = pd.DataFrame(result, columns=['block_producer_key'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        bot_cursor.close()
        return -1
    finally:
        bot_cursor.close()
        cursor.close()
        conn.commit()
    return nodes


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


def get_gcs_bucket():
    storage_client = storage.Client.from_service_account_json(BaseConfig.CREDENTIAL_PATH)
    bucket = storage_client.get_bucket(BaseConfig.GCS_BUCKET_NAME)
    return bucket

def download_uptime_files(start_offset, script_start_time, twenty_min_add, delimiter=None):
    file_name_list_for_memory = list()
    file_json_content_list = list()
    file_names = list()
    file_created = list()
    file_updated = list()
    file_generation = list()
    file_owner = list()
    file_crc32c = list()
    file_md5_hash = list()

    bucket = get_gcs_bucket()
    prefix_date = script_start_time.strftime("%Y-%m-%d")
    prefix = 'submissions/'+prefix_date
    blobs = bucket.list_blobs( prefix=prefix,delimiter=delimiter)
    
    for blob in blobs:
        file_timestamp = blob.name.split('/')[2].rsplit('-', 1)[0]
        file_epoch = tm.mktime(datetime.strptime(file_timestamp, "%Y-%m-%dT%H:%M:%SZ").timetuple())
       
        if file_epoch < twenty_min_add.timestamp() and (file_epoch > script_start_time.timestamp()):
            
            json_file_name = blob.name.split('/')[2]
            file_name_list_for_memory.append(blob.name)
            file_names.append(json_file_name)
            file_updated.append(file_timestamp)
            file_created.append(file_timestamp)
            file_generation.append(blob.generation)
            file_owner.append(blob.owner)
            file_crc32c.append(blob.crc32c)
            file_md5_hash.append(blob.md5_hash)
        elif file_epoch > twenty_min_add.timestamp():
            break
    file_count = len(file_name_list_for_memory)
    logger.info('file count for process : {0}'.format(file_count))

    if len(file_name_list_for_memory) > 0:
        start = time()
        file_contents = download_batch_into_memory(file_name_list_for_memory, bucket)
        end = time()
        logger.info('Time to download files: {0}'.format(end - start))
        for k, v in file_contents.items():
            file = k.split('/')[2]
            file_json_content_list.append(json.loads(v))
            # comment- saving the json files to local directory
            with open(os.path.join(BaseConfig.SUBMISSION_DIR, file), 'w') as fw:
                json.dump(json.loads(v), fw)

        df = pd.json_normalize(file_json_content_list)
        df.insert(0, 'file_name', file_names)
        df['file_created'] = file_created
        df['file_updated'] = file_updated
        df['file_generation'] = file_generation
        df['file_owner'] = file_owner
        df['file_crc32c'] = file_crc32c
        df['file_md5_hash'] = file_md5_hash
        df['blockchain_height'] = 0
        df['blockchain_epoch'] = df['created_at'].apply(
            lambda row: int(tm.mktime(datetime.strptime(row, "%Y-%m-%dT%H:%M:%SZ").timetuple()) * 1000))
        df = df[['file_name', 'blockchain_epoch', 'created_at', 'peer_id', 'snark_work', 'remote_addr',
                 'submitter', 'block_hash', 'blockchain_height', 'file_created', 'file_updated',
                 'file_generation', 'file_owner', 'file_crc32c', 'file_md5_hash']]

    else:
        df = pd.DataFrame()

    return df


def download_dat_files(state_hashes):
    bucket = get_gcs_bucket()
    for state in state_hashes:
        blob=bucket.get_blob('blocks/'+state+'.dat')
        destination_uri = '{}/{}'.format(BaseConfig.BLOCK_DIR, blob.name.split('/')[1])
        blob.download_to_filename(destination_uri)


def insert_uptime_file_history_batch(conn, df, page_size=100):
    tuples = [tuple(x) for x in df.to_numpy()]
    query = """INSERT INTO uptime_file_history(file_name, blockchain_epoch, created_at, peer_id, 
        remote_addr, submitter, block_hash, 
        blockchain_height, file_created_at ,file_modified_at, 
        file_generation, file_owner, 
        file_crc32c, file_md5_hash, state_hash, slot) 
    VALUES(%s ,%s ,%s ,%s ,%s ,%s ,%s , %s ,%s ,%s ,%s ,%s , %s, %s, %s, %s) """

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


def get_validate_state_hash(batch_file_list):
    file_list = []
    for file in batch_file_list:
        file_name = os.path.join(f'{BaseConfig.SUBMISSION_DIR}', file)
        file_list.append(file_name)
    file_names = ' '.join(file_list)

    cmd_string1 = f'docker run -v {BaseConfig.ROOT_DIR}:{BaseConfig.ROOT_DIR} ' \
                  f'gcr.io/o1labs-192920/delegation-verify:1.2.0-mainnet --block-dir {BaseConfig.BLOCK_DIR} '

    command = cmd_string1 + ' ' + file_names
    logger.info('Executing command: \n {0}'.format(command))
    ps = subprocess.Popen([command], stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True)
    output = ps.communicate()[0]
    logger.info('Command Output: \n {0}'.format(output))
    output_list = list()
    default_json_data = {'state_hash': '', 'height': 0, 'slot': 0}
    # read the result from the shell
    for line in output.splitlines():
        try:
            json_output = json.loads(line.decode("utf-8"))
            if "state_hash" in json_output:
                output_list.append(json_output)
            else:
                logger.info(json_output)
                output_list.append(default_json_data)
        except ValueError as error:
            logger.error(ERROR.format(error))
    df = pd.DataFrame(output_list)
    
    return df

def create_empty_folders():
    # comment- remove Blocks and Submissions directories
    shutil.rmtree(BaseConfig.BLOCK_DIR, ignore_errors=True)
    shutil.rmtree(BaseConfig.SUBMISSION_DIR, ignore_errors=True)
    # comment - create blocks and submissions directory
    os.makedirs(BaseConfig.BLOCK_DIR, exist_ok=True)
    os.makedirs(BaseConfig.SUBMISSION_DIR, exist_ok=True)

def main():
    existing_nodes = update_email_discord_status(connection)
    process_loop_count = 0
    bot_cursor = connection.cursor()
    bot_cursor.execute("SELECT batch_end_epoch FROM bot_logs ORDER BY batch_end_epoch DESC limit 1")
    result = bot_cursor.fetchone()
    batch_end_epoch = result[0]
    script_start_time = datetime.fromtimestamp(batch_end_epoch, timezone.utc)
    #script_start_time = datetime.fromtimestamp(1633766137, timezone.utc)
    script_end_time = datetime.now(timezone.utc)
    
    do_process = True
    while do_process:
        create_empty_folders()
        # comment - get 20 min time for fetching the files
        script_start_epoch = str(script_start_time.timestamp())

        twenty_min_add = script_start_time + timedelta(minutes=BaseConfig.SURVEY_INTERVAL_MINUTES)
        next_interval_epoch = str(twenty_min_add.timestamp())

        # comment - common str for offset
        script_start_time_final = str(script_start_time.date()) + '.' + str(script_start_time.timestamp())
        twenty_min_add_final = str(twenty_min_add.date()) + '.' + str(twenty_min_add.timestamp())
        logger.info('running for batch: {0} - {1}'.format(script_start_time_final, twenty_min_add_final))
        print('start',script_start_time)
        print('twenty min',twenty_min_add)
        # comment - change format for comparison
        script_end_time_var = datetime.strftime(script_end_time, '%Y-%m-%d %H:%M:%S')
        twenty_min_add_time_var = datetime.strftime(twenty_min_add, '%Y-%m-%d %H:%M:%S')
        if twenty_min_add_time_var > script_end_time_var:
            logger.info('all files are processed till date')
            break
        else:
            common_str = os.path.commonprefix([script_start_epoch, next_interval_epoch])
            script_offset = str(script_start_time.date()) + '.' + common_str
            master_df = download_uptime_files(script_offset, script_start_time, twenty_min_add)
            
            all_file_count = master_df.shape[0]
            if all_file_count > 0:
                 # download block dat files using "state_hash" column of df
                download_dat_files(list (master_df.block_hash))
                # comment- validate json files and get state_hash
                state_hash_df = get_validate_state_hash(list(master_df['file_name']))
                if not state_hash_df.empty:
                    print(state_hash_df)
                    master_df['state_hash'] = state_hash_df['state_hash']
                    master_df['blockchain_height'] = state_hash_df['height']
                    master_df['slot'] = pd.to_numeric(state_hash_df['slot'])

                    master_df.drop('snark_work', axis=1, inplace=True)
                    #insert_uptime_file_history_batch(connection, master_df)

                    columns_to_drop = ['created_at', 'peer_id', 'remote_addr', 'file_created',
                                    'file_generation', 'file_owner', 'file_crc32c', 'file_md5_hash']
                    master_df.drop(columns=columns_to_drop, axis=1, inplace=True)
                    master_df = master_df.rename(
                        columns={'file_updated': 'file_timestamps', 'submitter': 'block_producer_key'})

                    unique_statehash_df = master_df.drop_duplicates(['block_producer_key', 'state_hash'])
                    most_common_statehash = unique_statehash_df['state_hash'].value_counts().idxmax()
                    point_record_df = master_df.loc[master_df['state_hash'] == most_common_statehash]
                    try:
                        # comment - get the id of bot_log to insert in Point_record
                        # comment - last Epoch time & last filename
                        if not point_record_df.empty:
                            file_timestamp = master_df.iloc[-1]['file_timestamps']
                        else:
                            file_timestamp = 0
                        values = all_file_count, file_timestamp, most_common_statehash, script_start_time.timestamp(), twenty_min_add.timestamp()
                        # comment - always add bot_log, even if no data for 20min window
                        bot_log_id = create_bot_log(connection, values)

                        if not point_record_df.empty:
                            node_to_insert = point_record_df[['block_producer_key']]
                            node_to_insert = (
                                node_to_insert.merge(existing_nodes, on='block_producer_key', how='left', indicator=True)
                                    .query('_merge == "left_only"')
                                    .drop('_merge', 1))

                            node_to_insert['updated_at'] = datetime.now(timezone.utc)
                            execute_node_record_batch(connection, node_to_insert, 100)
                            point_record_df = point_record_df.drop('state_hash', axis=1)
                            point_record_df['amount'] = 1
                            point_record_df['created_at'] = datetime.now(timezone.utc)
                            point_record_df['bot_log_id'] = bot_log_id
                            point_record_df = point_record_df[
                                ['file_name', 'file_timestamps', 'blockchain_epoch', 'block_producer_key',
                                'blockchain_height', 'amount', 'created_at', 'bot_log_id']]

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
                # do_process = False

            script_start_time = twenty_min_add


            if script_start_time >= script_end_time:
                do_process = False


if __name__ == '__main__':
    main()
