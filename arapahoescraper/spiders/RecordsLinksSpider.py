import os
import re
import scrapy
from scrapy import log, signals
from scrapy.xlib.pydispatch import dispatcher
from selenium import webdriver
from datetime import datetime, timedelta
from selenium.common.exceptions import TimeoutException, NoSuchElementException

count = 0

def close_webdriver(wd): wd.quit()

def ternaty(regexp, str, replace1, replace2):
    value = re.findall(regexp, str)
    if value:
        value = [g for g in value[0] if g]
    value = '' if not value else value[0].replace(replace1, '')
    if value and replace2:
        return value.replace(replace2, '')
    else:
        return value

def get_sec_twp_rng(legal):
    subdivision = ''
    if type(legal) == list or type(legal) == tuple:
        legal = ' '.join(legal)
    matches = re.findall(r'(( |^)[0-9]{1,2} [0-9]{1,2} [0-9]{1,2})|(( |^)[0-9]{1,2}-[0-9]{1,2}-[0-9]{1,2})',
                     legal)
    if matches:
        matches = [match.strip() for match in matches[0] if match.strip()]
        m = matches[0]
        if '-' in m:
            m = m.split('-')
        else:
            m = m.split(' ')
        return {'sec': m[0], 'twp': m[1], 'rng': m[2], 'blk': '', 'lot': '', 'subdivision': ''}

    lower = legal.lower()
    sec_reg = r'(sec [0-9]{1,2})|(sec:[0-9]{1,2})'
    twp_reg = r'(tp [0-9]{1,2})|(tp:[0-9]{1,2})'
    rng_reg = r'(rng [0-9]{1,2})|(rng:[0-9]{1,2})'
    blk_reg = r'(blk[s]? [0-9]{1,2}&[0-9]{1,2})|(blk[s]? [0-9]{1,2}-[0-9]{1,2})|(blk[s]? [0-9]{1,2})'
    lot_reg = r'(lot[s]? [0-9]{1,2}&[0-9]{1,2})|(lot[s]? [0-9]{1,2}-[0-9]{1,2})|(lot[s]? [0-9]{1,2})'
    sec = ternaty(sec_reg, lower, 'sec ', 'sec1')
    twp = ternaty(twp_reg, lower, 'tp ', 'tp:')
    rng = ternaty(rng_reg, lower, 'rng ', 'rng:')
    blk = ternaty(blk_reg, lower, 'blk ', '')
    lot = ternaty(lot_reg, lower, 'lot ', 'lots ')
    if lot and blk:
        subdivision = ternaty('((' + blk_reg + ') .*)', lower, 'blk ' + blk + ' ', '')
    elif lot:
        subdivision = ternaty('((' + lot_reg + ') .*)', lower, 'lot ' + lot + ' ', 'lots ' + lot + ' ')
    return {'sec': sec, 'twp': twp, 'rng': rng, 'blk': blk, 'lot': lot, 'subdivision': subdivision.upper()}

class RecordsLinksSpider(scrapy.Spider):
    name = 'linksspider'
    date_formatter = "%m/%d/%Y"

    start_urls = ['http://legacy4.arapahoegov.com/oncoreweb/Search.aspx']

    def __init__(self, **kwargs):
        self.failed_urls = []
        self.end_date = datetime.today()
        self.start_date = self.end_date - timedelta(days=365 * 37)
        print('Scraping from ' + str(self.start_date))
        self.driver = webdriver.PhantomJS(os.path.join(os.path.dirname(__file__), 'bin/phantomjs'))
        self.driver.set_page_load_timeout(30)
        self.driver.set_script_timeout(30)
        dispatcher.connect(self.spider_closed, signals.spider_closed)

    def spider_closed(self, spider):
        self.crawler.stats.set_value('failed_urls', ','.join(spider.failed_urls))
        close_webdriver(self.driver)

    def parse(self, response):
        exception_message = '- - - - No Such Element Exception'
        elements_by_xpath = self.driver.find_elements_by_xpath
        element_by_xpath = self.driver.find_element_by_xpath
        by_id = self.driver.find_element_by_id
        total = 0
        def next_page():
            next_pages = None
            try:
                next_pages = [page
                         for page in elements_by_xpath(
                        ".//tr[@class='stdFontPager'][position()=1]/td//a[preceding-sibling::span]")]
            except NoSuchElementException:
                if '400 Bad Request' in self.driver.page_source:
                    print(exception_message)
                    self.driver.delete_all_cookies()
                    self.driver.refresh()
                    return next_page()
            if next_pages: return next_pages[0]
            else: return next_pages

        def get_hrefs():
            return list(set([e.get_attribute('href').replace('showdetails', 'details').replace('ShowDetails', 'details')
                    for e in elements_by_xpath(".//a[@class='stdFontResults']")]))

        def next_date(total):
            if total % 5 == 0:
                self.driver.delete_all_cookies()
                total = 0
            try:
                search_selector = element_by_xpath(".//table[@id='Table2']/tbody/tr[position() = last() - 1]//a")
                search_selector.click()
                submit = by_id('cmdSubmit')
                date_input = by_id('txtRecordDate')
                date_input.clear()
                date_input.send_keys(date.strftime(self.date_formatter))
                submit.click()
            except NoSuchElementException:
                self.driver.get(self.start_urls[0])
                next_date(total)

        self.driver.get(response.url)

        for date in self.dates():
            next_date(total)
            total += 1
            hrefs = get_hrefs()
            for href in hrefs:
                request = scrapy.Request(href,
                                         callback=self.parse_item)
                yield request
            next = next_page()
            while next:
                try:
                    next.click()
                except TimeoutException:
                    self.driver.refresh()
                    next = next_page()
                    next.click()
                hrefs = get_hrefs()
                for href in hrefs:
                    request = scrapy.Request(href,
                                             callback=self.parse_item)
                    yield request
                next = next_page()
            #log.msg(str(date), level=log.ERROR, spider=self)

        self.driver.close()

    def parse_item(self, response):
        if response.status == 404:
            self.failed_urls.append(response.url)
            return {}
        #log.msg('Scraping ' + str(response.url), level=log.ERROR, spider=self)
        item = {}
        search_pattern = [('instrument', 'lblCfn'), ('docType', 'lblDocumentType'), ('modifyDate', 'lblModifyDate'),
                          ('recordDate', 'lblRecordDate'), ('acknowledgementDate', 'lblAcknowledgementDate'),
                          ('grantor', 'lblDirectName'), ('grantee', 'lblReverseName'), ('bookType', 'lblBookType'),
                          ('bookPage', 'lblBookPage'), ('numberPages', 'lblNumberPages'),
                          ('consideration', 'lblConsideration'), ('comments', 'lblComments'),
                          ('comments2', 'lblComments2'), ('marriageDate', 'lblMarriageDate'),
                          ('legal', 'lblLegal'), ('address', 'lblAddress'), ('caseNumber', 'lblCaseNumber'),
                          ('parse1Id', 'lblParcelId'), ('furureDocs', 'pnlFutureDocs'), ('prevDocs', 'pnlPrevDocs'),
                          ('unresolvedLinks', 'lblUnresolvedLinks'), ('relatedDocs', 'pnlRelatedDocs'),
                          ('docHistory', 'pnlDocHistory'), ('refNum', 'lblRefNum'), ('rerecord', 'lblRerecord')]

        for key, id in search_pattern:
            value = response.selector.xpath(".//span[@id='%s']//text()" % id).extract()
            if value:
                if len(value) > 1:
                    item[key] = value
                else:
                    item[key] = value[0]
            else:
                item[key] = ''

        item['recep'] = item['instrument'][:-7].lstrip('0')
        item['year'] = item['instrument'][:4]
        item['Reception No'] = item['recep'] + '-' + item['year']
        if item['bookPage'].split('/') == 2:
            item['book'] = item['bookPage'].split('/')[0].strip()
            item['page'] = item['bookPage'].split('/')[1].strip()
        else:
            item['book'] = ''
            item['page'] = ''
        item['url'] = response.url
        if item['legal']:
            item.update(get_sec_twp_rng(item['legal']))
        yield item

    def dates(self):
        date = self.end_date
        yield date
        while date > self.start_date:
            date -= timedelta(days=1)
            print('Yielding date: ' + str(date))
            yield date
