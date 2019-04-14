import time
import re
import csv
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
from random import randint

reviews = []

def save_to_csv(list_of_dicts, file_name):
    with open(str(time.time()).replace('.','') + '_' + file_name + '.csv', 'w') as f:
        for this_dict in list_of_dicts:
            w = csv.DictWriter(f, this_dict.keys())
            w.writerow(this_dict)

class Browser():
    def __init__(self, browser_name, url, reviews_to_scrape, options):
        self.name = browser_name
        self.url = url
        self.reviews_to_scrape = reviews_to_scrape
        self.reviews = []
        self.options = options
        self.driver = webdriver.Chrome()
        self.driver.get(self.url)
        time.sleep(5)
        self.page_count = 1
        self.start_time = time.time()
        self.average_timing = 1
        self.timings = []
        self.duplicates = {}
        self.custom_css_applied = False
    
    def click_to_next_page(self):
        if self.custom_css_applied is False:
            hide_style = ('''
                var __hideStyle = document.createElement('style'); 
                __hideStyle.innerHTML = "%s";
                document.getElementsByTagName('body')[0].appendChild(__hideStyle);
            ''' %(self.options['custom_css']))
            self.driver.execute_script(hide_style)
            self.custom_css_applied = True
        self.driver.execute_script('document.querySelector("%s").scrollIntoView(); window.scrollBy(0,-window.innerHeight/2)' %(self.options['load_more_link']))
        time.sleep(0.2)
        self.driver.find_element_by_css_selector(self.options['load_more_link']).click()
        self.page_count += 1
        timing = time.time() - self.start_time
        self.timings.append(timing)
        self.average_timing = sum(self.timings)/len(self.timings)
        # time.sleep(self.average_timing)

    def count_stars(self, review):
        if self.options['site'] == 'google':
            return int(re.findall('sr=(.)',self.url)[0])
        if self.options['site'] == 'amazon':
            return self.get_element(review, self.options['review_selectors']['stars'], attribute='innerHTML').split(' ')[0].split('.')[0]
        star_count = 0
        stars = self.get_element(review, self.options['review_selectors']['stars'], collection = True)
        if self.options['site'] == 'leesa':
            filled_star = 'M11,0L7.8,6.6L0.5,7.6l5.3,5.1L4.5,20l6.5-3.4l6.5,3.4l-1.2-7.2l5.3-5.1l-7.3-1.1L11,0L11,0z'
            attribute = 'd'
        if self.options['site'] == 'purple':
            filled_star = 'fa fa-star ' 
            attribute = 'class'
        try:
            for star in stars:
                if star.get_attribute(attribute) == filled_star:
                    star_count += 1
        except:
            pass
        return star_count

    def get_element(self, parent_element, child_element_selector, collection = False, attribute = False):
        try:
            if collection:
                result = parent_element.find_elements_by_css_selector(child_element_selector)
            else:
                result = parent_element.find_element_by_css_selector(child_element_selector)
            if attribute:
                result = result.get_attribute(attribute)
            return result
        except StaleElementReferenceException:
            return False
        except NoSuchElementException:
            return None
    
    def stringify(self, to_stringify):
        if type(to_stringify) is bool:
            to_stringify = 'False'
        if type(to_stringify) is not str:
            to_stringify = to_stringify.encode('utf-8')
        return re.sub(r'([^a-zA-Z\d\s+]|\s+)','',to_stringify).lower()
    
    def get_key(self, data):
        if data['body'] is not None:
            key_string = self.stringify(data['name']) + self.stringify(data['date']) + self.stringify(data['title'])
            key_string += self.stringify(data['body'])[0:30]
        else:
            key_string = randint(999, 99999999999999999)
        return key_string
    
    def key_exists(self, data):
        exists = any(r['key'] == data['key'] for r in self.reviews[len(self.reviews)-self.options['per_page'] : len(self.reviews)])
        if exists:
            try:
                self.duplicates[data['key']] += 1
            except:
                self.duplicates.update({data['key']: 1})
            if self.duplicates[data['key']] > 5:
                return False
        return exists
        
    def data_contains_false(self, data):
        for value in data.values():
            if value == False:
                return True
        return False
    
    def get_review_data(self,review):
        data = {}
        data['id'] = len(self.reviews) + 1
        for option_key,option_value in self.options['review_selectors'].items():
            if option_key is not 'stars':
                if option_value == '':
                    data[option_key] = ''
                else:    
                    data[option_key] = self.get_element(review, option_value, False, 'innerHTML')
            else:
                if option_value == '':
                    data[option_key] = ''
                else:
                    data['stars'] = self.count_stars(review)
        data['key'] = self.get_key(data)
        if self.key_exists(data) or self.data_contains_false(data):
            return False
        return data
    
    def report(self):
        completion = len(self.reviews)/self.reviews_to_scrape
        eta_seconds = (self.reviews_to_scrape-len(self.reviews))/self.options['per_page'] * self.average_timing
        print('%s ### Page: %s ### Reviews: %s/%s ### Complete: %.2f%% ### ETA: %.2f hrs ### Average: %.4f' %(self.name, self.page_count, len(self.reviews), self.reviews_to_scrape, completion*100, eta_seconds/60/60, self.average_timing))
    
    def run(self):
        self.start_time = time.time()
        reviews_on_page = self.driver.find_elements_by_css_selector(self.options['review_container'])
        for review in reviews_on_page:
            data = self.get_review_data(review)
            if data is False:
                break
            reviews.append(data)
            self.reviews.append(data)
        if len(reviews_on_page) == self.options['per_page'] and data is not False:
            self.click_to_next_page()
            self.report()


class Scrape():
    def __init__(self, options):
        self.options = options
        self.browsers = []
        self.total_reviews_to_scrape = 0
        for url in self.options['urls']:
            self.total_reviews_to_scrape += url['reviews_to_scrape']
            browser_name = ('Browser%s' %(self.options['urls'].index(url)))
            self.browsers.append(Browser(browser_name, url['url'],url['reviews_to_scrape'], self.options))
            print('Creating browser #%s for %s' %(browser_name, url))
        while (len(reviews) < self.total_reviews_to_scrape):
            for browser in self.browsers:
                if len(browser.reviews) < browser.reviews_to_scrape:
                    browser.run()

leesa = {
    'site': 'leesa',
    'urls': [{
        'url': 'https://www.leesa.com/pages/reviews', 
        'reviews_to_scrape': 14379
    }],
    'review_container': '.product-review',
    'review_selectors': {
        'name': '.product-review__name',
        'date': '.product-review__date',
        'stars': '.product-review__stars svg path',
        'title': '.product-review__title',
        'body': '.product-review__content',
    },
    'load_more_link': 'span.reviews-area__pagination__next',
    'per_page': 10,
    'custom_css': ''
}  

purple = {
    'site': 'purple',
    'urls': [{
        'url': 'https://purple.com/mattress/buy#reviews', 
        'reviews_to_scrape': 11473
    }],
    'review_container': '.stamped-reviews .stamped-review',
    'review_selectors': {
       'name': '.author',
        'date': '.created',
        'stars': '.stamped-starratings i',
        'title': '.stamped-review-header-title',
        'body': '.stamped-review-content-body',
    },
    'load_more_link': '.next a',
    'per_page': 5,
    'custom_css': '.section-general,.modal-overlay.exit-intent-popup.animation-queued.is-open {display: none !important;}'
}

tuftandneedle = {
    'site': 'tuftandneedle',
    'urls': [{
        'url': 'https://www.tuftandneedle.com/mattress/reviews/', 
        'reviews_to_scrape': 57767
    }],
    'review_container': '.review',
    'review_selectors': {
        'name': '.name',
        'date': '.date',
        'body': '.response',
        'stars': '',
        'title': ''
    },
    'load_more_link': 'a.next_page',
    'per_page': 10,
    'custom_css': '.pop_backdrop, .exit_pop, .loading { display:none !important; }'
}

amazon = {
    'site': 'amazon',
    'urls': [{
        'url': 'https://www.amazon.com/Casper-Sleep-Mattress-Supportive-Scientifically/product-reviews/B00M9CODDW/ref=cm_cr_dp_d_show_all_top?ie=UTF8&reviewerType=all_reviews', 
        'reviews_to_scrape': 952
    }],
    'review_container': '.review',
    'review_selectors': {
        'name': '.author',
        'date': '.review-date',
        'body': '.review-text',
        'stars': '.a-icon-star .a-icon-alt',
        'title': '.review-title'
    },
    'load_more_link': 'ul.a-pagination .a-last a',
    'per_page': 10,
    'custom_css': ''
}

google = {
    'site': 'google',
    'urls': [
        {
            'url': 'https://www.google.com/shopping/customerreviews/merchantreviews?q=casper.com&sr=1', 
            'reviews_to_scrape': 102
        },
        {
            'url': 'https://www.google.com/shopping/customerreviews/merchantreviews?q=casper.com&sr=2', 
            'reviews_to_scrape': 156
        },
        {
            'url': 'https://www.google.com/shopping/customerreviews/merchantreviews?q=casper.com&sr=3', 
            'reviews_to_scrape': 422
        },
        {
            'url': 'https://www.google.com/shopping/customerreviews/merchantreviews?q=casper.com&sr=4', 
            'reviews_to_scrape': 2213
        },
        {
            'url': 'https://www.google.com/shopping/customerreviews/merchantreviews?q=casper.com&sr=5', 
            'reviews_to_scrape': 27304
        },
    ],
    'review_container': '.SzAWKe',
    'review_selectors': {
        'name': '',
        'date': '.CfOeR',
        'body': '.SzAWKe div[style="margin-top:6px"]',
        'stars': True,
        'title': ''
    },
    'load_more_link': '.H6F5E.JjMFxf',
    'per_page': 10,
    'custom_css': ''
}

options = google #google amazon tuftandneedle purple leesa
scraper = Scrape(options)
# save_to_csv(reviews,options['site'])