from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from scrapy.conf import settings
from scrapy import log

total = 0
class MongodbPipeLine(object):
    def __init__(self):
        connection = MongoClient(settings['MONGODB_URI'])
        db = connection[settings['MONGODB_DB']]
        self.collection = db[settings['MONGODB_COLLECTION']]

    def process_item(self, item, spider):
        global total
        if 'instrument' in item:
            if item:
                total += 1
                try:
                    self.collection.insert_one(item)
                except DuplicateKeyError:
                    print('Duplicate key')
            return item


