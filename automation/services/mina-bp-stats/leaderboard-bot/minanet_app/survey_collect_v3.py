import networkx as nx
import os
from datetime import datetime, timedelta, timezone
from time import time
import numpy as np
from config import BaseConfig
import psycopg2
import psycopg2.extras as extras
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from logger_util import logger

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', None)

ERROR = 'Error: {0}'

connection_aws = psycopg2.connect(
    host=BaseConfig.POSTGRES_HOST_AWS,
    port=BaseConfig.POSTGRES_PORT_AWS,
    database=BaseConfig.POSTGRES_DB_AWS,
    user=BaseConfig.POSTGRES_USER_AWS,
    password=BaseConfig.POSTGRES_PASSWORD_AWS
)

connection = psycopg2.connect(
    host=BaseConfig.POSTGRES_HOST,
    port=BaseConfig.POSTGRES_PORT,
    database=BaseConfig.POSTGRES_DB,
    user=BaseConfig.POSTGRES_USER,
    password=BaseConfig.POSTGRES_PASSWORD
)


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


def find_new_values_to_insert(existing_values, new_values):
    return existing_values.merge(new_values, how='outer', indicator=True) \
        .loc[lambda x: x['_merge'] == 'right_only'].drop('_merge', 1).drop_duplicates()


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


def filter_state_hash_percentile(df, p=0.9):
    get_map = dict()
    state_hash_list = df['state_hash'].value_counts().sort_values(ascending=False).index.to_list()
    # comment - get number of total unique block producer key
    num_unique_blk = df['block_producer_key'].nunique()
    good_state_hash_list = list()
    total_blk_count = 0
    for s in state_hash_list:
        # comment - filter the number of block producer having state hash s
        total_block_producers = df[df['state_hash'] == s]['block_producer_key']
        parent_node = df[df['state_hash'] == s]['parent_state_hash'].values[0]
        total_blk_count = total_blk_count + len(total_block_producers)
        good_state_hash_list.append(s)
        get_map[parent_node] = s
        if total_blk_count > p * num_unique_blk:
            break

    return good_state_hash_list, get_map


def create_graph(batch_df, p_selected_node, c_selected_node):
    batch_graph = nx.DiGraph()
    parent_hash_list = batch_df['parent_state_hash'].unique()
    state_hash_list = batch_df['state_hash'].unique()
    selected_parent = [parent for parent in parent_hash_list if parent in state_hash_list]

    batch_graph.add_nodes_from(p_selected_node)
    batch_graph.add_nodes_from(c_selected_node)
    batch_graph.add_nodes_from(state_hash_list)

    for row in batch_df.itertuples():
        state_hash = getattr(row, 'state_hash')
        parent_hash = getattr(row, 'parent_state_hash')

        if parent_hash in selected_parent:
            batch_graph.add_edge(parent_hash, state_hash)
    return batch_graph


def apply_weights(batch_graph, c_selected_node):
    for node in list(batch_graph.nodes()):
        if node in c_selected_node:
            batch_graph.nodes[node]['weight'] = 0
        else:
            batch_graph.nodes[node]['weight'] = np.inf
    return batch_graph


def get_minimum_weight(graph, child_node):
    child_node_weight = graph.nodes[child_node]['weight']
    for parent in list(graph.predecessors(child_node)):
        lower = min(graph.nodes[parent]['weight'] + 1, child_node_weight)
        child_node_weight = lower
    return child_node_weight


def bfs(graph, queue_list, node):
    visited = list()
    visited.append(node)
    while queue_list:
        m = queue_list.pop(0)
        for neighbour in list(graph.neighbors(m)):
            if neighbour not in visited:
                graph.nodes[neighbour]['weight'] = get_minimum_weight(graph, neighbour)
                visited.append(neighbour)
                queue_list.append(neighbour)
    shortlisted_state = []
    for node in list(graph.nodes()):
        if graph.nodes[node]['weight'] > BaseConfig.MAX_DEPTH:
            shortlisted_state.append(node)
    return shortlisted_state


def insert_state_hash_results(df, conn=connection, page_size=100):
    tuples = [tuple(x) for x in df.to_numpy()]
    query = """INSERT INTO percentile_statehash_table(parent_statehash, statehash, bot_log_id) VALUES ( %s, %s, 
    %s ) """
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
        sql_quary = """select parent_statehash, statehash from percentile_statehash_table where bot_log_id =%s"""
        cursor.execute(sql_quary, (bot_log_id,))
        result = cursor.fetchall()

        df = pd.DataFrame(result, columns=['parent_hash', 'child_hash'])
        previous_result_dict = dict(df.values)
        p_nodes_list = [v for v in previous_result_dict.values()]
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return previous_result_dict, p_nodes_list


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


def get_batch_for_processing(prev_batch_end, cur_batch_end, conn=connection_aws):
    cursor = conn.cursor()
    try:
        sql_select = "select file_name,receivedat, blockproducerkey, nodedata_block_statehash, parent_block_statehash, " \
                     "nodedata_blockheight, nodedata_slot, file_modified_at from uptime_file_history where receivedat " \
                     "> %s and " \
                     "receivedat " \
                     "< %s  order by receivedat"

        cursor.execute(sql_select, (prev_batch_end, cur_batch_end))
        result = cursor.fetchall()
        df = pd.DataFrame(result, columns=['file_name', 'blockchain_epoch', 'block_producer_key', 'state_hash',
                                           'parent_state_hash', 'blockchain_height', 'slot', 'file_timestamps'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(ERROR.format(error))
        cursor.close()
        return -1
    finally:
        cursor.close()
    return df


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


def main():
    update_email_discord_status(connection)
    process_loop_count = 0
    prev_batch_end, cur_batch_end, bot_log_id = get_batch_timings(connection)
    cur_timestamp = datetime.now(timezone.utc)

    if BaseConfig.END_SCRIPT_EPOCH:
        cur_timestamp = datetime.fromtimestamp(BaseConfig.END_SCRIPT_EPOCH, timezone.utc)

    p_map, p_selected_node = get_previous_statehash(bot_log_id)

    do_process = True
    logger.info("script start at {0}  end at {1}".format(prev_batch_end, cur_timestamp))
    while do_process:
        existing_state_df = get_state_hash_df(connection)
        existing_nodes = get_existing_nodes(connection)
        logger.info('running for batch: {0} - {1}'.format(prev_batch_end, cur_batch_end))

        if cur_batch_end > cur_timestamp:
            logger.info('all files are processed till date')
            break
        else:
            previous_time = prev_batch_end.timestamp() * 1000
            current_time = cur_batch_end.timestamp() * 1000
            master_df = get_batch_for_processing(previous_time, current_time)
            all_file_count = master_df.shape[0]

            if all_file_count > 0:
                master_df['state_hash'] = master_df['state_hash'].apply(lambda x: x.strip())
                master_df['parent_state_hash'] = master_df['parent_state_hash'].apply(lambda x: x.strip())

                start = time()
                c_selected_node, c_map = filter_state_hash_percentile(master_df)

                graph_df = master_df[master_df['parent_state_hash'].isin(master_df['state_hash'].unique())]
                batch_graph = create_graph(graph_df, p_selected_node, c_selected_node)
                weighted_graph = apply_weights(batch_graph=batch_graph, c_selected_node=c_selected_node)
                queue_list = p_selected_node + c_selected_node

                shortlisted_state_hash = bfs(graph=weighted_graph, queue_list=queue_list, node=queue_list[0])

                point_record_df = master_df[master_df['state_hash'].isin(shortlisted_state_hash)]
                end = time()
                threads_used = 1
                logger.info('Time to validate {0} files: {1} seconds'.format(all_file_count, end - start))
                state_hash_to_insert = find_new_values_to_insert(existing_state_df,
                                                                 pd.DataFrame(shortlisted_state_hash,
                                                                              columns=['state_hash']))

                if not state_hash_to_insert.empty:
                    create_statehash(connection, state_hash_to_insert)
                try:
                    if not point_record_df.empty:
                        file_timestamp = master_df.iloc[-1]['file_timestamps']
                    else:
                        file_timestamp = cur_batch_end
                        logger.info(prev_batch_end.timestamp())
                        logger.info(cur_batch_end.timestamp())

                    values = all_file_count, file_timestamp, prev_batch_end.timestamp(), cur_batch_end.timestamp(), end - start, threads_used
                    bot_log_id = create_bot_log(connection, values)

                    p_selected_node = c_selected_node
                    p_map = c_map
                    p_selected_df = pd.DataFrame(list(p_map.items()), columns=['p', 'c'])
                    p_selected_df['bot_log_id'] = bot_log_id
                    insert_state_hash_results(p_selected_df)

                    if not point_record_df.empty:
                        nodes_in_cur_batch = point_record_df[['block_producer_key']]
                        node_to_insert = find_new_values_to_insert(existing_nodes, nodes_in_cur_batch)
                        if not node_to_insert.empty:
                            node_to_insert['updated_at'] = datetime.now(timezone.utc)
                            create_node_record(connection, node_to_insert, 100)

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