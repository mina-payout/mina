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
import glob
import csv
import pydot
import re

from copy import deepcopy
from pylab import rcParams
from networkx.drawing.nx_agraph import graphviz_layout

warnings.filterwarnings('ignore')

def connect():
    connection = psycopg2.connect(
        host=BaseConfig.POSTGRES_HOST,
        port=BaseConfig.POSTGRES_PORT,
        database=BaseConfig.POSTGRES_DB,
        user=BaseConfig.POSTGRES_USER,
        password=BaseConfig.POSTGRES_PASSWORD
    )
    return connection


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


def get_batch_for_processing(prev_batch_end, cur_batch_end, conn):
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
        logger.exception("get_batch_for_processing")
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
        logger.exception("get_existing_nodes")
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
        logger.info("updated emails")
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("update_email_discord_status")
        cursor.close()
        return -1
    finally:
        cursor.close()
        conn.commit()
        logger.info("committed to db")
    return 0


def get_state_hash_df(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("select value from statehash")
        result = cursor.fetchall()
        state_hash = pd.DataFrame(result, columns=['statehash'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("get_state_hash_df")
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
        logger.exception("create_node_record")
        cursor.close()
        return 1
    finally:
        cursor.close()
    return 0


def create_statehash(conn, statehash_df, page_size=100):
    query = """INSERT INTO statehash ( value) VALUES ( %s) 
     ON CONFLICT DO NOTHING """
    cursor = conn.cursor()
    try:
        statehash_df.dropna()
        tuples = [tuple(x) for x in statehash_df.to_numpy()]
        logger.info('statehash tuples: {0}'.format(tuples))
        cursor = conn.cursor()
        extras.execute_batch(cursor, query, tuples, page_size)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("create_statehash")
        cursor.close()
        conn.rolllback()
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
        logger.exception("create_point_record")
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
        file_epoch = calendar.timegm(tm.strptime(file_timestamp,  "%Y-%m-%dT%H:%M:%SZ"))
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
        #elif file_epoch > twenty_min_add.timestamp():
        #    break
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
    #df.to_csv('/var/log/minanet/source_{0}.csv'.format(datetime.now(timezone.utc).timestamp()))
    
    return df


def download_dat_files(state_hashes):
    bucket = get_gcs_bucket()
    count = 0
    file_names = list()
    for sh in state_hashes:
        file_names.append('blocks/' + sh + '.dat')

    logger.info('downloading block files {0}'.format(file_names))
    start = time()
    tmp = download_batch_into_files(file_names, bucket)

    end = time()
    count = len(os.listdir(BaseConfig.BLOCK_DIR))
    
    logger.info('Time to download {0} block files: {1}'.format(count, end - start))
    return count


def create_uptime_file_history(conn, df, page_size=100):
    #temp_df = df.copy(deep=True)
    temp_df = df[df['blockchain_height'] > 0]
    temp_df.drop('snark_work', axis=1, inplace=True)
    temp_df.drop('peer_id', axis=1, inplace=True)
    temp_df.drop('created_at', axis=1, inplace=True)
    temp_df.drop('block_hash', axis=1, inplace=True)

    temp_df = temp_df[['file_name', 'blockchain_epoch', 'remote_addr', 'submitter', 'state_hash', 'parent_state_hash',
                       'blockchain_height', 'slot', 'file_updated', 'file_created', 'file_generation', 'file_crc32c',
                       'file_md5_hash']]
   
    query = """INSERT INTO uptime_file_history (file_name, receivedat, receivedfrom, node_id , block_statehash,
    parent_block_statehash, nodedata_blockheight, nodedata_slot, file_modified_at, file_created_at, file_generation,
    file_crc32c, file_md5_hash) VALUES (%s, %s, %s, (SELECT id FROM nodes WHERE block_producer_key= %s),(SELECT id
    FROM statehash WHERE value=%s),(SELECT id FROM statehash WHERE value=%s), %s, %s, %s, %s, %s, %s, %s) """
    try:
        #logger.info(' ==== temp_df: {0}'.format(temp_df.to_string())) 
        temp_df['state_hash'].fillna('None', inplace=True)
        temp_df['parent_state_hash'].fillna('None', inplace=True)
        temp_df['blockchain_height'].fillna(0, inplace=True)
        temp_df['slot'].fillna(0, inplace=True)
        tuples = [tuple(x) for x in temp_df.to_numpy()]

        cursor = conn.cursor()
        extras.execute_batch(cursor, query, tuples, page_size)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("error in create_uptime_file_history ")
        logger.error("Failed query: {0}".format(str(cursor._last_executed)))
        cursor.close()
        return -1
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
        cursor.execute("""( select id, batch_start_epoch start_epoch, status
                    from bot_logs bl
                    where status =-1
                    order by batch_start_epoch desc) 
                    union all 
                    (select id, batch_end_epoch start_epoch, status
                    from bot_logs bl2
                    where status <>-1
                    order by batch_end_epoch desc
                    limit 1) order by status, id asc """)
        result = cursor.fetchone()
        bot_log_id = result[0]
        prev_batch_end_epoch = result[1]
        status = result[2]
        logger.info("selected bot_log id")
        # comment - check if start script epoch available in env else use database epoch value
        if BaseConfig.START_SCRIPT_EPOCH:
            prev_batch_end_epoch = BaseConfig.START_SCRIPT_EPOCH

        prev_batch_end_ts = datetime.fromtimestamp(prev_batch_end_epoch, timezone.utc)
        cur_batch_end_ts = prev_batch_end_ts + timedelta(minutes=BaseConfig.SURVEY_INTERVAL_MINUTES)

        if status==-1:
            #files_processed file_timestamps processing_time number_of_threads status bot_log_id
            update_values = 0, None, 0, 0, 0, bot_log_id
            update_bot_log(conn, update_values, True)
        else:
            values = prev_batch_end_ts.timestamp(), cur_batch_end_ts.timestamp(), 0
            bot_log_id = create_bot_log(conn, values)
        logger.info("finalized bot_log id")    
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("get_batch_timings")
        return -1
    finally:
        cursor.close()
    return prev_batch_end_ts, cur_batch_end_ts, bot_log_id


def filter_state_hash_percentage(df, p=BaseConfig.PERCENT_PARAM):
    state_hash_list = df['state_hash'].value_counts().sort_values(ascending=False).index.to_list()
    # get 34% number of blk in given batch
    total_unique_blk = df['block_producer_key'].nunique()
    percentage_result = round(total_unique_blk * p, 2)
    good_state_hash_list = list()
    for s in state_hash_list:
        blk_count = df[df['state_hash'] == s]['block_producer_key'].nunique()
        # check blk_count for state_hash submitted by blk least 34%
        if blk_count >= percentage_result:
            good_state_hash_list.append(s)
    return good_state_hash_list


def create_graph(batch_df, p_selected_node_df, c_selected_node, p_map):
    batch_graph = nx.DiGraph()
    parent_hash_list = batch_df['parent_state_hash'].unique()
    state_hash_list = set(list(batch_df['state_hash'].unique()) + list(p_selected_node_df['state_hash'].values))
    selected_parent = [parent for parent in parent_hash_list if parent in state_hash_list]
    
    batch_graph.add_nodes_from(list(p_selected_node_df['state_hash'].values))
    batch_graph.add_nodes_from(c_selected_node)
    batch_graph.add_nodes_from(state_hash_list)
    #add_nodes_from_list(batch_graph, list(p_selected_node_df['state_hash'].values))
    #add_nodes_from_list(batch_graph, c_selected_node)
    #add_nodes_from_list(batch_graph, state_hash_list)

    #pdot = nx.drawing.nx_pydot.to_pydot(batch_graph)
    #for i, node in enumerate(pdot.get_nodes()):
    #    node.set_label(node[-4:])

    for row in batch_df.itertuples():
        state_hash = getattr(row, 'state_hash')
        parent_hash = getattr(row, 'parent_state_hash')

        if parent_hash in selected_parent:
            batch_graph.add_edge(parent_hash, state_hash)

    #  add edges from previous batch nodes
    batch_graph.add_edges_from(p_map)

    return batch_graph

def add_nodes_from_list(batch_graph, nodes_list):
    for node in nodes_list:
        batch_graph.add_node(pydot.Node(node, label=str(node)[-4:])) 

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


def apply_weights_new(batch_graph, c_selected_node, p_selected_node):
    for node in list(batch_graph.nodes()):
        weight = 0
        if node in c_selected_node:
            weight = 0
        elif node in p_selected_node['state_hash'].values:
            weight = p_selected_node[p_selected_node['state_hash'] == node]['weight'].values[0]
        else:
            weight = 9999

        batch_graph.nodes[node]['weight'] = weight
        batch_graph.nodes[node]['label'] = (str(node)[-4:]+ ', {0}'.format(weight))
    g_pos = None  # plot_graph(batch_graph, None, '1. first apply')
    return batch_graph, g_pos

def get_node_label(node, weights):
    #logger.info(node)
    name = str(node)[46:52]
    weight = weights[node]
    n_label = '{0} \n {1}'.format(name, weight)
    #logger.info(n_label)
    return n_label

def plot_graph(batch_graph, title, log_folder):
    try:
        names = nx.get_node_attributes(batch_graph, 'Name')
        weights = nx.get_node_attributes(batch_graph, 'weight')
        logger.info(f"Name: {names}\n type:{type(names)}")
        logger.info(f"weights: {weights}\n type:{type(weights)}")

        labelz = {node : get_node_label(node, weights) for node in batch_graph}
        #logger.info(labelz)
        #(pd.DataFrame.from_dict(data=labelz, orient='index').to_csv(log_folder+'/'+'node_weights.csv', header=False))
        
        rcParams['figure.figsize'] = 30, 30
        pos=graphviz_layout(batch_graph, prog='dot', args='-Gsplines=true -Gnodesep=2 -Goverlap=scalexy')
        pdot = nx.drawing.nx_pydot.to_pydot(batch_graph)

        nx.draw_networkx_nodes(batch_graph, pos, node_shape='s', node_size=300)
        nx.draw_networkx_edges(batch_graph, pos, edgelist=batch_graph.edges(), arrows=True)

        labelDescr = nx.draw_networkx_labels(batch_graph, pos=pos, labels=labelz, font_size=6, 
                                horizontalalignment='center', verticalalignment='center', clip_on=True)
        
        #for n,t in labelDescr.items():
        #    finDegree = 70
        #    t.set_rotation(finDegree)

        nx.draw(batch_graph, pos=pos,
            node_color='lightgreen', 
            node_size=1500,
            with_labels=False, 
            arrows=True)
        
        plt.savefig('{0}.pdf'.format(log_folder+'/'+str(title)), bbox_inches='tight')
    except(Exception ) as error:
        logger.exception("plot_graph")
        logger.info(f"batch_graph: {batch_graph}\n type:{type(batch_graph)}")

def plot_graph_sprint(batch_graph, g_pos, title):
    # plot the graph
    plt.figure(figsize=(24, 24))
    plt.title(title)
    
    if not g_pos:
        g_pos = nx.spring_layout(batch_graph, k=0.3, iterations=1)
    #logger.info(batch_graph)
    #logger.info(g_pos)

    nx.draw(batch_graph, pos=g_pos,  with_labels=False, node_size=1500, node_color='lightgreen', arrows=True)
    t_dict = {}
    for n in batch_graph.nodes:
        if batch_graph.nodes[n]['weight'] == 0:
            t_dict[n] = (str(n)[-4:], 0)
        else:
            t_dict[n] = (str(n)[-4:], batch_graph.nodes[n]['weight'])
    nx.draw_networkx_labels(batch_graph, pos=g_pos, labels=t_dict, font_size=6);

    """for n in batch_graph.nodes:
        weight = batch_graph.nodes[n]['weight']
        n.set_label(str(n)[-4:]+ ', {0}'.format(weight))"""
    #plt.show()  # pause before exiting
    plt.savefig('{0}.pdf'.format(title), bbox_inches='tight')
    plt.close()
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


def insert_state_hash_results(df, conn, page_size=100):
    temp_df = df[['parent_state_hash', 'state_hash', 'weight', 'bot_log_id']]
    tuples = [tuple(x) for x in temp_df.to_numpy()]
    query = """INSERT INTO bot_logs_statehash(parent_statehash_id, statehash_id, weight, bot_log_id ) 
        VALUES ( (SELECT id FROM statehash WHERE value= %s), (SELECT id FROM statehash WHERE value= %s), %s, %s ) """
    cursor = conn.cursor()
    try:
        extras.execute_batch(cursor, query, tuples, page_size)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("insert_state_hash_results")
        cursor.close()
        return 1
    finally:
        cursor.close()
    return 0


def get_previous_statehash(bot_log_id, conn):
    cursor = conn.cursor()
    try:
        sql_quary = """select  ps.value parent_statehash, s1.value statehash, b.weight
            from bot_logs_statehash b join statehash s1 ON s1.id = b.statehash_id 
            join statehash ps on b.parent_statehash_id = ps.id 
            join bot_logs bl on b.bot_log_id = bl.id
            where  batch_end_epoch =( select batch_start_epoch  from bot_logs bl where id =%s) """
        cursor.execute(sql_quary, (bot_log_id,))
        result = cursor.fetchall()

        df = pd.DataFrame(result, columns=['parent_state_hash', 'state_hash', 'weight'])
        previous_result_df = df[['parent_state_hash', 'state_hash']]
        p_selected_node_df = df[['state_hash', 'weight']]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("get_previous_statehash")
        cursor.close()
        return -1
    finally:
        cursor.close()
    return previous_result_df, p_selected_node_df


def create_bot_log(conn, values):
    # files_processed file_timestamps state_hash batch_start_epoch batch_end_epoch
    query = """INSERT INTO bot_logs(batch_start_epoch, batch_end_epoch, status)  values ( %s, %s, %s) RETURNING id """
    try:
        cursor = conn.cursor()
        cursor.execute('LOCK TABLE bot_logs IN ACCESS EXCLUSIVE MODE')
        cursor.execute(query, values)
        result = cursor.fetchone()
        logger.info('created bot_log id {0}'.format(result[0]))
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("create_bot_log")
        cursor.close()
        conn.rollback()
        return -1
    finally:
        cursor.close()
        conn.commit()
    return result[0]

def update_bot_log(conn, values, lock_table=False):
    # files_processed file_timestamps processing_time number_of_threads status bot_log_id
    query = """UPDATE public.bot_logs
            SET files_processed=%s, file_timestamps=%s, processing_time=%s, number_of_threads=%s, status=%s 
            where id = %s """
    try:
        cursor = conn.cursor()
        if lock_table:
            cursor.execute('LOCK TABLE bot_logs IN ACCESS EXCLUSIVE MODE')
        cursor.execute(query, values)
        logger.info('update_bot_log completed {0}'.format(values))
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("update_bot_log")
        cursor.close()
        conn.rollback()
        #return -1
    finally:
        cursor.close()
        conn.commit()
    #return result[0]

def find_new_values_to_insert(existing_values, new_values):
    try:
        result = existing_values.merge(new_values, how='outer', indicator=True) \
        .loc[lambda x: x['_merge'] == 'right_only'].drop('_merge', 1).drop_duplicates()
    except (Exception ) as error:
        logger.info("existing values: {0}".format(existing_values))
        logger.info("new_values values: {0}".format(new_values))
        logger.exception("find_new_values_to_insert")
        result = new_values
    return result

def get_relation_list(df):
    relation_list = []
    for child, parent in df[['state_hash', 'parent_state_hash']].values:
        if parent in df['state_hash'].values:
            relation_list.append((parent, child))
    return relation_list

def update_scoreboard(conn, score_till_time):
    sql = """with vars  (snapshot_date, start_date) as( values (%s AT TIME ZONE 'UTC', 
			(%s - interval '%s' day) AT TIME ZONE 'UTC')
	)
	, epochs as(
		select extract('epoch' from snapshot_date) as end_epoch,
		extract('epoch' from start_date) as start_epoch from vars
	)
	, b_logs as(
		select  COUNT(1) OVER()  as surveys, id
		from bot_logs b , epochs e
		where b.batch_start_epoch between start_epoch and end_epoch and status=1
	)
	, scores as (
		select p.node_id, count(p.bot_log_id) bp_points
		from points_summary p join b_logs b on p.bot_log_id =b.id
		group by 1
	)
	, final_scores as (
	select node_id, bp_points, 
		surveys, trunc( ((bp_points::decimal*100) / surveys),2) as score_perc
	from scores l join nodes n on l.node_id=n.id, b_logs t
	)
	update nodes nrt set score = s.bp_points, score_percent=s.score_perc  
	from final_scores s where nrt.id=s.node_id """

    history_sql="""insert into score_history (node_id, score_at, score, score_percent)
        SELECT id as node_id, %s, score, score_percent from nodes where score is not null ON CONFLICT DO NOTHING """
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (score_till_time, score_till_time, BaseConfig.UPTIME_DAYS_FOR_SCORE,))
        cursor.execute(history_sql, (score_till_time,))
    except (psycopg2.DatabaseError, Exception) as error:
        logger.exception("update_scoreboard")
        cursor.close()
        return -1
    finally:
        cursor.close()
    return 0


def list_to_file(file_to_save, list_to_save):
    with open(file_to_save, 'wb') as myfile:
        wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
        wr.writerow(list_to_save)

# enables extra logging on prod to identify invalid block files
def extraLogging(state_hash_df, master_df, bot_log_id):
    
    try:
        # Get a list of files (file paths) in the given directory 
        list_of_files = filter( os.path.isfile,
                                glob.glob(BaseConfig.BLOCK_DIR + '/*') )
        # get list of ffiles with size
        files_with_size = [ (file_path, os.stat(file_path).st_size) 
                            for file_path in list_of_files ]
        # Iterate over list of tuples i.e. file_paths with size
        # and print them one by one
        for file_path, file_size in files_with_size:
            logger.info('Block files downloaded \n: {0} --> {1}'.format(file_path, file_size))
        log_folder = BaseConfig.LOGGING_LOCATION+'tmp/'+ str(bot_log_id ) # datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        os.makedirs(log_folder)

        tmp = master_df.drop('snark_work', axis=1, errors='ignore')
        state_hash_df.to_csv(log_folder+'/state_hash_df.csv')
        tmp.to_csv(log_folder+'/0_master_df.csv')
        #move block files and dowloaded uptime files
        #shutil.copy(BaseConfig.ROOT_DIR, log_folder)
    except(Exception ) as error:
        logger.exception("extraLogging")
    return log_folder

def main():
    connection = connect()
    update_email_discord_status(connection)
    process_loop_count = 0
    prev_batch_end, cur_batch_end, bot_log_id = get_batch_timings(connection)
    relation_df, p_selected_node_df = get_previous_statehash(bot_log_id, connection)
    connection.close()
    p_map = get_relation_list(relation_df)

    logger.info("first script start at {0}  end at {1}".format(prev_batch_end, cur_batch_end))
    do_process = True
    while do_process:
        #tm.sleep(10)
        logger.info("inside while loop {0}".format(process_loop_count))
        try:
            connection = connect()
            existing_state_df = get_state_hash_df(connection)
            existing_nodes = get_existing_nodes(connection)
            connection.close()
            create_empty_folders()
            logger.info('running for batch: {0} - {1}'.format(prev_batch_end, cur_batch_end))
            script_offset = os.path.commonprefix([str(prev_batch_end.strftime("%Y-%m-%dT%H:%M:%SZ")),
                                                str(cur_batch_end.strftime("%Y-%m-%dT%H:%M:%SZ"))])

            if cur_batch_end > datetime.now(timezone.utc):
                connection = connect()
                logger.info('all files are processed till date')
                update_values = None, None, 0, 0, -1, bot_log_id
                update_bot_log(connection, update_values)
                connection.close()
                break
            else:
                #master_df, state_hash_df = get_batch_for_processing(prev_batch_end, cur_batch_end)
                master_df = pd.DataFrame() 
                state_hash_df = pd.DataFrame() 
                # comment- returns true if master_df is empty
                uptime_flag = master_df.empty

                if uptime_flag:
                    master_df = download_uptime_files(script_offset, prev_batch_end, cur_batch_end)

                all_file_count = master_df.shape[0]
                if all_file_count > 0:
                    if uptime_flag:
                        count = download_dat_files(list(master_df['block_hash'].unique()))
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
                        
                        verifier_dropped_df = master_df.query("state_hash == ''")
                        
                        # comment - get unique statehash in batch data
                        state_hash = pd.unique(master_df[['state_hash', 'parent_state_hash']].values.ravel('k'))
                        state_hash_to_insert = find_new_values_to_insert(existing_state_df,
                                                                        pd.DataFrame(state_hash, columns=['statehash']))
                        logger.info('state_hash_to_insert : {0}: {1}'.format(state_hash_to_insert.empty, state_hash_to_insert.to_string()))
                        
                        nodes_in_cur_batch = pd.DataFrame(master_df['submitter'].unique(),
                                                        columns=['block_producer_key'])
                        node_to_insert = find_new_values_to_insert(existing_nodes, nodes_in_cur_batch)

                        
                        # comment - insert batch data into uptime_file_history table
                        uptime_file_history_df = master_df.copy()
                        
                        if 'snark_work' in master_df.columns:
                            master_df.drop('snark_work', axis=1, inplace=True)

                        columns_to_drop = ['remote_addr', 'file_created',
                                        'file_generation', 'file_owner', 'file_crc32c', 'file_md5_hash']
                        master_df.drop(columns=columns_to_drop, axis=1, inplace=True, errors='ignore')
                        master_df = master_df.rename(
                            columns={'file_updated': 'file_timestamps', 'submitter': 'block_producer_key'})

                        c_selected_node = filter_state_hash_percentage(master_df)

                        percentile_filter_df = master_df.query(("state_hash not in @c_selected_node"))

                        #logger.info('c_selected_node')
                        #ogger.info(c_selected_node)
                        #logger.info('p_map')
                        #logger.info(p_map)
                        batch_graph = create_graph(master_df, p_selected_node_df, c_selected_node, p_map)
                        weighted_graph, g_pos = apply_weights(batch_graph=batch_graph, c_selected_node=c_selected_node,
                                                            p_selected_node=p_selected_node_df)
                        
                        queue_list = list(p_selected_node_df['state_hash'].values) + c_selected_node

                        batch_state_hash = list(master_df['state_hash'].unique())

                        shortlisted_state_hash_df = bfs(graph=weighted_graph, queue_list=queue_list, node=queue_list[0],
                                                        batch_statehash=batch_state_hash, g_pos=g_pos)

                        point_record_df = master_df[
                            master_df['state_hash'].isin(shortlisted_state_hash_df['state_hash'].values)]


                        bfs_filter_df = master_df[~master_df['state_hash'].isin(shortlisted_state_hash_df['state_hash'].values)]
                        log_folder = extraLogging(state_hash_df, master_df, bot_log_id)
                        p_selected_node_df.to_csv(log_folder+'/p_selected_node_df.csv')
                        shortlisted_state_hash_df.to_csv(log_folder+'/shortlisted_state_hash_df.csv')
                        verifier_dropped_df.to_csv(log_folder+'/1_verifier_dropped_df.csv')
                        percentile_filter_df.to_csv(log_folder+'/2_percentile_filter_df.csv')
                        bfs_filter_df.to_csv(log_folder+'/3_bfs_filter_df.csv')
                        point_record_df.to_csv(log_folder+'/4_point_record_df.csv')
                        point_file_count = point_record_df.shape[0]
                        files_dropped_perc = (point_file_count/all_file_count)*100
                        logger.info('files_dropped_perc:{0} master_df size:{1}, point_record_df size:{2}'.format(files_dropped_perc, all_file_count, point_file_count))
                        logger.info(weighted_graph)
                        plot_graph(weighted_graph, bot_log_id, log_folder)
                        g_pos = None
                    

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
                            connection = connect()
                            # comment- insert unique statehash into statehash table
                            if not state_hash_to_insert.empty:
                                create_statehash(connection, state_hash_to_insert)
                                logger.info('create_statehash completed')

                            # comment- insert unique block_producer_key into nodes table
                            if not node_to_insert.empty:
                                node_to_insert['updated_at'] = datetime.now(timezone.utc)
                                create_node_record(connection, node_to_insert, 100)
                                logger.info('create_node_record completed')

                            if uptime_flag:
                                result = create_uptime_file_history(connection, uptime_file_history_df)
                                logger.info('create_uptime_file_history completed')
                                
                            shortlisted_state_hash_df['bot_log_id'] = bot_log_id
                            insert_state_hash_results(shortlisted_state_hash_df, connection)
                            logger.info('insert_state_hash_results completed')
                            if not point_record_df.empty:
                                point_record_df['amount'] = 1
                                point_record_df['created_at'] = datetime.now(timezone.utc)
                                point_record_df['bot_log_id'] = bot_log_id
                                point_record_df = point_record_df[
                                    ['file_name', 'file_timestamps', 'blockchain_epoch', 'block_producer_key',
                                    'blockchain_height', 'amount', 'created_at', 'bot_log_id', 'state_hash']]

                                create_point_record(connection, point_record_df)
                                logger.info('create_point_record completed')
                                update_values = all_file_count, file_timestamp, end - start, threads_used, 1, bot_log_id
                                update_bot_log(connection, update_values)
                                update_scoreboard(connection, cur_batch_end)
                        except Exception as error:
                            connection.rollback()
                            connection.close()
                            update_values = 0, '', 0, -1, bot_log_id
                            update_bot_log(connection, update_values)
                            logger.exception("Updating points")
                        finally:
                            connection.commit()
                            connection.close()
                        process_loop_count += 1
                        logger.info('Processed it loop count : {0}'.format(process_loop_count))

                    else:
                        logger.info('Finished processing data from table.')
                else:
                    logger.info('Zero files found.')
                    update_values = all_file_count, None, 0, 0, 1, bot_log_id
                    connection = connect()
                    update_bot_log(connection, update_values)
                    connection.close()
               
                tm.sleep(10)
                connection = connect()
                prev_batch_end, cur_batch_end, bot_log_id = get_batch_timings(connection)
                #prev_batch_end = cur_batch_end
                #cur_batch_end = prev_batch_end + timedelta(minutes=BaseConfig.SURVEY_INTERVAL_MINUTES)
                if cur_batch_end >= datetime.now(timezone.utc):
                    update_values = None, None, 0, 0, -1, bot_log_id
                    update_bot_log(connection, update_values)
                    do_process = False
                connection.close()
        except Exception as genericError:
            logger.exception("Unknown Error")
if __name__ == '__main__':
    main()
