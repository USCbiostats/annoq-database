import load_env
import time
from elasticsearch import helpers
from elasticsearch.helpers import BulkIndexError
import ijson
import os
import sys
import pprint
from src.config.settings import settings
from src.config.es import es
#run python3 index_es_json -m test_input_json

import logging

logging.basicConfig(
    handlers=[logging.FileHandler('logfile.log', 'w', 'utf-8')],
    format='%(levelname)s: %(message)s',
    datefmt='%m-%d %H:%M',
    level=logging.INFO #CRITICAL ERROR WARNING  INFO    DEBUG    NOTSET 
)

def load_json(directory):
    start_time = time.time()
    for root, dirs, files in os.walk(directory, topdown=True):
        # Sort the directory names
        dirs.sort() 
        # Sort the files list in place
        files.sort()
        for name in files:
            if name.endswith('.json'):
                print(os.path.join(root, name))
                print("- %s seconds ---" % (time.time() - start_time))
                with open(os.path.join(root, name), 'r') as open_file:
                    parser = ijson.parse(open_file)
                    for value in ijson.items(parser, 'item'):
                        yield value

def bulk_load_parallel(directory):

    for success, info in helpers.parallel_bulk(es, load_json(directory), index=settings.ANNOQ_ANNOTATIONS_INDEX, thread_count=5, chunk_size=2000, max_retries=10, request_timeout=50, queue_size=10):
        if not success:
            logging.error('A document failed:', info)


def bulk_load(directory):
   
    helpers.bulk(es, load_json(directory), index=settings.ANNOQ_ANNOTATIONS_INDEX, chunk_size=10000, request_timeout=1000)
 

def bulk_load_streaming(directory):
    try:
        for success, info in helpers.streaming_bulk(es, load_json(directory), index=settings.ANNOQ_ANNOTATIONS_INDEX, chunk_size=5000, request_timeout=1000):
        # May need to update chunk size for larger number of columns
        # for success, info in helpers.streaming_bulk(es, load_json(directory), index=settings.ANNOQ_ANNOTATIONS_INDEX, chunk_size=50, request_timeout=1000):        
            if not success:
                logging.error('A document failed:', info)
            #else:
                #print(f"Document successfully indexed: {info}")

    except BulkIndexError as e:
        # This block catches errors where specific documents in a chunk failed indexing
        print(f"A BulkIndexError occurred: {e.errors}")
        # You can process e.errors to see the specific failures

    except Exception as e:
        # This block catches other potential exceptions, e.g., connection issues,
        # network timeouts, or other general API errors.
        print(f"An unexpected error occurred during bulk indexing: {e}")

    else:
        # This block executes if no exceptions were raised during the entire iteration
        print("All documents processed successfully without any exceptions.")


if __name__ == "__main__": 
    in_folder = sys.argv[1]
    bulk_load_streaming(in_folder)


#python3 -m src.index_es_json ../../annoq-output/HRC_03_07_19/batch2/
# python3 -m src.index_es_json ../../../annoq/batch1/
