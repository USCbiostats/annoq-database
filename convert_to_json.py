'''
usage: convert_to_json.py <gzfile>.gz [folder]

it will convert gz file into multiple json files and put them in ./json/[folder/]<gzfile>/1 ./json/[folder/]<gzfile>/2...

'''
import fileinput
import pickle
from utils import id_gen
import sys
import time
import gzip
import os
import shutil
import json
import shutil


in_folder = sys.argv[1]
if len(sys.argv) > 2:
    out_folder = sys.argv[2] + '/'
else:
    out_folder = ''

work_directory = 'temp_work'

def init_find_error():
    err_file = open("log_import_error", "w")

    def t(da):
        for i in da:
            err_file.write(str(i) + "\n")
    return t


find_error = init_find_error()
start_time = time.time()


def tmp_print(*argv):
    s = ' '.join((str(i) for i in argv))
    print('\b'*tmp_print.l + ' '*tmp_print.l, end='\r', flush=True)
    print(s, end='', flush=True)
    tmp_print.l = len(s)


tmp_print.l = 0


def parse_line(l, data_parser, header):
    line = l.rstrip().split("\t")
    d = {}
    for idx in range(len(header)):
        if line[idx] == ".":
            continue
        k = header[idx]
        try:
            d[k] = data_parser.get(k, str)(line[idx])
        except:
            print('parse error:', k, line[idx], data_parser.get(k, str))
            d[k] = str(line[idx])
    return d


def write_data(f, da):
    json.dump(da, f)
    f.close()


def create_working_dir(directory):
    try:
        os.mkdir(directory)
        print(directory+ "(temp work directory) created\n")
    except:
        print('json path exists\n')


def delete_working_dir(directory):
    try:
        shutil.rmtree(directory)
        print(directory+"(temp work directory) removed\n")
    except:
        print('folder not removed\n')


def convert_file(in_filename, work_dir=work_directory):   
    with open('data/doc_type.pkl', 'rb') as data:
        dtype = pickle.load(data)

    data_parser = {}
    for k in dtype:
        data_parser[k] = eval(dtype[k])
    data_parser['chr'] = str
    data_parser['GWAS_catalog_pubmedid'] = str
    data_parser['GRASP_PMID'] = str

    error = open("error.log", "w")
    count = 0
    header = ''
    da_list = []
    out_path = './' + work_directory+ '/' + out_folder + \
        in_filename.split('/')[-1].split('.')[0] + '/'
    os.makedirs(out_path, exist_ok=True)

    f = gzip.open(in_filename, mode='rb')
    out_file_name = '1'

    for i in f:
        i = i.decode()
        count += 1
        if not header:
            header = i.rstrip().split("\t")
            continue
        data = {
            "_index": "vs-index",
            "_id": id_gen(i),
            "_source": parse_line(i, data_parser, header)
        }
        try:
            data = {
                "_index": "vs-index",
                "_id": id_gen(i),
                "_source": parse_line(i, data_parser, header)
            }
            da_list.append(data)
        except:
            error.write(i)
        if count % 50000 == 0:
            write_data(open(out_path + out_file_name + '.json', 'w'), da_list)
            out_file_name = str(int(out_file_name) + 1)
            da_list = []
            tmp_print("import {}".format(count), "spend time:",
                      time.time() - start_time, "s")
    write_data(open(out_path + out_file_name + '.json', 'w'), da_list)
    print("")
    print("import record ", count)
    print("used time", time.time() - start_time, "s")


if __name__=='__main__':
    create_working_dir(work_directory)
    for root, dirs, files in os.walk(in_folder, topdown=False):
        for name in files:
            if name.endswith('.gz'):
                filepath = os.path.join(root, name)
                print(filepath)
                convert_file(filepath)
                print("finished ", filepath, time.time() - start_time, "s")
              
    print("")
    print("used time", time.time() - start_time, "s")