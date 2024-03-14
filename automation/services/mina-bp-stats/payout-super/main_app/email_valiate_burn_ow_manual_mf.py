import psycopg2
from datetime import timezone
import datetime
from config import BaseConfig
import pandas as pd
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
from logger_util import logger
import os
import hashlib


def send_mail(epoch_id, delegate_record_df):
    # read the data from delegation_record_table
    payouts_df = delegate_record_df
    total_minutes = (int(epoch_id+1) * 7140 * 3) + (BaseConfig.SLOT_WINDOW_VALUE * 3)
    deadline_date = BaseConfig.GENESIS_DATE + datetime.timedelta(minutes=total_minutes)
    current_date = datetime.datetime.now()
    day_count = deadline_date - current_date
    day_count = day_count.days
    deadline_date = deadline_date.strftime("%d-%m-%Y %H:%M:%S")

    print(os.getcwd())
    # reading email template
    f = open(BaseConfig.BURN_EMAIL_TEMPLATE, "r")
    html_text = f.read()
    
    print(list(payouts_df.columns.values))
    # ['delegating_wallet_key', 'return_wallet_key', 'bp_key', 'mds_hash', 'bp_email', 'payout_amount', 'payout_received', 'payout_balance', 'payout_memo', 'burn_amount', 'burn_received']
    count = 0
    #for i in range(payouts_df.shape[0]):
    for i, row in payouts_df.iterrows():    
        # 0-delegating_wallet_name	1-delegating_wallet_key	2-return_wallet	3-bpdelegationpublickey	4-bpemailaddress	
        # 5-blocks_produced	6-payout_amount	7-blocks_won	8-burn_reward
        RETURN_WALLET_ADDRESS = row['return_wallet_key'] 
        #wallet_name = payouts_df.iloc[i, 0]
        if 1==1: #if 'Treasury' in wallet_name: 
            FOUNDATION_ADDRESS = row['delegating_wallet_key'] 
            BLOCK_PRODUCER_ADDRESS = row['bp_key'] 
            PAYOUT_AMOUNT = row['payout_amount'] 
            PAYOUT_RECEIVED = row['payout_received'] 
            #PAYOUT_BALANCE = row['payout_balance']
            BP_EMAIL = row['bp_email'] 
            BURN_PAYOUT_AMOUNT = row['burn_amount'] 
            MD5_HASH = hashlib.md5(BLOCK_PRODUCER_ADDRESS.encode('utf-8')).hexdigest()
            html_content = html_text
          
            # Adding dynamic values into the template
            html_content = html_content.replace("#FOUNDATION_ADDRESS", str(FOUNDATION_ADDRESS))
            html_content = html_content.replace("#PAYOUT_AMOUNT", str(PAYOUT_AMOUNT))
            html_content = html_content.replace("#EPOCH_NO", str(epoch_id)) 
            html_content = html_content.replace("#CURRENT_EPOCH_NO", str(epoch_id+1))
            html_content = html_content.replace("#DELEGATE_ADDRESS", str(BLOCK_PRODUCER_ADDRESS))
            html_content = html_content.replace("#DEADLINE_DATE", str(deadline_date))
            html_content = html_content.replace("#DAY_COUNT", str(day_count))
            html_content = html_content.replace("#RETURN_WALLET_ADDRESS", str(RETURN_WALLET_ADDRESS))
            html_content = html_content.replace("#BURN_PAYOUT_AMOUNT", str(BURN_PAYOUT_AMOUNT))
            #html_content = html_content.replace("#BURN_PAYOUT_AMOUNT", str('0.00000'))
            html_content = html_content.replace("#BURN_WALLET_ADDRESS", 'B62qiburnzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzmp7r7UN6X')
            html_content = html_content.replace("#MD5_HASH", MD5_HASH)
            
            #URGENT: Mina Foundation Delegation Program Missing Burn Payment - Epoch (EPOCH_NO)
            subject = f"""URGENT: Mina Foundation Delegation Program Missing Burn Payment - Epoch {epoch_id}"""
            
            block_producer_email = BP_EMAIL
        
            message = Mail(from_email=BaseConfig.FROM_EMAIL,
                        to_emails=block_producer_email,
                        subject=subject,
                        plain_text_content='text',
                        html_content=html_content)
            try:
                sg = SendGridAPIClient(api_key=BaseConfig.SENDGRID_API_KEY)
                response = sg.send(message)
                logger.info('email sent to: delgate:{0}, delgatee: {1}, emailid: {2}, status {3}, messageId: {4}'.format(FOUNDATION_ADDRESS, BLOCK_PRODUCER_ADDRESS, 
                    block_producer_email, response.status_code, response.headers.get_all('X-Message-Id')))       
                count = count + 1    
            except Exception as e:
                text_file = open('summary_files/{0}.html'.format(FOUNDATION_ADDRESS), "w")
                text_file.write(html_content)
                text_file.close()
                logger.error('Error sending email: delgate:{0}, delgatee: {1}, error: {2}'.format(FOUNDATION_ADDRESS, BLOCK_PRODUCER_ADDRESS, e))
    logger.info("Calculation: epoch number: {0}, emails sent: {1}".format(epoch_id,count))

if __name__ == "__main__":
    logger.info(" starting process")
    epoch  = 71
    df = pd.read_csv('summary_files/burn_summary_{0}_1.csv'.format(epoch), index_col=0)
    send_mail(epoch, df)