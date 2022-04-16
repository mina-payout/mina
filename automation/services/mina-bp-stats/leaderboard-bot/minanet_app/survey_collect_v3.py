import os
from datetime import datetime, timedelta, timezone
from time import time
import time as tm
import json
import calendar
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
import networkx as nx
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings('ignore')

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


def get_batch_for_processing(prev_batch_end, cur_batch_end, conn=connection):
    cursor = conn.cursor()
    try:
        sql_select = """
        select file_name,extract('epoch' from file_created_at)*1000,block_producer_key, s1.value block_statehash, 
                    ps.value parent_block_statehash, nodedata_blockheight, nodedata_slot, file_modified_at  
        from uptime_file_history u join statehash s1 ON s1.id = u.block_statehash 
		            join statehash ps on u.parent_block_statehash = ps.id 
                    join nodes n on n.id=u.node_id
        where file_created_at > %s  and file_created_at < %s order by file_created_at
        """

        cursor.execute(sql_select, (prev_batch_end, cur_batch_end))
        result = cursor.fetchall()
        df = pd.DataFrame(result, columns=['file_name', 'blockchain_epoch', 'submitter', 'state_hash',
                                           'parent', 'height', 'slot', 'file_updated'])
        columns_state = ['state_hash', 'height', 'slot', 'parent']

        # comment - get verified statehash df
        statehash_df = df[columns_state]
        df.drop(columns_state, axis=1, inplace=True, errors='ignore')
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return df, statehash_df


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
        sql = """update nodes set application_status = true, discord_id =%s, email_id =%s
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
        cursor.execute("select value from statehash")
        result = cursor.fetchall()
        state_hash = pd.DataFrame(result, columns=['statehash'])
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
    query = """INSERT INTO statehash ( value) 
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
                amount, created_at, bot_log_id, statehash_id) 
            VALUES ( %s, %s,  %s, (SELECT id FROM nodes WHERE block_producer_key= %s), %s, %s, 
                    %s, %s, (SELECT id FROM statehash WHERE value= %s) )"""
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
    prefix = 'submissions/' + prefix_date + '/' + start_offset
    blobs = bucket.list_blobs(prefix=prefix, delimiter=delimiter)

    cnt = 1
    for blob in blobs:
        file_timestamp = blob.name.split('/')[2].rsplit('-', 1)[0]
        file_epoch = tm.mktime(datetime.strptime(file_timestamp, "%Y-%m-%dT%H:%M:%SZ").timetuple())
        cnt = cnt + 1
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
    if len(file_name_list_for_memory) > 0:
        start = time()
        file_contents = download_batch_into_memory(file_name_list_for_memory, bucket)
        end = time()
        logger.info('Time to download {0} submission files: {1}'.format(file_count, end - start))
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
            lambda row: int(calendar.timegm(datetime.strptime(row, "%Y-%m-%dT%H:%M:%SZ").timetuple()) * 1000))
        df = df[['file_name', 'blockchain_epoch', 'created_at', 'peer_id', 'snark_work', 'remote_addr',
                 'submitter', 'block_hash', 'blockchain_height', 'file_created', 'file_updated',
                 'file_generation', 'file_owner', 'file_crc32c', 'file_md5_hash']]
    else:
        df = pd.DataFrame()
    return df


def download_dat_files(state_hashes):
    bucket = get_gcs_bucket()
    count = 0
    file_names = list()
    for sh in state_hashes:
        file_names.append('blocks/' + sh + '.dat')

    start = time()
    tmp = download_batch_into_files(file_names, bucket)
    end = time()
    count = len(os.listdir(BaseConfig.BLOCK_DIR))

    logger.info('Time to download {0} block files: {1}'.format(count, end - start))
    return count


def create_uptime_file_history(conn, df, page_size=100):
    temp_df = df.copy(deep=True)
    temp_df.drop('snark_work', axis=1, inplace=True)
    temp_df.drop('peer_id', axis=1, inplace=True)
    temp_df.drop('created_at', axis=1, inplace=True)
    temp_df.drop('block_hash', axis=1, inplace=True)

    temp_df = temp_df[['file_name', 'blockchain_epoch', 'remote_addr', 'submitter', 'state_hash', 'parent_state_hash',
                       'blockchain_height', 'slot', 'file_updated', 'file_created', 'file_generation', 'file_crc32c',
                       'file_md5_hash']]

    tuples = [tuple(x) for x in temp_df.to_numpy()]
    query = """INSERT INTO uptime_file_history (file_name, receivedat, receivedfrom, node_id , block_statehash,
    parent_block_statehash, nodedata_blockheight, nodedata_slot, file_modified_at, file_created_at, file_generation,
    file_crc32c, file_md5_hash) VALUES (%s, %s, %s, (SELECT id FROM nodes WHERE block_producer_key= %s),(SELECT id
    FROM statehash WHERE value=%s),(SELECT id FROM statehash WHERE value=%s), %s, %s, %s, %s, %s, %s, %s) """
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


def create_empty_folders():
    # comment- remove Blocks and Submissions directories
    shutil.rmtree(BaseConfig.BLOCK_DIR, ignore_errors=True)
    shutil.rmtree(BaseConfig.SUBMISSION_DIR, ignore_errors=True)
    # comment - create blocks and submissions directory
    os.makedirs(BaseConfig.BLOCK_DIR, exist_ok=True)
    os.makedirs(BaseConfig.SUBMISSION_DIR, exist_ok=True)


def get_batch_timings(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, batch_end_epoch FROM bot_logs ORDER BY batch_end_epoch DESC limit 1 ")
        result = cursor.fetchone()
        bot_log_id = result[0]
        prev_epoch = result[1]

        # comment - check if start script epoch available in env else use database epoch value
        if BaseConfig.START_SCRIPT_EPOCH:
            prev_epoch = BaseConfig.START_SCRIPT_EPOCH

        prev_batch_end = datetime.fromtimestamp(prev_epoch, timezone.utc)
        cur_batch_end = prev_batch_end + timedelta(minutes=BaseConfig.SURVEY_INTERVAL_MINUTES)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        return -1
    finally:
        cursor.close()
    return prev_batch_end, cur_batch_end, bot_log_id


def filter_state_hash_percentile(df, p=90):
    state_hash_list = df['state_hash'].value_counts().sort_values(ascending=False).index.to_list()

    unique_blk = list()
    for state_hash in state_hash_list:
        blk_count = df[df['state_hash'] == state_hash]['block_producer_key'].nunique()
        unique_blk.append(blk_count)

    percentile_result = round(np.percentile(unique_blk, p))
    good_state_hash_list = list()
    get_map = dict()
    for s in state_hash_list:
        blk_count = df[df['state_hash'] == s]['block_producer_key'].nunique()
        if blk_count >= percentile_result:
            good_state_hash_list.append(s)
            parent_node = df[df['state_hash'] == s]['parent_state_hash'].values[0]
            get_map[parent_node] = s
    return good_state_hash_list, get_map


def create_graph(batch_df, p_selected_node_df, c_selected_node, p_map):
    batch_graph = nx.DiGraph()
    parent_hash_list = batch_df['parent_state_hash'].unique()
    state_hash_list = set(list(batch_df['state_hash'].unique()) + list(p_selected_node_df['state_hash'].values))
    selected_parent = [parent for parent in parent_hash_list if parent in state_hash_list]
    """ t1=[w[42:] for w in list(p_selected_node_df['state_hash'].values)]
    t2=[w[42:] for w in c_selected_node]
    t3=[w[42:] for w in state_hash_list]
    batch_graph.add_nodes_from(t1)
    batch_graph.add_nodes_from( t2)
    batch_graph.add_nodes_from(t3) """

    batch_graph.add_nodes_from(list(p_selected_node_df['state_hash'].values))
    batch_graph.add_nodes_from(c_selected_node)
    batch_graph.add_nodes_from(state_hash_list)

    for row in batch_df.itertuples():
        state_hash = getattr(row, 'state_hash')
        parent_hash = getattr(row, 'parent_state_hash')

        if parent_hash in selected_parent:
            batch_graph.add_edge(parent_hash, state_hash)

    #  add edges from previous batch nodes
    batch_graph.add_edges_from(p_map)

    return batch_graph


def apply_weights(batch_graph, c_selected_node, p_selected_node):
    for node in list(batch_graph.nodes()):
        if node in c_selected_node:
            batch_graph.nodes[node]['weight'] = 0
        elif node in p_selected_node['state_hash'].values:
            batch_graph.nodes[node]['weight'] = p_selected_node[p_selected_node['state_hash'] == node]['weight'].values[
                0]
        else:
            batch_graph.nodes[node]['weight'] = 9999

    g_pos = None  # plot_graph(batch_graph, None, '1. first apply')
    return batch_graph, g_pos


def plot_graph(batch_graph, g_pos, title):
    # plot the graph
    plt.figure(figsize=(8, 8))
    plt.title(title)
    if not g_pos:
        g_pos = nx.spring_layout(batch_graph, k=0.3, iterations=1)
    nx.draw(batch_graph, pos=g_pos, connectionstyle='arc3, rad = 0.1', with_labels=False, node_size=500)
    t_dict = {}
    for n in batch_graph.nodes:
        if batch_graph.nodes[n]['weight'] == 0:
            t_dict[n] = (n[-4:], 0)
        else:
            t_dict[n] = (n[-4:], batch_graph.nodes[n]['weight'])
    nx.draw_networkx_labels(batch_graph, pos=g_pos, labels=t_dict, font_size=8);
    plt.show()  # pause before exiting
    return g_pos


def get_minimum_weight(graph, child_node):
    child_node_weight = graph.nodes[child_node]['weight']
    for parent in list(graph.predecessors(child_node)):
        lower = min(graph.nodes[parent]['weight'] + 1, child_node_weight)
        child_node_weight = lower
    return child_node_weight


def bfs(graph, queue_list, node, batch_statehash, g_pos):
    visited = list()
    visited.append(node)
    cnt = 2
    while queue_list:
        m = queue_list.pop(0)
        for neighbour in list(graph.neighbors(m)):
            if neighbour not in visited:
                graph.nodes[neighbour]['weight'] = get_minimum_weight(graph, neighbour)
                visited.append(neighbour)
                # if not neighbour in visited:
                queue_list.append(neighbour)
        # plot_graph(graph, g_pos, str(cnt)+'.'+m)
        cnt += 1
    shortlisted_state = []
    hash_weights = []
    for node in list(graph.nodes()):
        if graph.nodes[node]['weight'] <= BaseConfig.MAX_DEPTH_INCLUDE:
            # if node in batch_statehash:
            shortlisted_state.append(node)
            hash_weights.append(graph.nodes[node]['weight'])

    shortlisted_state_hash_df = pd.DataFrame()
    shortlisted_state_hash_df['state_hash'] = shortlisted_state
    shortlisted_state_hash_df['weight'] = hash_weights
    return shortlisted_state_hash_df


def insert_state_hash_results(df, conn=connection, page_size=100):
    temp_df = df[['parent_state_hash', 'state_hash', 'weight', 'bot_log_id']]
    tuples = [tuple(x) for x in temp_df.to_numpy()]
    query = """INSERT INTO bot_logs_statehash(parent_statehash_id, statehash_id, weight, bot_log_id ) 
        VALUES ( (SELECT id FROM statehash WHERE value= %s), (SELECT id FROM statehash WHERE value= %s), %s, %s ) """
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


def get_previous_statehash(bot_log_id, conn=connection):
    cursor = conn.cursor()
    try:
        sql_quary = """select  ps.value parent_statehash, s1.value statehash, b.weight
            from bot_logs_statehash b join statehash s1 ON s1.id = b.statehash_id 
		    join statehash ps on b.parent_statehash_id = ps.id where bot_log_id =%s"""
        cursor.execute(sql_quary, (bot_log_id,))
        result = cursor.fetchall()

        df = pd.DataFrame(result, columns=['parent_state_hash', 'state_hash', 'weight'])
        previous_result_df = df[['parent_state_hash', 'state_hash']]
        p_selected_node_df = df[['state_hash', 'weight']]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return previous_result_df, p_selected_node_df


def create_bot_log(conn, values):
    # files_processed file_timestamps state_hash batch_start_epoch batch_end_epoch
    query = """INSERT INTO bot_logs(files_processed, file_timestamps, batch_start_epoch, batch_end_epoch, 
                processing_time, number_of_threads)  values ( %s, %s, %s, %s, %s, %s) RETURNING id """
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


def find_new_values_to_insert(existing_values, new_values):
    return existing_values.merge(new_values, how='outer', indicator=True) \
        .loc[lambda x: x['_merge'] == 'right_only'].drop('_merge', 1).drop_duplicates()


def get_relation_list(df):
    relation_list = []
    for child, parent in df[['state_hash', 'parent_state_hash']].values:
        if parent in df['state_hash'].values:
            relation_list.append((parent, child))
    return relation_list


def main():
    update_email_discord_status(connection)
    process_loop_count = 0
    prev_batch_end, cur_batch_end, bot_log_id = get_batch_timings(connection)
    cur_timestamp = datetime.now(timezone.utc)
    if BaseConfig.END_SCRIPT_EPOCH:
        cur_timestamp = datetime.fromtimestamp(BaseConfig.END_SCRIPT_EPOCH, timezone.utc)

    relation_df, p_selected_node_df = get_previous_statehash(bot_log_id)
    p_map = get_relation_list(relation_df)

    logger.info("script start at {0}  end at {1}".format(prev_batch_end, cur_timestamp))
    do_process = True
    while do_process:
        existing_state_df = get_state_hash_df(connection)
        existing_nodes = get_existing_nodes(connection)
        create_empty_folders()
        logger.info('running for batch: {0} - {1}'.format(prev_batch_end, cur_batch_end))
        script_offset = os.path.commonprefix([str(prev_batch_end.strftime("%Y-%m-%dT%H:%M:%SZ")),
                                              str(cur_batch_end.strftime("%Y-%m-%dT%H:%M:%SZ"))])

        if cur_batch_end > cur_timestamp:
            logger.info('all files are processed till date')
            break
        else:
            master_df, state_hash_df = get_batch_for_processing(prev_batch_end, cur_batch_end)
            # comment- returns true if master_df is empty
            uptime_flag = master_df.empty

            if uptime_flag:
                master_df = download_uptime_files(script_offset, prev_batch_end, cur_batch_end)

            all_file_count = master_df.shape[0]
            if all_file_count > 0:
                if uptime_flag:
                    count = download_dat_files(list(master_df.block_hash))
                    if count <= 0:
                        logger.info("No dat files in BLOCKS directory")
                        break

                start = time()
                threads_used = 1
                if uptime_flag:
                    state_hash_df, threads_used = processing_batch_files(list(master_df['file_name']),
                                                                         BaseConfig.MAX_VERIFIER_INSTANCES)

                end = time()

                logger.info('Time to validate {0} files: {1} seconds'.format(all_file_count, end - start))
                if not state_hash_df.empty:
                    master_df['state_hash'] = state_hash_df['state_hash']
                    master_df['blockchain_height'] = state_hash_df['height']
                    master_df['slot'] = pd.to_numeric(state_hash_df['slot'])
                    master_df['parent_state_hash'] = state_hash_df['parent']

                    master_df['state_hash'] = master_df['state_hash'].apply(lambda x: x.strip())
                    master_df['parent_state_hash'] = master_df['parent_state_hash'].apply(lambda x: x.strip())
                    # comment - get unique statehash in batch data
                    state_hash = pd.unique(master_df[['state_hash', 'parent_state_hash']].values.ravel('k'))
                    state_hash_to_insert = find_new_values_to_insert(existing_state_df,
                                                                     pd.DataFrame(state_hash, columns=['statehash']))
                    # comment- insert unique statehash into statehash table
                    if not state_hash_to_insert.empty:
                        create_statehash(connection, state_hash_to_insert)

                    nodes_in_cur_batch = pd.DataFrame(master_df['submitter'].unique(),
                                                      columns=['block_producer_key'])
                    node_to_insert = find_new_values_to_insert(existing_nodes, nodes_in_cur_batch)

                    # comment- insert unique block_producer_key into nodes table
                    if not node_to_insert.empty:
                        node_to_insert['updated_at'] = datetime.now(timezone.utc)
                        create_node_record(connection, node_to_insert, 100)

                    # comment - insert batch data into uptime_file_history table
                    if uptime_flag:
                        create_uptime_file_history(connection, master_df)

                    if 'snark_work' in master_df.columns:
                        master_df.drop('snark_work', axis=1, inplace=True)

                    columns_to_drop = ['remote_addr', 'file_created',
                                       'file_generation', 'file_owner', 'file_crc32c', 'file_md5_hash']
                    master_df.drop(columns=columns_to_drop, axis=1, inplace=True, errors='ignore')
                    master_df = master_df.rename(
                        columns={'file_updated': 'file_timestamps', 'submitter': 'block_producer_key'})

                    c_selected_node, c_map = filter_state_hash_percentile(master_df)
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
                    p_selected_node_df = shortlisted_state_hash_df.copy()
                    # comment - get the parent_state_hash of shortlisted list
                    parent_hash = []
                    for s in shortlisted_state_hash_df['state_hash'].values:
                        p_hash = master_df[master_df['state_hash'] == s]['parent_state_hash'].values[0]
                        parent_hash.append(p_hash)
                    shortlisted_state_hash_df['parent_state_hash'] = parent_hash

                    p_map = get_relation_list(shortlisted_state_hash_df[['parent_state_hash', 'state_hash']])
                    try:
                        if not point_record_df.empty:
                            file_timestamp = master_df.iloc[-1]['file_timestamps']
                        else:
                            file_timestamp = cur_batch_end
                            logger.info('empty point record for start epoch {0} end epoch {1} '.format(
                                prev_batch_end.timestamp(), cur_batch_end.timestamp()))

                        values = all_file_count, file_timestamp, prev_batch_end.timestamp(), cur_batch_end.timestamp(), end - start, threads_used
                        bot_log_id = create_bot_log(connection, values)

                        shortlisted_state_hash_df['bot_log_id'] = bot_log_id
                        insert_state_hash_results(shortlisted_state_hash_df)

                        if not point_record_df.empty:
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
