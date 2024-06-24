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

connection_leaderboard = psycopg2.connect(
    host=BaseConfig.POSTGRES_LEADERBOARD_HOST,
    port=BaseConfig.POSTGRES_LEADERBOARD_PORT,
    database=BaseConfig.POSTGRES_LEADERBOARD_DB,
    user=BaseConfig.POSTGRES_LEADERBOARD_USER,
    password=BaseConfig.POSTGRES_LEADERBOARD_PASSWORD
)

def get_block_producer_mail(winner_bpk):
    mail_id_sql = """select email_id from nodes where block_producer_key = %s"""
    cursor = connection_leaderboard.cursor()
    email = ''
    try:
        if BaseConfig.OVERRIDE_EMAIL:
            email = BaseConfig.OVERRIDE_EMAIL
        else:
            cursor.execute(mail_id_sql, (winner_bpk,))
            if cursor.rowcount > 0:
                data = cursor.fetchall()
                email = data[-1][-1]
                if email == '':
                    logger.warning("email not found for :".format(winner_bpk))
    except (Exception, psycopg2.DatabaseError) as error:
        logger.info("Error: {0} ".format(error))
        cursor.close()
    print(email)
    return email

def send_mail(epoch_id, delegate_record_df, debug_mode=False):
    # read the data from delegation_record_table
    payouts_df = delegate_record_df
    total_minutes = (int(epoch_id+1) * 7140 * 3) + (BaseConfig.SLOT_WINDOW_VALUE * 3)
    deadline_date = BaseConfig.GENESIS_DATE + datetime.timedelta(minutes=total_minutes)
    current_date = datetime.datetime.now(datetime.timezone.utc)

    day_count = deadline_date - current_date
    day_count = day_count.days
    deadline_date = deadline_date.strftime("%d-%m-%Y %H:%M:%S")

    print(os.getcwd())
    # reading email template
    f = open(BaseConfig.CALCULATE_EMAIL_TEMPLATE, "r")
    html_text = f.read()
    
    count = 1
    for i in range(payouts_df.shape[0]):
        
        # 0-delegating_wallet_name  1-delegating_wallet_key 2-return_wallet 3-bpdelegationpublickey 4-bpemailaddress    
        # 5-blocks_produced 6-payout_amount 7-blocks_won    8-burn_reward
        RETURN_WALLET_ADDRESS = payouts_df.iloc[i, 2] 
        wallet_name = payouts_df.iloc[i, 0]
        if 1==1: #if 'Treasury' in wallet_name: 
            FOUNDATION_ADDRESS = payouts_df.iloc[i, 1]
            BLOCK_PRODUCER_ADDRESS = payouts_df.iloc[i, 3]
            PAYOUT_AMOUNT = payouts_df.iloc[i, 6] 
            PAYOUT_RECEIVED = 0.0 # payouts_df.iloc[i, 4] 
            BP_EMAIL = payouts_df.iloc[i, 4] 
            MD5_HASH = hashlib.md5(BLOCK_PRODUCER_ADDRESS.encode('utf-8')).hexdigest()
            html_content = html_text
          
            # Adding dynamic values into the template
            html_content = html_content.replace("#FOUNDATION_ADDRESS", str(FOUNDATION_ADDRESS))
            html_content = html_content.replace("#PAYOUT_AMOUNT", str(PAYOUT_AMOUNT))
            html_content = html_content.replace("#EPOCH_NO", str(epoch_id)) 
            html_content = html_content.replace("#CURRENT_EPOCH_NO", str(epoch_id+1))
            html_content = html_content.replace("#BLOCK_PRODUCER_ADDRESS", str(BLOCK_PRODUCER_ADDRESS))
            html_content = html_content.replace("#DEADLINE_DATE", str(deadline_date))
            html_content = html_content.replace("#DAY_COUNT", str(day_count))
            html_content = html_content.replace("#RETURN_WALLET_ADDRESS", str(RETURN_WALLET_ADDRESS))
            #html_content = html_content.replace("#BURN_PAYOUT_AMOUNT", str('0.00000'))
            html_content = html_content.replace("#BURN_WALLET_ADDRESS", 'B62qiburnzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzmp7r7UN6X')
            html_content = html_content.replace("#MD5_HASH", MD5_HASH)
            

            subject = f"""Delegation from {BaseConfig.ADDRESS_SUBJECT} Address {FOUNDATION_ADDRESS[:7]}...{FOUNDATION_ADDRESS[-4:]} Send Block Rewards in MINA for Epoch {epoch_id}"""
            #block_producer_email = get_block_producer_mail(BLOCK_PRODUCER_ADDRESS)
            block_producer_email = BP_EMAIL
            #block_producer_email = ['David.sedgwick@minaprotocol.com', 'umesh@ontab.com']
            if debug_mode:
                block_producer_email = ['test@email.com']
        
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
            if debug_mode:
                break
    logger.info("Calculation: epoch number: {0}, emails sent: {1}".format(epoch_id,count))

if __name__ == "__main__":
    logger.info(" starting process")
    epoch  = 0
    debug_mode = True
    #debug_mode = False
    df = pd.read_csv('summary_files/obligation_summary_{0}.csv'.format(epoch), index_col=0)
    send_mail(epoch, df, debug_mode)
