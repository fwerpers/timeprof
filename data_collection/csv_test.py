import csv
from tempfile import NamedTemporaryFile
import shutil
from datetime import timedelta
from datetime import datetime
import argparse

CSV_PATH = "data/@fwerpers:matrix.org.csv"
tempfile = NamedTemporaryFile(mode='w', delete=False)
LINE_NUMBER = 2302

def get_csv_context(csv_path, line_number, size):
    with open(csv_path, 'r') as f:
        reader = csv.reader(f, delimiter=',')
        n_row = sum(1 for row in reader)
        collected_rows = []
        start_i = min(n_row-size, line_number - size/2)
        end_i = start_i + size
        i = 1
        f.seek(0)
        for row in reader:
            row = [str(i)] + row
            if start_i <= i <= end_i:
                collected_rows.append(row)
            i += 1
        return collected_rows

def get_last_csv_context(csv_path, size):
    with open(csv_path, 'r') as f:
        reader = csv.reader(f, delimiter=',')
        n_row = sum(1 for row in reader)
        rows = get_csv_context(csv_path, n_row, size)
        return rows

def get_csv_context_timedelta(csv_path, timestamp=datetime.now(), timedelta=timedelta(days=1)):
    with open(csv_path, 'r') as f:
        reader = csv.reader(f, delimiter=',')
        n_row = sum(1 for row in reader)
        collected_rows = []
        now = datetime.now()
        start_time = min(now-timedelta, timestamp - timedelta/2)
        end_time = start_time + timedelta
        f.seek(0)
        i = 1
        for row in reader:
            time = datetime.fromisoformat(row[0])
            row = [str(i)] + row
            if start_time <= time <= end_time:
                collected_rows.append(row)
            i += 1
        return collected_rows

def modify_line(csv_path, line_number, new_tag):
    with open(csv_path, 'r') as csvfile, tempfile:
        reader = csv.reader(csvfile, delimiter=',')
        writer = csv.writer(tempfile, delimiter=',')
        i = 1
        for row in reader:
            if i == line_number:
                row[1] = new_tag
            writer.writerow(row)
            i += 1
        shutil.move(tempfile.name, CSV_PATH)

def batch_modify_lines(start_i, end_i, new_tag):
    with open(filename, 'r') as csvfile, tempfile:
        reader = csv.reader(csvfile, delimiter=',')
        writer = csv.writer(tempfile, delimiter=',')
        i = 1
        for row in reader:
            if start_i <= i <= end_i:
                row[1] = new_tag
            writer.writerow(row)
            i += 1
        shutil.move(tempfile.name, filename)

def main_history():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", dest="line", type=int)
    parser.add_argument("-n", dest="size", type=int, default=10)
    args = parser.parse_args()
    if not args.line:
        rows = get_last_csv_context(CSV_PATH, args.size)
    else:
        rows = get_csv_context(CSV_PATH, args.line, args.size)
    #rows = [','.join(row) for row in rows]
    #response = "\n".join(rows)
    #print(response)
    for row in rows:
        print(','.join(row))

def main_edit():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", dest="line", type=int, required=True)
    parser.add_argument("label")
    args = parser.parse_args()
    modify_line(CSV_PATH, args.line, args.label)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", type=int)
    parser.add_argument("-n", type=int, default=10)
    args = parser.parse_args()
    #rows = get_csv_context(CSV_PATH, LINE_NUMBER, 10)
    #for row in rows:
        #print(row)
    #modify_line(CSV_PATH, LINE_NUMBER, "kallehej")
    #rows = get_csv_context(CSV_PATH, LINE_NUMBER, 10)
    #for row in rows:
        #print(row)
    #last_context = get_last_csv_context(CSV_PATH, 10)
    #for row in last_context:
        #print(row)
    #last_context_timedelta = get_last_csv_context_timedelta(CSV_PATH)
    #for row in last_context_timedelta:
        #print(row)
    #last_context_timedelta = get_csv_context_timedelta(CSV_PATH)
    #for row in last_context_timedelta:
        #print(row)

if __name__ == "__main__":
    #main()
    main_history()
    #main_edit()
