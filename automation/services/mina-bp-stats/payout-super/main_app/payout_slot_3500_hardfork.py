import hashlib
import math
import numpy as np
import pandas as pd
import psycopg2

from config import BaseConfig
from logger_util import logger

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

def read_payout_summary_for_epoch(epoch):
    query = """select provider_key, bp_key, blocks_produced, payout_amount, 
    payout_balance from payout_summary where epoch=%s;"""
    cursor = connection_payout.cursor()
    try:
        cursor.execute(query, (epoch,))
        blocks_produced_list = cursor.fetchall()
        summary_df = pd.DataFrame(blocks_produced_list,
                            columns=['provider_key', 'bp_key', 'blocks_produced', 'payout_amount', 'payout_balance'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("Error reading summary")
        cursor.close()
    return summary_df    

def read_wallet_mappings_for_epoch(epoch):
    query = """select provider_wallet_name, provider_key, return_wallet_key, bp_key, bp_email, 
     wallet0, wallet1, wallet2, wallet3, wallet4, wallet5, wallet6, wallet7, wallet8, wallet9, wallet10 
     from bp_wallet_mapping where epoch=%s;"""
    cursor = connection_payout.cursor()
    try:
        cursor.execute(query, (epoch,))
        blocks_produced_list = cursor.fetchall()
        mapping_df = pd.DataFrame(blocks_produced_list,
                            columns=['provider_wallet_name', 'provider_key', 'return_wallet_key', 'bp_key', 'bp_email', 'wallet0', 
                                     'wallet1', 'wallet2', 'wallet3', 'wallet4', 'wallet5', 'wallet6', 
                                     'wallet7', 'wallet8', 'wallet9', 'wallet10' ])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("Error reading wallet mapping")
        cursor.close()
    return mapping_df    


def get_record_for_validation(return_wallets, start_slot, end_slot):
    cursor = connection_archive.cursor()
    query = ''' WITH RECURSIVE chain AS (
    (SELECT b.id, b.state_hash,parent_id, b.creator_id,b.height,b.global_slot_since_genesis,b.global_slot_since_genesis/7140 as epoch,b.staking_epoch_data_id
    FROM blocks b WHERE height = (select MAX(height) from blocks)
    ORDER BY timestamp ASC
    LIMIT 1)
    UNION ALL
    SELECT b.id, b.state_hash,b.parent_id, b.creator_id,b.height,b.global_slot_since_genesis,b.global_slot_since_genesis/7140 as epoch,b.staking_epoch_data_id
    FROM blocks b
    INNER JOIN chain ON b.id = chain.parent_id AND chain.id <> chain.parent_id
    )
    SELECT    amount::int8/power(10,9) as total_pay, pk.value as receiver,
    epoch,global_slot_since_genesis, pk2.value as source_wallet, uc.memo
    FROM chain c INNER JOIN blocks_user_commands AS buc on c.id = buc.block_id
    inner join user_commands AS uc on uc.id = buc.user_command_id
       and uc.command_type='payment' and status <>'failed'
    INNER JOIN public_keys as PK ON PK.id = uc.receiver_id 
    INNER JOIN public_keys as PK2 ON PK2.id = uc.source_id
    where pk.value in %s and global_slot_since_genesis between %s and %s '''

    try:
        cursor.execute(query, (tuple(return_wallets), start_slot, end_slot))
        validation_record_list = cursor.fetchall()
        print("validation_record_list")
        print (len(validation_record_list))
        validation_record_df = pd.DataFrame(validation_record_list,
                                            columns=['total_pay', 'provider_pub_key', 'epoch', 'global_slot_since_genesis', 'source', 'memo'])
    except (Exception, psycopg2.DatabaseError) as error:
        logger.exception("Error reading payout transactions from Archive DB")
        #logger.error("Failed query: {0}".format(str(cursor._do)))
        cursor.close()
    print("validation_record_df")
    print(validation_record_df.shape[0])
    return validation_record_df

def determine_slot_range_for_validation(epoch_no, last_slot_validated=0):
    # find entry from summary table for matching winner+provider pub key
    # check last_delegation_epoch
    #  - when NULL           : start = epoch_no-1 * 7140, end = ((epoch_no+1)*7140) +3500
    #  - when < (epoch_no-1) : start = (last_delegation_epoch * 7140)+3500, end = ((epoch_no+1)*7140) +3500
    #  - when == epoch_no    : start = epoch * 7140, end = ((epoch+1)*7140) +3500

    # hardfork changes: Epoch number have reset to 0, and its starting with Global slot 564480
    # so simply add this to below calculations
    # then fetch the payout transactions for above period for each winner+provider pub key combination
    start_slot = ((epoch_no) * 7140) + 3500 + 564480
    end_slot = ((epoch_no + 1) * 7140) + 3500 + 564480- 1

    # update code to use simple condition
    # as the validation for received amount is done against Delegating account
    # can't use same slot duration again, even for discontinued delegation
    """ if last_slot_validated >0:
        start_slot = last_slot_validated +1
    else:
        start_slot = ((epoch_no-1) * 7140) """
    return start_slot, end_slot

def truncate(number, digits=5) -> float:
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper

def find_return_amount(payout_transactions_df, return_wallet, source_wallets):
    total_amt = 0.00000
    memo_string = ''
    payouts_df = payout_transactions_df[(payout_transactions_df['provider_pub_key']==return_wallet) & 
                                           (payout_transactions_df['source'].isin(source_wallets) ) ]
                        
    if not payouts_df.empty:
        total_amt = truncate(payouts_df.total_pay.sum(),5)
        md5s = payouts_df['memo'].unique()
        memo_string = ','.join(md5s)
   
    return total_amt, memo_string


def main(epoch):
    # get payout_summary for epoch
    # get wallet_mappings for epoch 
    # get all payment received in one_wallet_return address
    # filter payments by wallet mappings.
    # also collect MD5 hash on payments 
    start_slot, end_slot = determine_slot_range_for_validation(epoch)
    print('slot rangne: {}:{}'.format(start_slot, end_slot))
    logger.info("validation: start_slot: {0}, end_slot: {1}".format(start_slot,end_slot))
    mapping_df = read_wallet_mappings_for_epoch(epoch)
    return_wallets = mapping_df['return_wallet_key'].unique()
    #return_wallets = np.append(return_wallets, [burn_return_wallet_key])
    return_wallets = ["B62qoUVTKseKucekfhegBxuaMkoJ37ThTE12gpGWjExV4UZvhqZD6w9"]
    payout_transactions_df = get_record_for_validation(return_wallets, start_slot, end_slot)
    # creating transactions summary for debug purposes
    payout_transactions_df.to_csv('payout_transactions_df_%d.csv' %(epoch))
    summary_df = read_payout_summary_for_epoch(epoch)

    super_df = pd.merge( summary_df, mapping_df, how='left', 
                                     left_on=['provider_key','bp_key'], 
                                     right_on = ['provider_key','bp_key'], indicator=True)
    
    result = pd.DataFrame(columns=('delegating_wallet_name', 'delegating_wallet_key', 'return_wallet_key', 'bp_key', 'mds_hash', 'bp_email',
              'payout_amount', 'payout_received', 'payout_memo' ))
    
    print(list(result.columns.values))

    for index, row in super_df.iterrows():
        delegating_wallet_name = row['provider_wallet_name']
        bp_key = row['bp_key']
        mds_hash = hashlib.md5(row['bp_key'].encode('utf-8')).hexdigest()
        provider_key = row['provider_key']
        return_wallet = 'B62qoUVTKseKucekfhegBxuaMkoJ37ThTE12gpGWjExV4UZvhqZD6w9' #row['return_wallet_key']
        bp_email = row['bp_email']
        payout_amount = row['payout_amount']
        
        source_wallets = (tuple(filter(lambda x: str(x) != 'nan', row['wallet0':])))
        payout_received, payout_memo = find_return_amount(payout_transactions_df, return_wallet, source_wallets)

        result.loc[index] = [delegating_wallet_name, provider_key, return_wallet, bp_key, mds_hash, bp_email, 
                             payout_amount, payout_received, payout_memo]

    result.to_csv('validation_summary_%d.csv' %(epoch))

        
if __name__ == "__main__":
    epoch_no = main(0)