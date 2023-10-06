from logging import Logger
import threading
from config import BaseConfig
from google.cloud.storage import Client as GSClient, Blob


def download_batch_into_memory(batch, bucket, inclue_metadata=True, max_threads=BaseConfig.MAX_THREADS_TO_DOWNLOAD_FILES):
    """Given a batch of storage filenames, download them into memory.

    Downloading the files in a batch is multithreaded.

    :param batch: A list of gs:// filenames to download.
    :type batch: list of str
    :param bucket: The google api pucket.
    :type bucket: google.cloud.storage.bucket.Bucket
    :param inclue_metadata: True to inclue metadata
    :type inclue_metadata: bool
    :param max_threads: Number of threads to use for downloading batch.  Don't increase this over 10.
    :type max_threads: int
    :return: Complete blob contents and metadata.
    :rtype: dict
    """

    def download_blob(blob_name, state):
        """Standalone function so that we can multithread this."""
        blob = bucket.blob(blob_name=blob_name)
        content = blob.download_as_bytes()  # json.loads(blob.download_as_string())
        state[blob_name] = content
        
    batch_data = {bn: {} for bn in batch}
    threads = []
    active_thread_count = 0
    for blobname in batch:
        thread = threading.Thread(target=download_blob, kwargs={"blob_name": blobname, "state": batch_data})
        threads.append(thread)
        thread.start()
        active_thread_count += 1
        if active_thread_count == max_threads:
            # finish up threads in batches of size max_threads.  A better implementation would be a queue
            #   from which the threads can feed, but this is good enough if the blob size is roughtly the same.
            for thread in threads:
                thread.join()
            threads = []
            active_thread_count = 0

    # wait for the last of the threads to be finished
    for thread in threads:
        thread.join()
    return batch_data

def download_batch_into_files(batch, bucket, inclue_metadata=True, 
    folder_path=BaseConfig.BLOCK_DIR, max_threads=BaseConfig.MAX_THREADS_TO_DOWNLOAD_FILES):
    """Given a batch of storage filenames, download them into memory.

    Downloading the files in a batch is multithreaded.

    :param batch: A list of gs:// filenames to download.
    :type batch: list of str
    :param bucket: The google api pucket.
    :type bucket: google.cloud.storage.bucket.Bucket
    :param inclue_metadata: True to inclue metadata
    :type inclue_metadata: bool
    :param max_threads: Number of threads to use for downloading batch.  Don't increase this over 10.
    :type max_threads: int
    :return: Complete blob contents and metadata.
    :rtype: dict
    """

    def download_blob_to_file(blob_name, state):
        """Standalone function so that we can multithread this."""
        blob = bucket.blob(blob_name=blob_name)
        if blob.exists()  : #and blob.size>0 isinstance(blob, Blob)
            destination_uri = '{}/{}'.format(folder_path, blob.name.split('/')[1])
            blob.download_to_filename(destination_uri)
            state[blob_name]=1
        else:
            Logger.warning('Block file not found: {0}'.format(blob_name))
        
    batch_data = {bn: {} for bn in batch}
    threads = []
    active_thread_count = 0
    for blobname in batch:
        thread = threading.Thread(target=download_blob_to_file, kwargs={"blob_name": blobname, "state": batch_data})
        threads.append(thread)
        thread.start()
        active_thread_count += 1
        if active_thread_count == max_threads:
            # finish up threads in batches of size max_threads.  A better implementation would be a queue
            #   from which the threads can feed, but this is good enough if the blob size is roughtly the same.
            for thread in threads:
                thread.join()
            threads = []
            active_thread_count = 0

    # wait for the last of the threads to be finished
    for thread in threads:
        thread.join()
    return batch_data

