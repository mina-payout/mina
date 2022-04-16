import os
from config import BaseConfig
import threading
from logger_util import logger
import subprocess
import json
import pandas as pd
import traceback

ERROR = 'Error: {0}'


def get_validate_state_hash(batch_file_list, combine_list):
    file_list = []
    for file in batch_file_list:
        file_name = os.path.join(f'{BaseConfig.SUBMISSION_DIR}', file)
        file_list.append(file_name)
    file_names = ' '.join(file_list)

    cmd_string1 = f'docker run --cpus={BaseConfig.MAX_CPU_PER_INNSTANCE} -v {BaseConfig.ROOT_DIR}:{BaseConfig.ROOT_DIR} ' \
                  f'gcr.io/o1labs-192920/delegation-verify:1.2.3-mainnet --block-dir {BaseConfig.BLOCK_DIR} '

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
            traceback.print_exc()
    # append the result to master list
    combine_list.append(output_list)


def processing_batch_files(batch_list, max_threads=BaseConfig.MAX_VERIFIER_INSTANCES):
    # comment - batch_list ( number of files in 20-min time window )
    # comment - max_threads (number of docker instances run parallel at once's)
    # comment - create number of  mini_batches based on max_threads value
    active_thread_count = 0
    threads = []
    # clean up all existed docker contianers
    ps = subprocess.Popen(['docker container prune -f'], stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True)
    if len(batch_list) <= max_threads*2:
        # run only 1 instance if batch size is less than 10
        max_threads = 1
          
    # divide the batch_list into mini_batches based on max_threads ie no. mini batches = max_threads
    mini_batches = [batch_list[i::max_threads] for i in range(max_threads)]
    logger.info('using {0} threads for parallel verification'.format(max_threads))
    master_list = list()
    for batch in mini_batches:
        thread = threading.Thread(target=get_validate_state_hash,
                                  kwargs={"batch_file_list": batch, "combine_list": master_list})
        threads.append(thread)
        thread.start()
        active_thread_count += 1
        if active_thread_count == max_threads:
            for thread in threads:
                thread.join()
            threads = []
            active_thread_count = 0

    for thread in threads:
        thread.join()

    # combining the results of each batch and generating the dataframe
    flat_list = [item for sublist in master_list for item in sublist]
    df = pd.DataFrame(flat_list)

    return df, max_threads

