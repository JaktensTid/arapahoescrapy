import gc
import subprocess

while True:
    process = subprocess.Popen('scrapy crawl linksspider', shell=True, stdout=subprocess.PIPE)
    process.wait()
    gc.collect()