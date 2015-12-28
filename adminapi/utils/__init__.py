from __future__ import print_function
import sys
from itertools import izip

def log2(x):
    i = -1
    while x:
        x >>= 1
        i += 1
    return i

def print_table(input_table_rows, max_col_len=40, file=sys.stdout):
    if not input_table_rows:
        return

    # Format objects for table display
    table_rows = []
    for row in input_table_rows:
        cols = []
        for col in row:
            formatted_obj = format_obj(col)
            if len(formatted_obj) > max_col_len - 4:
                cols.append(formatted_obj[0:max_col_len] + u' ...')
            else:
                cols.append(formatted_obj)
        table_rows.append(cols)

    # Get maximal length for all columns
    column_lens = [0] * len(table_rows[0])
    for row in table_rows:
        for col_no, col in enumerate(row):
            column_lens[col_no] = max(column_lens[col_no], len(col))

    sep = '+-{0}-+'.format('-+-'.join('-' * col_len for col_len in column_lens))
    print(sep, file=file)
    for row_no, row in enumerate(table_rows):
        if row_no == 1:
            print(sep, file=file)
        table_line = '| {0} |'.format(' | '.join(col.ljust(col_len)
            for col, col_len in izip(row, column_lens)))
        print(table_line, file=file)
    print(sep, file=file)

def format_obj(obj):
    if isinstance(obj, basestring):
        return obj
    elif hasattr(obj, '__iter__'):
        return ', '.join(sorted(unicode(x) for x in obj))
    else:
        return unicode(obj)

def print_heading(heading, char='-', file=sys.stdout):
    print('{0}\n{1}\n'.format(heading, char * len(heading)), file=file)
