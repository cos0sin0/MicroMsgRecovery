SQLiteRet
=========
**Recover deleted data from SQLite databases**

  SQLiteRet is a Python3 script which goes through a SQLite database file and dumps all intact deleted rows it finds. Optionally, it attempts retrieval of partial (corrupted) rows and exports to file.

Usage:
---------
`sqliteret.py file [--corrupted] [--nostrict] [--output outputFile] [--tab | --raw] [--verbose] [--help]`

* --corrupted, -c 

  **Corrupted rows**: selecting this option, the program will try to partially retrieve rows which contain corrupted data; the option is most useful to read through deleted string (corrupted rows make up to 80% of deleted rows), but please bear in mind that the reliability of these results is limited as these row can never be recovered with accuracy. Since primary keys are not available, they're outputted as 0.
  Due to corruption, each partial row might be read in different ways and a group of rows is outputted istead of a single row. 
  In output, each group is separated by an additional new-line.
  

* --nostrict, -ns

  **Strict and non strict mode**: normally, the program runs in strict mode, i.e. it assumes a common use of table types, which means *int* type tables actually store integers, *char* type tables actually store strings and so forth. However, SQLite allows for more flexible table types, e.g. an integer can be stored in a *char* type table. If you suspect a non regular use of table types, select the --nostrict option. 
Note: running this option raises the odds of false hits.


* --output outputFile, -o outputFile

  **Output files**: select an output file. Recommended types are .tsv and .txt.
If not specified, results will be printed to sdout.
Note: use this option instead of output redirection, since the program may require user interaction.


* --tab, -t | --raw,-r

  **Output modes**: tab mode outputs each row as a tab-separated list of values. It is recommended for .tsv files.
raw mode outputs each row as a Python tuple. It is recommended for stdout and .txt files.
Defaults to raw.


* --verbose, -v

  **Verbose mode**: prints additional information during execution.

User interaction:
-----------------
User interaction might be required if a database page is found to belong to more than one possible table. 
The program will ask to choose between the possible schemas presenting an example of a row decoded to each schema.


Usage example:
-------------
`sqliteret.py cookies.sqlite -c -o results.tsv -t -v`

  Sample output:
![alt sample output](http://s3.postimg.org/3s8leoflv/two.png "Sample output")

`sqliteret.py cookies.sqlite -c -o results.txt`

  Sample output:
![alt sample output](http://s8.postimg.org/pocz34c4l/one.png "Sample output")


Note:
----- 
SQLiteRet relies on the principle that deleted data can be found in the file's free (unallocated) space. Therefore, the chance of recovering data from databases which have been fully vacuumed and defragmented is minimal.


  
  
