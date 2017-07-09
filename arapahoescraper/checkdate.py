import os
from pymongo import MongoClient
from datetime import datetime

client = MongoClient(os.environ['MONGODB_URI'])

db = client['adcogov']
col = db['adcogovrecords']
dates = [datetime.strptime(d['recordDate'].split(' ')[0].strip(), '%m/%d/%Y') for d in col.find({},{'recordDate' : 1})]
    
#instr = set([d['instrument'] for d in col.find({},{'instrument' : 1})])
#print(len(list(instr)))
print(min(dates))



