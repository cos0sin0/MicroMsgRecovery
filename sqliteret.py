# -*- coding:utf-8 -*-
#!/usr/bin/env python3
#
# Copyright (C) 2014 by A.D. <adotddot1123@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


import sqlite3
import struct
import itertools
import binascii
import time
import argparse
import sys
import csv
from collections import defaultdict
import re
zhPattern = re.compile(u'[\u4e00-\u9fa5]+')

global_data_sets = [['id','message']]
global_undelete_data = []
global_count = 0

def p(f):
    print('%s.%s(): %s' % (f.__module__, f.__name__, f()))

def write():
    with open('msg.csv','a',encoding='utf8') as out:
        csv_write = csv.writer(out)
        csv_write.writerows(global_data_sets)

def write_data(data):
    with open('deleted.csv','a',encoding='utf8') as out:
        csv_write = csv.writer(out)
        csv_write.writerows(data)

p(sys.getdefaultencoding)

class NullWriter:
    '''Disable print in non-verbose mode'''
    def write(self, stream):
        pass


class VarintReader:
    '''Functions for extracting varints'''
    def __init__(self, fileobj):
        self.file = fileobj

                     
    def varint_from_file(self):
        '''Reads a single varint from a given file; it expects the cursor to be already at the start of the varint'''

        #This algorithm follows the description of SQLite documentation on varints

        #Treat each byte of the encoding as an unsigned integer between 0 and 255. Let the bytes of the encoding be called A0, A1, A2, ..., A8.             
        a0 = struct.unpack('>B', self.file.read(1))[0]
            
        #If A0 is between 0 and 240 inclusive, then the result is the value of A0.
        if a0 <= 240: return a0

        #If A0 is between 241 and 248 inclusive, then the result is 240+256*(A0-241)+A1.
        elif a0 >=241 and a0 <=248:
            a1 = struct.unpack('>B', self.file.read(1))[0]
            return 240+256*(a0-241)+a1

        #If A0 is 249 then the result is 2288+256*A1+A2.
        elif a0 == 249:
            a1, a2 = struct.unpack('>2B', self.file.read(2))
            return 2288 + 256*a1+a2

        #If A0 is 250 then the result is A1..A3 as a 3-byte big-ending integer.
        elif a0 == 250:
            #struct cannot unpack 3 bytes: add a null-byte padding at the beginning and unpack it as a 4-bytes int 
            return struct.unpack('>I', b'\x00'+self.file.read(3))[0]

        #If A0 is 251 then the result is A1..A4 as a 4-byte big-ending integer.
        elif a0 == 251:
            return struct.unpack('>I', self.file.read(4))[0]
            
        #If A0 is 252 then the result is A1..A5 as a 5-byte big-ending integer.
        elif a0 == 252:
            #unpack as an 8-bytes int
            return struct.unpack('>Q', b'\x00\x00\x00'+self.file.read(5))[0]
                
        #If A0 is 253 then the result is A1..A6 as a 6-byte big-ending integer.
        elif a0 == 253:
            return struct.unpack('>Q', b'\x00\x00'+self.file.read(6))[0]

        #If A0 is 254 then the result is A1..A7 as a 7-byte big-ending integer.
        elif a0 == 254:
            return struct.unpack('>Q', b'\x00'+self.file.read(7))[0]

        #If A0 is 255 then the result is A1..A8 as a 8-byte big-ending integer.
        elif a0 == 255:
            return struct.unpack('>Q', self.file.read(8))[0]

    def varint_integer(self):
        '''Reads a single varint from a given file; it expects the cursor to be already at the start of the varint'''

        # This algorithm follows the description of SQLite documentation on varints

        # Treat each byte of the encoding as an unsigned integer between 0 and 255. Let the bytes of the encoding be called A0, A1, A2, ..., A8.
        tmp = self.file.read(1)
        a0 = struct.unpack('>B', tmp)[0]
        #print('current byte:',tmp)
        #print('byte to integer:',a0)
        # If A0 is between 0 and 240 inclusive, then the result is the value of A0.
        if a0 <= 127:
            return a0

        a1 = struct.unpack('>B', self.file.read(1))[0]

        if a1 <=127:
            return a1 + (a0-128)*128

        a2 = struct.unpack('>B', self.file.read(1))[0]

        if a2<=127:
            return a2 + (a1-128*128)*128*128+(a0-128)*128

        return None




    def n_varints_file(self, n):
        '''Read a specified number of varints from a given file; the cursor on the file must be already in place'''
        return [self.varint_from_file() for i in range(n)]


###############################################################################################################################################


class DBSchema:
    '''Interactions with the database tables, validation of data according to the tables'''

    def __init__(self, dbpath):
        #connect to database
        self.cur = sqlite3.connect(dbpath).cursor()
        #get schema of the database
        self.schema = self.get_schema()
        #description of the tables
        self.tables = self.table_info(self.schema)
        #visible records in the tables
        self.cells = self.table_cells(self.tables)
        global_undelete_data.extend(self.cells[21])
        #disconnect
        self.cur.connection.close()


    def get_schema(self):
        '''Returns the sqlite_master table of the database'''

        return self.cur.execute('SELECT * FROM sqlite_master WHERE type="table"').fetchall()


    def table_info(self, schema):
        '''Returns a detailed description of each table'''

        tables = {}        
        for row in schema:
            if row[0] == 'table':
                try:
                    current_tbl_name, current_tbl_root = row[2], row[3]
                    #gets a list of one description tuple for each column
                    #the tuple values are: cid|name|type|notnull|dflt_value|pk
                    current_tbl_desc = self.cur.execute('PRAGMA table_info('+current_tbl_name+')').fetchall()
                    tables[current_tbl_root] = (current_tbl_name, current_tbl_desc)
                except Exception as ex:
                    print(ex)

        #the key-value pairs of the dictionary tables follow the structure:
        #root number:(table name, [(cid1, name1, type1, notnull1, dftl1, pk1), ..., (cidN, nameN, typeN, notnullN, dfltN, pkN)]
        print(tables)
        tables = {21: ('FTS5IndexMessage_content', [(0, 'id', 'INTEGER', 0, None, 1), (1, 'c0', 'TEXT', 0, None, 0)])}
        return tables


    def table_cells(self, tables):
        '''Returns the non-deleted records for each table'''

        cells = {}
        for root_no in tables:
            cells[root_no]=self.cur.execute('SELECT * FROM '+tables[root_no][0]).fetchall()
            
        #the key-values pairs of the dictionary cells follow the structure:
        #root number: list of rows
        return cells


    def data_check(self, piece):
        '''Validates pieces of string data'''

        #validations are made on string and blob types, which are extracted as bytes
        if isinstance(piece, bytes):
            #do not return strings which contain non-printable characters
            for charint in piece:
                if charint > 160 or (charint < 31 and charint != 9):
                    return False
            #also, do not return blobs which are strings of only 0s.
            if all([x==48 for x in piece]): return False

        return True


    def validate_serials(self, serials, tbl_desc, skip, nostrict):
        '''Confronts an iterable of serial type varints with the table schema to see if they corrispond'''

        for i in range(len(serials)):

            #first associate the serial number with the corresponding column
            serial = serials[i]
            col_desc = tbl_desc[i+skip]            

            #check the type of the column and if notnull is set
            col_type = col_desc[2].lower()
            col_notnull = col_desc[3]

            #get the column affinity
            col_affinity = self.get_col_aff(col_type)

            #in non-strict mode, the function follows sqlite's documentations guidelines about data types
            #possibly stored by columns with certain affinities; this makes the check much less strict
            #as it is possible to find more data types per affinity 
            if True:
                    
                if serial == 0 and not col_notnull: continue

                #integer-, real- and numeric-affinity columns can store data in any possible way
                elif col_affinity in ['INTEGER', 'NUMERIC', 'REAL', 'NONE'] and serial < 12: continue

                #text- and none-affinity columns can store strings and blob
                elif col_affinity == 'NONE' and serial >= 12: continue

                elif col_affinity == 'TEXT' and serial >= 13: continue

                else: return False

            #in strict mode, the function assumes a reasonable use of the column types;
            #that is, it assumes that columns with INTEGER, REAL and NUMERIC affinity
            #actually store numbers, TEXT stores strings, and NONE stores blob;
            else:

                #data can only be null if NOT NULL is not set
                if serial == 0 and not col_notnull: continue
                
                elif col_affinity == 'INTEGER' and serial in [1, 2, 3, 4, 5, 6, 8, 9]: continue

                #the validation for real includes the serial types for integer types smaller than 8 bytes because in certain cases
                #the floating point number can be converted to integer
                elif col_affinity == 'REAL' and serial in [1, 2, 3, 4, 5, 7, 8, 9]:continue

                elif col_affinity == 'NUMERIC' and serial in [1, 2, 3, 4, 5, 6, 7, 8, 9]: continue

                elif col_affinity == 'NONE' and serial >= 12 and not serial%2: continue

                elif col_affinity == 'TEXT' and serial >= 13 and serial%2: continue

                else: return False
                
        #return the validated serials plus a code 8 for each skipped one
        return serials


        

    def get_col_aff(self, col_type):
        '''Returns the column affinity for the given column type'''
        #This algorithm follows the description of SQLite documentation
        #it is based on certain substrings contained in the column type string

        if 'int' in col_type: return 'INTEGER'

        elif 'char' in col_type or 'text' in col_type or 'clob' in col_type: return 'TEXT'

        elif not col_type or 'blob' in col_type: return 'NONE'

        elif 'real' in col_type or 'floa' in col_type or 'doub' in col_type: return 'REAL'

        else: return 'NUMERIC'


############################################################################################################################################################


class RecordRetriever:
    '''Retrieval of the records'''

    def __init__(self, file, filepath, corr, nostrict):
        self.file = file
        
        #options
        self.corr = corr
        self.nostrict = nostrict

        self.vr = VarintReader(file)
        self.dbs = DBSchema(filepath)

    def pl_decode_id(self, serial):
        '''Returns a piece of data read from the file basing on a given serial type'''
        #print("come into pl_decode_file:",serial)
        #serial 0: size 0, null
        if serial == 0: return None

        #serial 1: size 1, type int
        elif serial == 1: return struct.unpack('>B', self.file.read(1))[0]

        #serial 2: size 2, type int
        elif serial == 2: return struct.unpack('>H', self.file.read(2))[0]

        #serial 3: size 3, type int
        elif serial == 3: return struct.unpack('>I', b'\x00'+self.file.read(3))[0] #null-byte padding added

        #serial 4: size 4, type int
        elif serial == 4: return struct.unpack('>I', self.file.read(4))[0]

        #serial 5: size 6, type int
        elif serial == 5: return struct.unpack('>Q', b'\x00\x00'+self.file.read(6))[0]

        #serial 6: size 8, type int
        elif serial == 6: return struct.unpack('>Q', self.file.read(8))[0]

        #serial 7: size 8, type float
        elif serial == 7: return struct.unpack('>d', self.file.read(8))[0]

        #serial 8: size 0, constant 0
        elif serial == 8: return 0

        #serial 9: size 0, constant 1
        elif serial == 9: return 1
        else:return None

    def pl_decode_msg(self, serial):
        '''Returns a piece of data read from the file basing on a given serial type'''

        #serial N>=13 and odd: size (N-13)/2, type str
        if serial >=13 and serial%2:
            strsize = int((serial-13)/2)
            #print("hint some msg")

            try:
                tmp = self.file.read(strsize)
                tmp = tmp.decode(encoding = "utf-8")
                flag = zhPattern.match(tmp)
                if flag:
                    print("hit the msg:")
                    print(tmp)
                    return tmp
            except Exception as ex:
                tmp=None
                #print("decode error:",ex)
            return None
        else:
            return None



    def intact_rows_bruteforce(self, offset, end_offset, table_rootno):
        '''Retrieval of rows with intact headers'''

        #This function attempts a retrieval of intact rows adopting a brute-force strategy
        #in order to avoid the false negatives of corrupted and truncated rows.
        #Starting from given offset, it reads possible serial numbers according to the given table schema;
        #if these appear to be valid serial number, it proceeds to extract data,
        #which is further verified; the process loops by moving offset of one byte
        #until the indicated end offset is met.
        
        got = []
        found = {}
        #table description and number of columns
        table_desc = self.dbs.tables[table_rootno][1]
        #column_no = len(table_desc)
        offset = offset + 10
        while offset <= end_offset:
            #global_count =  global_count+1
            self.file.seek(offset)
            #print('At offset', offset)

            # try:
            #     pl_len, rowid, hd_len = self.vr.n_varints_file(3)
            # except:
            #     offset += 1
            #     continue

            #read as many varints as the number of columns
            serials = [0,0]
            try:
                type1 = self.vr.varint_integer()
                if type1 != 0:
                    offset += 1
                    continue
                    return
                type2 = self.vr.varint_integer()
                if type2 == None:
                    offset += 1
                    continue
                    return
                serials[0] = type1
                serials[1] = type2
            except struct.error:
                offset += 1
                continue

            #validate them
            gen = self.dbs.validate_serials(serials, table_desc, 0, self.nostrict)
            #if invalid, advance and restart
            if  gen == False:
                offset += 1
                continue
            if gen[0]>1000000 or gen[1]==0 or gen[1]>1000000 :
                offset += 1
                continue
            if self.file.tell() >= end_offset: break

            else:
                try:
                    #extract a row according to the found serials
                    #print(serials)
                    row=[None,None]
                    row[0]=0
                    row[1]=self.pl_decode_msg(serials[1])
                    if row[1] is None:
                        offset += 1
                        continue
                    #tt=global_data_sets
                    #row[1] = row[1].strip()
                    global_data_sets.append(row)
                    #bbytes = row[1].encode('utf8')
                    #b_length = len(bbytes)
                    #offset = offset+b_length
                    #continue
                except Exception as ex:
                    print(ex)
                    offset += 1
                    continue

                #if the row is not empty and its data is valid, append it to the list of results                
                # if any(row) and all([self.dbs.data_check(piece) for piece in row]):
                #     #append to found the start and end of this row
                #     found[offset] = self.file.tell()
                # if all([self.compatible_strings(row)[1:] != vis[1:] for vis in self.dbs.cells[table_rootno]]):
                #     if row[0] == None: row[0] = rowid
                #     row = self.compatible_strings(row)
                #     got.append(row)
                #
                #     offset = self.file.tell()+1
                #     continue

                #make a cursor check
                #if self.file.tell()>=end_offset: break

            #move on
            offset+=1
            
        #the dictionary found is used later in the retrieval of corrupted rows        
        return (got, found)


    def corrupted_rows_bruteforce(self, offset, end_offset, table_rootno, found):
        '''Partial retrieval of rows with corrupted headers'''

        #This function adopts an algorithm similar those of function intact_rows_bruteforce;
        #however, corrupted rows have corrupted primary key serials. Therefore, only non-primary key
        #serial numbers are read and validated. 
        #In each row, primary keys occupy a space of up to 8*pk_no bytes;
        #once the function has read non-pk serials, it tries to read the row starting at different offsets
        #so that it skips each possible number of bytes occupied by primary keys.
        #As a result, groups of possible rows are found instead of single rows 

        got = []
        #get table description, number of columns, number of primary keys
        table_desc = self.dbs.tables[table_rootno][1]
        column_no = len(table_desc)
        pk_no = len([column_desc for column_desc in table_desc if column_desc[5]])

        while offset <= end_offset:
            self.file.seek(offset)

            #if the cursor's at the beginning of a row that's already been found intact,
            #skip it and jump right after its end
            if offset in found:
                offset = found[offset] + 1
                continue

            try:
                #read as many possible serial numbers as the number of columns which are not primary keys
                serials = self.vr.n_varints_file(column_no - pk_no)

            except struct.error:
                offset += 1
                continue
            if self.file.tell() >= end_offset: break

            #validate them; advance and restart if not valid
            gen = self.dbs.validate_serials(serials, table_desc, pk_no, self.nostrict)
            if not gen:
                offset += 1
                continue

            else:
                group = []
                bku = self.file.tell()
                
                for i in range(8*pk_no):
                    #this allows all possible numbers of bytes occupied by primary keys
                    self.file.seek(bku + i)
                    #read row, append to group if valid
                    try:
                        row = [self.pl_decode_file(code) for code in gen]
                    except:
                        continue
                                              
                    if any(row) and all([self.dbs.data_check(piece) for piece in row]):
                        row = self.compatible_strings(row)
                        group.append(row)

                if any(group):
                    got.append(group)

            #move on
            offset +=1
        
        return got

        
    def scan_page(self, offset, end_offset, table_rootno):
        '''Retrieval of rows in a page depending on specified options'''

        #retrieve intact rows
        introws, found = self.intact_rows_bruteforce(offset, end_offset, table_rootno)
        #if specified by options, attempt retrieval of corrupted rows as well
        # if self.corr: corrows = self.corrupted_rows_bruteforce(offset, end_offset, table_rootno, found)
        # #otherwise return an empty list instead
        # else: corrows=[]
        
        return (introws, None)


    def compatible_strings(self, iterable):
        '''Returns a tuple in which all instances of bytes are converted into string and stripped of the leading b' and the final ' '''
        new = []
        for i in iterable:
            if isinstance(i, bytes): new.append(str(i)[2:-1])
            else: new.append(i)
        return tuple(new)
        

################################################################################################################################################


class DBScanner:
    '''High-level retrieving of deleted data and outputting'''
    
    def __init__(self, filepath, out, corr, nostrict, tab, raw, verbose):
        
        self.start = time.time()
        print('SQLiteRet', time.strftime('%d-%m-%Y %H:%M:%S', time.gmtime(self.start)))

        #init and check output
        self.out = out
        if self.out:
            try:
                open(self.out, 'wt')
            except:
                print('Cannot open output file. Please verify you have the permission to write to directory.\nExiting program.')
                exit(0)
            
    
        #init file and file info
        self.filepath = filepath
        try:
            self.file = open(self.filepath, 'rb')
        except Exception as ex:
            print(ex)
            print('Database file not found or you don\'t have permission to access file.\nExiting program.')
            exit(0)
        self.filesize = len(self.file.read())
        self.pagesize = self.find_pagesize()

        #init options
        self.corr = corr
        self.tab = tab
        self.raw = raw
        self.verbose = verbose

        #set up for retrieval        
        self.introws = defaultdict(list)
        self.corrows = defaultdict(list)
        self.done = []
        self.rst = sys.stdout
        self.nullwriter = NullWriter()
        self.rrt = RecordRetriever(self.file, filepath, corr, nostrict)


    def execute(self):
        '''Complete process of scanning the database and outputting the results'''

        print('\nThe program will now scan the whole database. The process may take several minutes. Please wait...\n')
        #if not self.verbose: sys.stdout = self.nullwriter
        #get rows from known schemas
        #print('\n\n')
        print('[1] find data in root')
        self.from_root()
        print('known_root id done')
        self.to_out()
        print('known_root output id done')

        #rows from unknown schemas

        print('\n\n')
        self.unknown_root()
        if not self.verbose: sys.stdout = self.rst
        print('\nScanning terminated')
        #output
        self.to_out()



    #-------------------------------------------------now all output functions

    def to_out(self,name='table_output'):
        '''Output results'''
        
        print('\nDatabase fully scanned in', time.strftime('%H:%M:%S', time.gmtime(time.time()-self.start)), '\nProceeding to output...')

        #if self.out: sys.stdout = open(self.out, 'wt')
        if self.tab: self.tab_print()
        else: self.raw_print()


    def raw_print(self):
        '''Prints rows as tuples'''
        print('raw_print')
        for i in self.introws:
            #print table name
            print()        
            print(self.rrt.dbs.tables[i][0])
            #get column names
            tdesc = self.rrt.dbs.tables[i][1]
            cnames = [t[1] for t in tdesc]
            if self.introws[i]:
                print()
                print('Fields: ', end='')
                for j in cnames: print(j, end=' ')
                print()

                try:
                    for r in self.introws[i]:
                        print(r)
                
		#unlikely to happen unless you have gigantic databases
                except MemoryError:
                    continue
                                    
            else:
                print('No intact records found for this table')

            if self.corr:
                print('\n\n'+self.rrt.dbs.tables[i][0],'[corrupted records]')
                if self.corrows[i]:
                    print()
                    print('Fields: ', end='')
                    for j in cnames: print(j, end=' ')
                    print()

                    try:
                        for t in self.corrows[i]:
                            for i in t: print(i)
                            print()
                    except MemoryError:
                        continue

                else:
                    print('No corrupted records found for this table')

            print('\n\n\n')


    def tab_print(self):
        '''Prints the rows as tab-separated values'''
        print("tab_print")
        for i in self.introws:
            print()        
            print(self.rrt.dbs.tables[i][0])            
            tdesc = self.rrt.dbs.tables[i][1]
            cnames = [t[1] for t in tdesc]
            if self.introws[i]:
                print()
                for j in cnames: print(j, end='\t')
                print('\n')


                try:
                    for r in self.introws[i]:
                        for p in r: print(p, end='\t')
                        print()
                     
                
                except MemoryError:
                    continue
                                    
            else:
                print('No intact records found for this table')

            if self.corr:
                print('\n')
                print(self.rrt.dbs.tables[i][0], '[CORRUPTED]\n')

                if self.corrows[i]:
                    for j in cnames: print(j, end='\t')
                    print('\n')

                    try:
                        for t in self.corrows[i]:                           
                            for i in t:
                                for p in i: 
                                    print(p, end='\t')                                      
                                print()
                            print()
                        
                    
                    except MemoryError: continue
                       
                else:
                    print('No corrupted records found for this table')

            print('\n\n\n')


            
    #-----------------------------------------------------------------------now functions for retrieving

        
    def find_pagesize(self):
        '''Returns needed information found in the database file header'''
        #database page size
        self.file.seek(16)
        pagesize = struct.unpack('>H', self.file.read(2))[0]
        if pagesize == 1: pagesize = 65536
        return pagesize


    def from_root(self):
        '''Retrieval from pages with known schema'''

        #Each table root page may contain, at the end of the page, the number of the other pages corresponding to that table.
        #If any number pages are found, visit each of them and retrieve rows using the schema of the root.
        
        print('Attempting retrieval from known schemas')
        for rootno in self.rrt.dbs.tables:
            print('\n Scanning table', self.rrt.dbs.tables[rootno][0])

            #the first page of the pages to scan is of course the root
            others = [rootno]

            #go to start of page
            offset = (rootno-1)*self.pagesize

            #start reading page
            while offset < rootno*self.pagesize:
                self.file.seek(offset)
                #read first two bytes
                zeros = struct.unpack('>BB', self.file.read(2))
                #verify they're 0; if so, the next byte is the number of a page to scan
                if not any(zeros):
                    page = struct.unpack('>B', self.file.read(1))[0]
                    #exclude page numbers 0 and 1
                    if page and page != 1: others.append(page)
                #move further on
                offset+=1

            #clean up the list a bit
            others = sorted(set(others))
            #then visit each of the page numbers found
            for pageno in others:
                #scan the pages and find the rows - if the user hasn't specified otherwise, 
	        #corrupted rows won't be looked for and an empty list will be returned instead
                introws, corrows = self.rrt.scan_page(self.pagesize*(pageno-1), self.pagesize*pageno, rootno)
                #append to main dictionaries intact and corrupted rows
                self.introws[rootno].extend(introws)
                self.corrows[rootno].extend(corrows)

                #give different outputs depending on the user's option for corrupted rows
                if self.corr:
                    print('  Page {:>3}\t{:>4} intact rows found\t{:>4} corrupted rows found'.format(pageno, len(introws), len(corrows)))
                else:
                    print('  Page {:>3}\t{:>4} rows found'.format(pageno, len(introws)))
                #print("find delete record:")
                #print(introws)
 
            #remember which pages have already been scanned
            self.done.extend(others)


    def unknown_root(self):
        '''Retrieval from pages with unknown schema'''

        #This function scans the pages which haven't been found to belong to a certain table. 
        #It bruteforces all the schemas trying to retrieve rows from each.
        #If more than one schema has found valid rows, the program requires user interaction.
        
        print('Attempting retrieval from unknown schemas\nThe process may require user interaction!')

        #go to page 3
        offset = self.pagesize*2
        pageno = 3

        while offset < self.filesize:
        #skip pages already done 
            if pageno in self.done:                
                offset += self.pagesize
                pageno+=1
                continue

            else:
                self.file.seek(offset)
                flag = struct.unpack('>B', self.file.read(1))[0]
                #skip index pages
                if flag in [10, 12]:
                    offset += self.pagesize
                    pageno+=1
                    continue                

                #recover the rows for each schemas
                print('\n Scanning page', pageno)
                d = {}
                for root in self.rrt.dbs.tables:
                    print('  Attempting schema {:<25}'.format(self.rrt.dbs.tables[root][0]), end='\t')
                    d[root] = self.rrt.scan_page(offset, offset+self.pagesize, root)
                    if self.corr:
                        print('found: {:>4} intact rows {:>4} corrupted rows'.format(len(d[root][0]), len(d[root][1])))
                    else:
                        print('found {:>4} intact rows'.format(len(d[root][0])))

                #the possible valid schemas are those which have found at least one row, either intact or corrupted
                possible = [x for x in d if d[x][0] or d[x][1]]

                root = 0

                #if more than one schema has found valid rows, require user interaction
                if len(possible)>1:
                    #if verbose is not active, return stdout to original
                    if not self.verbose: sys.stdout = self.rst
                    print('\nConflict between DB schemas. Please select from the following rows the one you consider correct:')

                    #give an option not to dump any row
                    print('\n-1\tNone of these row is correct')

                    #give options for each of the schemas presenting as a sample the first row found for each schema
                    for i in range(len(possible)):                        
                        page = possible[i]
                        if d[page][0]:
                            print(i, '\t', d[page][0][0], '\tfor table', self.rrt.dbs.tables[page][0])
                        else:
                            print(i, '\t', d[page][1][0], '\tfor table', self.rrt.dbs.tables[page][0])


                    #ask to choose option
                    while True:
                        choice = int(input('\nEnter number:'))

                        if choice == -1: break #dump nothing

                        elif choice in range(len(possible)): #choose corresponding root
                            root = possible[choice]
                            break
                        
                        else: print('Invalid choice')
                    #if  not verbose, return print function to silent
                    if not self.verbose: sys.stdout = self.nullwriter

                #if only one schema is valid, the root chosen is that one
                elif len(possible) == 1:
                    root = possible[0]

                #if no schema was valid, print a message
                elif len(possible) == 0:
                    print('  No records found in this page')
                    #if no records have been found, there is a chance there are no more full page. 
		    #Go backwards, read a significant number of bytes and, if they're all 0,
                    #terminate scanning.
                    self.file.seek(self.file.tell()-100)
                    if not any(self.file.read(100)): break

                if root:
                    introws, corrows = d[root]
                    self.introws[root].extend(introws)
                    self.corrows[root].extend(corrows)

            offset += self.pagesize
            pageno += 1

    def all_table_scan(self):
        page_num = int(self.filesize/self.pagesize)
        others = range(3,page_num)
        # then visit each of the page numbers found
        for pageno in others:
            print("scaning page no is :",pageno)
            # scan the pages and find the rows - if the user hasn't specified otherwise,
            # corrupted rows won't be looked for and an empty list will be returned instead
            introws, corrows = self.rrt.scan_page(self.pagesize * (pageno - 1), self.pagesize * pageno, 21)
            # append to main dictionaries intact and corrupted rows
            #self.introws[rootno].extend(introws)
            #self.corrows[rootno].extend(corrows)

            # give different outputs depending on the user's option for corrupted rows
            # if self.corr:
            #     print('  Page {:>3}\t{:>4} intact rows found\t{:>4} corrupted rows found'.format(pageno, len(introws),
            #                                                                                      len(corrows)))
            # else:
            #     print('  Page {:>3}\t{:>4} rows found'.format(pageno, len(introws)))
            # print("find delete record:")
            # print(introws)

        # remember which pages have already been scanned
        # self.done.extend(others)

        

###################################################################################################################################################################

                        
def main():
    epilog='''
-----------------------------------------------------------------------

More on usage options:

 Corrupted rows: selecting this option, the program will try to partially retrieve rows which contain 
  corrupted data; this can be useful to recover corrupted strings, but please bear in mind that the 
  reliability of these results is limited.

 Non-strict mode: if this option is NOT selected, the program runs in strict mode and assumes a regular 
  use of the database i.e. numeric types actually store numbers, string types store strings and so forth; 
  in non-strict mode, the program follows the looser guidelines of SQLite, which allows for "improper" 
  uses of table types, e.g. it is possible to store a string in a int type table.

 Output file: if not specified, results will be dumped to stdout.

 Output modes: 
   --tab if this option is selected, each row will be printed as a list of values separated by tabs.
   --raw if this option is selected, each row will be printed as a tuple.
   If no output mode is chosen, it defaults to raw.
'''
    
    parser = argparse.ArgumentParser(description = 'SQLiteRet: retrieve deleted rows from SQLite databases and dump them.\nMay require user interaction.', epilog=epilog, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('file', help='database file') 
    parser.add_argument('-c','--corrupted', action='store_true', default=False, help='also attempt retrieval of corrupted rows')
    parser.add_argument('-ns','--nostrict', action='store_true', help='run the program in non-strict mode')
    parser.add_argument('-o','--output', metavar='outputFile', default=False, help='specify output file')
    mode = parser.add_mutually_exclusive_group() 
    mode.add_argument('-t','--tab', action='store_true', help='print results as lists of tab-separated values')
    mode.add_argument('-r','--raw', action='store_true', help='print results as tuples')
    parser.add_argument('-v', '--verbose', action='store_true', help='print additional information')
    args = parser.parse_args()

    dbscanner = DBScanner(filepath = args.file, out = args.output, corr = args.corrupted, nostrict = args.nostrict, tab=args.tab, raw=args.raw, verbose = args.verbose)
    tt = global_undelete_data
    dbscanner.all_table_scan()
    json ={}
    remain_list =[]
    for line in global_undelete_data:
        json[line[1]]=line[0]
    for msg in global_data_sets:
        if msg[1] not in json:
            remain_list.append(msg)
    write_data(remain_list)
    #dbscanner.execute()

    

main()

if  __name__ == '__main__':
    print('total step:',global_count)
    write()


            


