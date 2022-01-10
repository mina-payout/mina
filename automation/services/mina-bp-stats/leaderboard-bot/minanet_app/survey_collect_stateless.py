import os
from datetime import datetime, timedelta, timezone
from time import time
import time as tm
import json
import numpy as np
from config import BaseConfig
from google.cloud import storage
from google.cloud.storage import Client as GSClient, Blob
from download_batch_files import download_batch_into_memory, download_batch_into_files
import psycopg2
import psycopg2.extras as extras
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from logger_util import logger
import subprocess
import shutil
from multiprocessing import processing_batch_files

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

def get_existing_nodes(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("select block_producer_key from nodes")
        result = cursor.fetchall()
        nodes = pd.DataFrame(result, columns=['block_producer_key'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return nodes

def update_email_discord_status(conn, page_size=100):
    # 4 - block_producer_key,  3 - block_producer_email , # 2 - discord_id
    spread_df = connect_to_spreadsheet()
    spread_df = spread_df.iloc[:, [2, 3, 4]]
    tuples = [tuple(x) for x in spread_df.to_numpy()]
    cursor = conn.cursor()
    try:
        sql = """update nodes set application_status = true, discord_id =%s, block_producer_email =%s
             where block_producer_key= %s """
        extras.execute_batch(cursor, sql, tuples, page_size)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.commit()
    return 0

def get_state_hash_df(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("select value from state_hash")
        result = cursor.fetchall()
        state_hash = pd.DataFrame(result, columns=['state_hash'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        return -1
    finally:
        cursor.close()
    return state_hash

def create_node_record(conn, df, page_size=100):
    tuples = [tuple(x) for x in df.to_numpy()]
    query = """INSERT INTO nodes ( block_producer_key, updated_at) 
            VALUES ( %s,  %s )  """
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

def create_statehash(conn, statehash_df, page_size=100):
    tuples = [tuple(x) for x in statehash_df.to_numpy()]
    logger.info('create_statehash: {0}'.format(tuples))
    query = """INSERT INTO state_hash ( value) 
            VALUES ( %s)  """
    cursor = conn.cursor()
    try:
        cursor = conn.cursor()
        extras.execute_batch(cursor, query, tuples, page_size)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return 0

def create_point_record(conn, df, page_size=100):
    tuples = [tuple(x) for x in df.to_numpy()]
    query = """INSERT INTO points ( file_name, file_timestamps, blockchain_epoch, node_id, blockchain_height,
                amount, created_at, bot_log_id, state_hash_id) 
            VALUES ( %s, %s,  %s, (SELECT id FROM nodes WHERE block_producer_key= %s), %s, %s, 
                    %s, %s, (SELECT id FROM state_hash WHERE value= %s) )"""
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
    prefix = 'submissions/'+prefix_date+'/'+start_offset
    blobs = bucket.list_blobs( prefix=prefix,delimiter=delimiter)
    cnt =1
    for blob in blobs:
        file_timestamp = blob.name.split('/')[2].rsplit('-', 1)[0]
        file_epoch = tm.mktime(datetime.strptime(file_timestamp, "%Y-%m-%dT%H:%M:%SZ").timetuple())
        cnt=cnt+1
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
        elif file_epoch > twenty_min_add.timestamp() :
            break
    file_count = len(file_name_list_for_memory)
    if len(file_name_list_for_memory) > 0:
        start = time()
        file_contents = download_batch_into_memory(file_name_list_for_memory, bucket)
        end = time()
        logger.info('Time to download {0} submission files: {1}'.format(file_count, end - start))
        for k, v in file_contents.items():
            file = k.split('/')[2]
            file_json_content_list.append(json.loads(v))
            # comment- saving the json files to local directory
            #with open(os.path.join(BaseConfig.SUBMISSION_DIR, file), 'w') as fw:
            #    json.dump(json.loads(v), fw)
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
    count=0
    file_names = list()
    for sh in state_hashes:
        file_names.append('blocks/'+sh+'.dat')
        
    start = time()
    tmp = download_batch_into_files(file_names, bucket)
    end = time()
    count = len(tmp)
    logger.info('Time to download {0} block files: {1}'.format(count, end - start))
    return count

def create_uptime_file_history(conn, df, page_size=100):
    temp_df = df.copy(deep=True)
    temp_df.drop('snark_work', axis=1, inplace=True)
    temp_df.drop('peer_id', axis=1, inplace=True)
    temp_df.drop('created_at', axis=1, inplace=True)
    temp_df.drop('block_hash', axis=1, inplace=True)
    temp_df = temp_df[['file_name', 'blockchain_epoch', 'remote_addr',
                'submitter', 'state_hash', 'file_created', 'file_updated',
                'file_generation', 'file_crc32c', 'file_md5_hash']]
    temp_df = temp_df.rename(columns={'blockchain_epoch': 'receivedat', 'submitter':'blockproducerkey','remote_addr':'receivedFrom', 
                    'state_hash':'nodedata_block_statehash'})
    tuples = [tuple(x) for x in temp_df.to_numpy()]
    query = """INSERT INTO uptime_file_history(file_name, receivedAt, receivedFrom, blockproducerKey, 
         nodeData_block_stateHash,  file_created_at, file_modified_at, file_generation, file_crc32c, file_md5_hash) 
    VALUES(%s ,%s ,%s ,%s ,%s, %s ,%s ,%s ,%s ,%s ) """
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
    query = """INSERT INTO bot_logs(files_processed, file_timestamps, batch_start_epoch, batch_end_epoch, processing_time, number_of_threads)
                values ( %s, %s, %s, %s, %s, %s) RETURNING id """
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


def filter_state_hash_percentile(df):
    state_hash_list = list()
    # comment- group the state_hash in dataframe and find there count
    unique_state_hash_count = df['state_hash'].value_counts()
    # comment- find the 90 percentile of all state_hash count
    percentile = round(np.percentile(unique_state_hash_count.values, 90))

    for state_hash, total_count in zip(unique_state_hash_count.index, unique_state_hash_count.values):
        # comment- check percentile equal or above total count
        if total_count >= percentile:
            state_hash_list.append(state_hash)
    # comment- filter df with state_hash_list
    filter_df = df[df['state_hash'].isin(state_hash_list)]

    return filter_df, state_hash_list

def find_new_values_to_insert(existing_values, new_values):
    return existing_values.merge(new_values, how = 'outer' ,indicator=True)\
            .loc[lambda x : x['_merge']=='right_only'].drop('_merge', 1).drop_duplicates()

def get_batch_timings(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT batch_end_epoch FROM bot_logs ORDER BY batch_end_epoch DESC limit 1")
        result = cursor.fetchone()
        prev_epoch = result[0]
        prev_batch_end  = datetime.fromtimestamp(prev_epoch, timezone.utc)
        cur_batch_end = prev_batch_end + timedelta(minutes=BaseConfig.SURVEY_INTERVAL_MINUTES)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        return -1
    finally:
        cursor.close()
    return prev_batch_end, cur_batch_end

def main():
    update_email_discord_status(connection)
    process_loop_count = 0
    prev_batch_end, cur_batch_end = get_batch_timings(connection)
    cur_timestamp = datetime.now(timezone.utc)
    do_process = True
    while do_process:
        existing_state_df = get_state_hash_df(connection)
        existing_nodes = get_existing_nodes(connection)
        create_empty_folders()
        # comment - get 20 min time for fetching the files
        logger.info('runing for batch: {0} - {1}'.format(prev_batch_end, cur_batch_end))
        # comment - common str for offset
        script_offset = os.path.commonprefix([str(prev_batch_end.strftime("%Y-%m-%dT%H:%M:%SZ")), 
                    str(cur_batch_end.strftime("%Y-%m-%dT%H:%M:%SZ"))])
       
        if cur_batch_end > cur_timestamp:
            logger.info('all files are processed till date')
            break
        else:
            master_df = download_uptime_files(script_offset, prev_batch_end, cur_batch_end)
            all_file_count = master_df.shape[0]
            if all_file_count > 0:
                 # download block dat files using "state_hash" column of df
                count = download_dat_files(list (master_df.block_hash))
                if count <= 0:
                    logger.info("No dat files in BLOCKS directory")
                    break
                # comment- validate json files and get state_hash
                #state_hash_df = get_validate_state_hash(list(master_df['file_name']))
                data={"state_hash":"3NLBR3qs9iWBwSn613Rn95h5k7hsYYB7s3crQKun68GBD16qUmfW","height":79353,"slot":114285},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NKQa1FsdHakAKjKBbmDc4AqQGm3J58EJoiCweGEPcrHW2aNX7uF","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NKQa1FsdHakAKjKBbmDc4AqQGm3J58EJoiCweGEPcrHW2aNX7uF","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NKQa1FsdHakAKjKBbmDc4AqQGm3J58EJoiCweGEPcrHW2aNX7uF","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NKQa1FsdHakAKjKBbmDc4AqQGm3J58EJoiCweGEPcrHW2aNX7uF","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NLpfnoyAy3MeF1XXBPyDtJ7KAbo5b9HyRS33YehKxDRXbBCtRzx","height":79351,"slot":114279},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NL1AsDtNrU3vGa11yRN3nX33gcavTNyFDoQUx4QPJK7zZMNRgxz","height":79352,"slot":114281},{"state_hash":"3NLXk8kk6XW6VbmAeWMWEfMTBSYKxABbMfdHVeeKrsHPVoeUSoqz","height":79354,"slot":114286},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKggVvxKeBP4rDjXP8sKdbdiT9s5ZWnHQjXvDKpCudT2UUUs3g7","height":79356,"slot":114290},{"state_hash":"3NKggVvxKeBP4rDjXP8sKdbdiT9s5ZWnHQjXvDKpCudT2UUUs3g7","height":79356,"slot":114290},{"state_hash":"3NKggVvxKeBP4rDjXP8sKdbdiT9s5ZWnHQjXvDKpCudT2UUUs3g7","height":79356,"slot":114290},{"state_hash":"3NKggVvxKeBP4rDjXP8sKdbdiT9s5ZWnHQjXvDKpCudT2UUUs3g7","height":79356,"slot":114290},{"state_hash":"3NKggVvxKeBP4rDjXP8sKdbdiT9s5ZWnHQjXvDKpCudT2UUUs3g7","height":79356,"slot":114290},{"state_hash":"3NKggVvxKeBP4rDjXP8sKdbdiT9s5ZWnHQjXvDKpCudT2UUUs3g7","height":79356,"slot":114290},{"state_hash":"3NKqePYHkY1Rw5mLyiPYo8qjTPQR4uPU3YA7y9VHLom93yNmY6k2","height":79356,"slot":114290},{"state_hash":"3NKGPvk1z1mppD4Lu7kj6sS1JvixFtohZ8wF7EGqXM6R6dzMFMwQ","height":79356,"slot":114290},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NKszAvtC2HBCAeRXJF9dufuGES5T7dtYyjCWyHgKQBrWrPpJnL5","height":79355,"slot":114289},{"state_hash":"3NLQzdzeZyeT1UY15H4A9jSL4V7J3L1sAQPPEzGQYhHu6NxxLUQv","height":79135,"slot":113966},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NKX4DdCwcLvxP9bbMotTEr1PUURHdQYK993wGnYK9kkRqaBmegb","height":79357,"slot":114291},{"state_hash":"3NLvFTAQQk4fKGQ1arJe8sfKmmYM3RDAg559sM5fLkHDeBTSbQFm","height":79018,"slot":113811}
                start = time()
                state_hash_df, threads_used = pd.DataFrame(data) #processing_batch_files(list(master_df['file_name']), BaseConfig.MAX_VERIFIER_INSTANCES)
                end = time()
                logger.info('Time to validate {0} files: {1} seconds'.format(all_file_count, end - start))
                if not state_hash_df.empty:
                    master_df['state_hash'] = state_hash_df['state_hash']
                    master_df['blockchain_height'] = state_hash_df['height']
                    master_df['slot'] = pd.to_numeric(state_hash_df['slot'])
                    create_uptime_file_history(connection, master_df)
                    if 'snark_work' in master_df.columns:
                        master_df.drop('snark_work', axis=1, inplace=True)
                    
                    columns_to_drop = ['remote_addr', 'file_created',
                                    'file_generation', 'file_owner', 'file_crc32c', 'file_md5_hash']
                    master_df.drop(columns=columns_to_drop, axis=1, inplace=True)
                    master_df = master_df.rename(
                        columns={'file_updated': 'file_timestamps', 'submitter': 'block_producer_key'})
                    point_record_df, selected_state_hash = filter_state_hash_percentile(master_df)
                    # comment- comma separated state_hashes
                    state_hash_to_insert = find_new_values_to_insert(existing_state_df, pd.DataFrame(selected_state_hash, columns=['state_hash']))
                    if not state_hash_to_insert.empty:
                        create_statehash(connection, state_hash_to_insert)
                    try:
                        # comment - get the id of bot_log to insert in Point_record
                        # comment - last Epoch time & last filename
                        if not point_record_df.empty:
                            file_timestamp = master_df.iloc[-1]['file_timestamps']
                        else:
                            file_timestamp = 0
                        values = all_file_count, file_timestamp, prev_batch_end.timestamp(), cur_batch_end.timestamp(), end - start, threads_used
                        # comment - always add bot_log, even if no data for 20min window
                        bot_log_id = create_bot_log(connection, values)

                        if not point_record_df.empty:
                            nodes_in_cur_batch = point_record_df[['block_producer_key']]
                            node_to_insert = find_new_values_to_insert(existing_nodes, nodes_in_cur_batch)
                            if not node_to_insert.empty:
                                node_to_insert['updated_at'] = datetime.now(timezone.utc)
                                create_node_record(connection, node_to_insert, 100)
                            #point_record_df = point_record_df.drop('state_hash', axis=1)
                            point_record_df['amount'] = 1
                            point_record_df['created_at'] = datetime.now(timezone.utc)
                            point_record_df['bot_log_id'] = bot_log_id
                            point_record_df = point_record_df[
                                ['file_name', 'file_timestamps', 'blockchain_epoch', 'block_producer_key',
                                'blockchain_height', 'amount', 'created_at', 'bot_log_id', 'state_hash']]

                            create_point_record(connection, point_record_df)
                    except Exception as error:
                        connection.rollback()
                        logger.error(ERROR.format(error))
                    finally:
                        connection.commit()
                    process_loop_count += 1
                    logger.info('Processed it loop count : {0}'.format(process_loop_count))
            else:
                logger.info('Finished processing data from table.')

            prev_batch_end = cur_batch_end
            cur_batch_end = prev_batch_end + timedelta(minutes=BaseConfig.SURVEY_INTERVAL_MINUTES)
            if prev_batch_end >= cur_timestamp:
                do_process = False


if __name__ == '__main__':
    main()
