import pandas as pd
import os
import json
import math
import psycopg2
import requests as rs
import numpy as np
import io
import ijson

from pandas import json_normalize
from timeit import default_timer as timer
from config import BaseConfig
from logger_util import logger
from google.cloud import storage
from itertools import groupby
from psycopg2 import extras
from io import StringIO


connection_archive = psycopg2.connect(
    host=BaseConfig.POSTGRES_ARCHIVE_HOST,
    port=BaseConfig.POSTGRES_ARCHIVE_PORT,
    database=BaseConfig.POSTGRES_ARCHIVE_DB,
    user=BaseConfig.POSTGRES_ARCHIVE_USER,
    password=BaseConfig.POSTGRES_ARCHIVE_PASSWORD
)
connection_payout = psycopg2.connect(
    host=BaseConfig.POSTGRES_PAYOUT_HOST,
    port=BaseConfig.POSTGRES_PAYOUT_PORT,
    database=BaseConfig.POSTGRES_PAYOUT_DB,
    user=BaseConfig.POSTGRES_PAYOUT_USER,
    password=BaseConfig.POSTGRES_PAYOUT_PASSWORD
)


def get_all_blocks_produced_for_epoch(start_slot, end_slot):
    # calculate blocks produced by delegate
    query = '''WITH RECURSIVE chain AS (
    (SELECT b.id, b.state_hash,parent_id, b.creator_id,b.height,b.global_slot_since_genesis/7140 AS epoch,b.global_slot_since_genesis 
        FROM blocks b WHERE height = (select MAX(height) from blocks)
        ORDER BY timestamp ASC
        LIMIT 1)
    UNION ALL
    SELECT b.id, b.state_hash,b.parent_id, b.creator_id,b.height,b.global_slot_since_genesis/7140 AS epoch,
        b.global_slot_since_genesis FROM blocks b INNER JOIN chain
            ON b.id = chain.parent_id AND chain.id <> chain.parent_id
    ) SELECT count(distinct c.id) as blocks_produced, pk.value as creator
    FROM chain c INNER JOIN blocks_internal_commands bic  on c.id = bic.block_id
    INNER JOIN public_keys pk ON pk.id = c.creator_id
    WHERE global_slot_since_genesis between %s and %s 
    GROUP BY pk.value;
    '''
    cursor = connection_archive.cursor()
    try:
        cursor.execute(query, (start_slot, end_slot))
        blocks_produced_list = cursor.fetchall()
        df = pd.DataFrame(blocks_produced_list,
                                            columns=['blocks_produced', 'creator'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("get_all_blocks_produced_for_epoch")
        cursor.close()
    return df    

def insert_into_staking_ledger(modified_staking_df, epoch_no):
    tmp = modified_staking_df[['pk', 'balance','delegate']].copy()
    tmp['epoch_number']= epoch_no
    tuples = [tuple(x) for x in tmp.to_numpy()]
    query = '''INSERT INTO  staking_ledger (provider_key, balance, bp_key, epoch) 
                VALUES ( %s, %s, %s, %s) 
                ON CONFLICT (provider_key, bp_key, epoch)  DO NOTHING '''
    result = 0
    try:
        cursor = connection_payout.cursor()
        extras.execute_batch(cursor, query, tuples, 100)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception('failed to insert_into_staking_ledger')
        connection_payout.rollback()
        cursor.close()
        result = -1
    finally:
        cursor.close()
        connection_payout.commit()
    return result


def insert_into_wallet_mapping(wallet_mapping_df):
    #wallet_mapping_df['epoch'] = epoch_no
    tuples = [tuple(x) for x in wallet_mapping_df.to_numpy()]
    query = '''INSERT INTO public.bp_wallet_mapping (provider_wallet_name, provider_key, return_wallet_key, bp_key, bp_email, 
     wallet0, wallet1, wallet2, wallet3, wallet4, wallet5, wallet6, wallet7, wallet8, wallet9, wallet10, epoch)
    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
    ON CONFLICT (provider_key, epoch)  DO NOTHING '''
    result = 0
    try:
        cursor = connection_payout.cursor()
        extras.execute_batch(cursor, query, tuples, 100)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("error while saving to wallet_mapping")
        cursor.close()
        connection_payout.rollback()
        result = -1
    finally:
        cursor.close()
        connection_payout.commit()
    return result

def save_payout_summary(df, epoch, page_size=100):
    tmp_df = df[['delegating_wallet_key','bpdelegationpublickey', 'blocks_produced', 'payout_amount']].copy()
    tmp_df['payout_balance'] = 0
    tmp_df['burn_balance'] = 0
    tmp_df['epoch'] = epoch
    
    #tmp_df = tmp_df.drop(['delegating_wallet_name','return_wallet', 'bpemailaddress'], axis=1, inplace=True)
    tuples = [tuple(x) for x in tmp_df.to_numpy()]
    query = '''INSERT INTO  payout_summary (provider_key, bp_key, blocks_produced, payout_amount, 
     payout_balance, burn_balance, epoch) 
            VALUES (%s, %s, %s, %s, %s, %s, %s) 
      ON CONFLICT (provider_key, bp_key, epoch) 
      DO UPDATE SET payout_amount = EXCLUDED.payout_amount , 
        blocks_produced=EXCLUDED.blocks_produced
      '''
    #DO UPDATE SET payout_amount = payout_summary.payout_amount + EXCLUDED.payout_amount
    result = 0
    try:
        cursor = connection_payout.cursor()
        extras.execute_batch(cursor, query, tuples, page_size)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception('Error in save_payout_summary')
        connection_payout.rollback()
        cursor.close()
        result = -1
    finally:
        cursor.close()
        connection_payout.commit()
    return result

def read_mf_delegating_wallets():
    query = '''select info, address from mf_wallets where info like '%Grants' or info like '%Treasury' '''   
    cursor = connection_payout.cursor()
    try:
        cursor.execute(query)
        mf_wallets = cursor.fetchall()
        df_mf_wallets = pd.DataFrame(mf_wallets, columns=['info', 'address'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("error while getting blocks won")
        cursor.close()
    return df_mf_wallets   

def get_blocks_produced_by_bp(all_blocks_produced_df, delegate_bpk):
    blocks_produced = 0
    current_acc_df = all_blocks_produced_df.query('creator==@delegate_bpk')

    if not current_acc_df.empty:
        blocks_produced = current_acc_df.iloc[0]['blocks_produced']
    return blocks_produced

def get_blocks_won_by_provider(all_blocks_won_df, provider_key):
    blocks_won = 0
    current_acc_df = all_blocks_won_df.query('winner==@provider_key')

    if not current_acc_df.empty:
        blocks_won = current_acc_df.iloc[0]['blocks_produced']
    return blocks_won

def truncate(number, digits=5) -> float:
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper

def get_gcs_client():
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = BaseConfig.CREDENTIAL_PATH
    return storage.Client()

def read_staking_json_list_fixed(staking_file_prefix):
    storage_client = get_gcs_client()
    bucket = storage_client.get_bucket(BaseConfig.GCS_BUCKET_NAME)
    blobs = storage_client.list_blobs(bucket, prefix=staking_file_prefix)
    file_dict_for_memory = dict()
    for blob in blobs:
        file_dict_for_memory[blob.name] = blob.updated
    sorted_list = sorted(file_dict_for_memory.items(), key=lambda p: p[1], reverse=True)
    most_recent_file = sorted_list[0][0]
    return most_recent_file


def read_staking_json_for_epoch(epoch_id):
    storage_client = get_gcs_client()
    bucket = storage_client.get_bucket(BaseConfig.GCS_BUCKET_NAME)
    
    staking_file_prefix = "staking-" + str(epoch_id)+"-"
    blobs = storage_client.list_blobs(bucket, prefix=staking_file_prefix)
    # convert to string
    ledger_name = ''
    modified_staking_df = pd.DataFrame()
    file_to_read = read_staking_json_list_fixed(staking_file_prefix) 
    for blob in blobs:
        logger.info(blob.name)
        if blob.name in file_to_read:
            #logger.info(blob.name)
            ledger_name = blob.name
            json_data_string = blob.download_as_string()
            json_data_dict = json.loads(json_data_string)
            modified_staking_df = json_normalize(json_data_dict)
    return modified_staking_df, ledger_name


def read_foundation_accounts():
    foundation_account_df = pd.read_csv(BaseConfig.DELEGATION_ADDRESSS_CSV, header=None)
    foundation_account_df.columns = ['pk']
    return foundation_account_df

def calculate_supercharged_block_rewads(blocks_produced, total_stake_to_bp, mf_delegation_amount):
    # provider share
    provider_share = mf_delegation_amount / total_stake_to_bp
    # payout
    return truncate((provider_share * 0.92) * BaseConfig.COINBASE * blocks_produced,  5)


def read_wallet_mapping_spreadsheet(epoch_no):
    sheet_url = "{}?output=csv&key={}".format(BaseConfig.ONE_WALLET_SHEET_PATH, BaseConfig.ONE_WALLET_SHEET_NAME)
    
    bytes_data = rs.get(sheet_url)
 
    s=str(bytes_data.content,'utf-8')
    data = StringIO(s) 
    ### Read csv
    column_names = ['delegating_wallet_name', 'delegating_wallet_key', 'return_wallet', 'bpdelegationpublickey', 
             'bpemailaddress', 'wallet0', 'wallet1', 'wallet2', 'wallet3', 'wallet4', 'wallet5', 'wallet6',
               'wallet7', 'wallet8', 'wallet9', 'wallet10' ]
    df = pd.read_csv(data, names=column_names, header=0, delimiter=",") 
    df = df.replace({np.nan:None})
    df['epoch']=epoch_no

    logger.info("connected to BP-Wallet-Mapping excel")
    return df


def determine_slot_range_for_calculation(epoch_no):
    # Since Epoch 0, after hardfork, started at 564480 Global Slot since Genesis,
    # calculate slot for range normally and add 564480 to that.
    
    start_slot = ((epoch_no) * 7140) + 564480
    end_slot = ((epoch_no+1) * 7140) + 564480 - 1
    
    return start_slot, end_slot

def main(epoch):
    start_slot, end_slot = determine_slot_range_for_calculation(epoch)
    print('slot rangne: {}:{}'.format(start_slot, end_slot))
    t = timer()
    all_blocks_produced_df = get_all_blocks_produced_for_epoch(start_slot, end_slot)
    print( timer() - t)
    
    
    
    t = timer()
    staking_ledger_df, ledger_name = read_staking_json_for_epoch(epoch)
    staking_ledger_df["balance"] = pd.to_numeric(staking_ledger_df["balance"])
    print( timer() - t)
    
    wallet_mapping_df = read_wallet_mapping_spreadsheet(epoch)
    
    df_mf_wallets = read_mf_delegating_wallets()
    
    result = pd.DataFrame(columns=('delegating_wallet_name', 'delegating_wallet_key', 'return_wallet', 'bpdelegationpublickey', 
             'bpemailaddress', 'blocks_produced', 'payout_amount')) 

    for index, row in df_mf_wallets.iterrows():
        total_stake_to_bp=0.0
        block_reward=0.0
 
        bp_produced=0
        provider_key = row['address']
        try:
            bp_key = staking_ledger_df.query('pk in @provider_key')['delegate'].values[0]
            bp_email = wallet_mapping_df.query('bpdelegationpublickey == @bp_key')['bpemailaddress'].values[0]
            provider_delegation_amount = staking_ledger_df.query('pk in @provider_key')['balance'].values[0]

            delegation_df = staking_ledger_df.query('delegate == @bp_key')
            total_stake_to_bp = delegation_df['balance'].sum()
            bp_produced = get_blocks_produced_by_bp(all_blocks_produced_df, bp_key)
            block_reward = calculate_supercharged_block_rewads(bp_produced, total_stake_to_bp, provider_delegation_amount)
            
            result.loc[index] = [row['info'], provider_key, 'B62qoUVTKseKucekfhegBxuaMkoJ37ThTE12gpGWjExV4UZvhqZD6w9', bp_key,
                                bp_email, bp_produced, block_reward]
        except (Exception, psycopg2.DatabaseError) as error:
            logger.exception("error in calculation")
            logger.info(provider_key, 'B62qoUVTKseKucekfhegBxuaMkoJ37ThTE12gpGWjExV4UZvhqZD6w9', bp_key,
                                bp_email, bp_produced)
        
    result.to_csv('obligation_summary_%d.csv' %(epoch))
    save_payout_summary(result, epoch)
    insert_into_wallet_mapping(wallet_mapping_df)

    t = timer()
    insert_into_staking_ledger(staking_ledger_df, epoch)
    print( timer() - t)
    
if __name__ == "__main__":
    epoch_no = main(0)
      