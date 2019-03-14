"""
This module is used to scrape linkedin.
Currently only support scraping people that match
a given search keyword in a specific location. At the moment
only supported location is 'Colombia'.

For example if we set keyword = 'Data Scientist'
the class LinkedinPeopleScraper will scrape all the profiles
of people that match that query in the specified location.
"""

import time
import os
import json
import pandas as pd
from flatten_json import flatten
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException)
from selenium.webdriver.common.action_chains import ActionChains


def read_json(file):
    '''
    function that reads a json file
    '''
    with open(file, 'r') as input_:
        results = json.loads(json.load(input_))
    return results

def write_json(data, file_name):
    '''
    writes a json file of the given data
    '''
    with open(file_name, 'w') as output:
        json.dump(json.dumps(data), output)

def to_excel_batch(keyword):
    files=os.listdir('results/{}'.format(keyword))
    results = [read_json('results/CEO/{}'.format(i)) for i in files]
    results = [flatten(i) for i in results]
    df = pd.DataFrame(results)
    return df
    
class LinkedinPeopleScraper:
    """
    Class that scrapes all the persons in a linkedin search
    given a keyword and a location
    """

    def __init__(self, keyword, username,
                 password, location="Colombia"):

        self.keyword = keyword
        self.username = username
        self.password = password
        self.location = location
        self.driver = webdriver.Firefox()
        self.data = []
        self.wall_time = 0

        # Create a directory to save results if it doesnt exist
        self.results_dir = 'results/{}'.format(self.keyword)
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

    def login(self):
        '''
        This method enters linkedin with a given username and password
        '''
        self.driver.get("https://linkedin.com")
        username_item = self.driver.find_element_by_xpath(
            '//input[@id="login-email"]')
        password_item = self.driver.find_element_by_xpath(
            '//input[@id="login-password"]')
        username_item.send_keys(self.username)
        password_item.send_keys(self.password)
        self.driver.find_element_by_xpath(
            '//input[@class="login submit-button"]').click()

    def url_location_mapper(self):
        '''
        Method that maps a location like "Colombia" to the corresponding code that
        needs to be inserted in the linkedin url in order to see only results of
        people in colombia.
        '''
        mapping = {"Colombia": "co"}
        return mapping[self.location]

    def infinite_scroller(self, speed='fast'):
        '''
        This function is used to scroll down to the bottom of a page with
        infinite scrolling
        '''
        scroll_pause_time = 1
        act = ActionChains(self.driver)
        while True:
            # Scroll down
            if speed == 'fast':
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight)")
            elif speed == 'slow':
                self.driver.execute_script("window.scrollBy(0, 200)")
            elif speed == 'medium':
                act.send_keys(Keys.PAGE_DOWN).perform()

            # Wait to load page
            time.sleep(scroll_pause_time)

            copyright_ = self.driver.find_elements_by_id('footer-copyright')

            attempts = 3
            intent = 0
            print('Checking if no more scrolls...')
            for attempt in range(attempts):
                print('Attempt = {}'.format(attempt))
                if copyright_:
                    intent += 1
                    print('Finished verifications = {}'.format(intent))
                    time.sleep(1)
                    copyright_ = self.driver.find_elements_by_id(
                        'footer-copyright')
                else:
                    break

            if intent == attempts:
                print('Already at bottom of page!')
                break

    def get_profile_links(self, page):
        '''
        Given a keyword, location and a page number (of the total number of pages),
        this method returns the links of the profiles found in that page.
        '''

        mapped_location = self.url_location_mapper()
        search_url = ("https://www.linkedin.com/search/results/people/"
                      "?facetGeoRegion=%5B%22{}%3A0%22%5D&keywords={}&"
                      "origin=FACETED_SEARCH&page={}".
                      format(mapped_location, self.keyword, page))
        self.driver.get(search_url)

        # Load all page by scrolling to bottom
        self.infinite_scroller(speed='slow')

        time.sleep(3)

        profile_links_items = WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located((
                By.XPATH, '//a[@class="search-result__result-link ember-view"]')))
        # We extract all profile links. We use set to ensure there are no duplicates
        profile_links = (
            list(set([profile.get_attribute('href')
                      for profile in profile_links_items])))

        return profile_links

    def expand_all(self):
        '''
        There are many elements in a linkedin profile were you need to click on a
        "show more" button in order to see full information. This method clicks on
        all buttons needed so everything is expanded and full info is available.
        '''
        # First we need to scroll down to completely load the page
        self.infinite_scroller(speed='medium')

        # Last thing to load on a linkedin page is the interests box
        # So we know page if loaded when we can find this element.
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((
                By.XPATH, (
                    '//section[@class="pv-profile-section'
                    ' pv-interests-section artdeco-container-card ember-view"]'))))

        # Expand description box2
        try:
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.XPATH, ('//li-icon[@class='
                               '"pv-top-card-section__summary-toggle-button-icon"]')))).click()
        except TimeoutException:
            pass

        # Expand everythin else: Exeperience, education, etc...

        while True:
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((
                        By.XPATH, (
                            '//li-icon[@class="pv-profile-section__toggle-detail-icon"'
                            ' and contains(@type,"chevron-down-icon")]')))).click()
            except TimeoutException:
                break

        # Expand skills section
        try:
            self.driver.find_element_by_xpath(
                '//li-icon[@class="pv-skills-section__chevron-icon"]').click()
        except NoSuchElementException:
            pass

    def get_profile_data(self, profile_link):
        '''
        This function scrapes relevant data of a profile given its profile linke
        '''

        # Enter the profile link
        self.driver.get(profile_link)

        # We expand everything we need to scrape
        self.expand_all()

        # Create dictionary conatining user data
        user_data = dict.fromkeys(['link', 'name', 'headline', 'description',
                                   'experience', 'education', 'aptitudes'])
        link = profile_link
        name = self.driver.find_element_by_xpath(
            '//h1[@class="pv-top-card-section__name inline t-24 t-black t-normal"]').text
        headline = self.driver.find_element_by_xpath(
            '//h2[@class="pv-top-card-section__headline mt1 t-18 t-black t-normal"]').text
        description = None
        try:
            description_box = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((
                    By.XPATH, (
                        '//div[@class="pv-top-card-section__summary'
                        ' pv-top-card-section__summary--with-content mt4 ember-view"]'))))
            description = description_box.find_element_by_tag_name('p').text
        except TimeoutException:
            pass

        # Experience section
        experience_section = self.driver.find_element_by_id(
            "experience-section")

        experience_items = (
            experience_section.find_elements_by_xpath(
                (('.//div[@class="pv-entity__position-group-pager'
                  ' pv-profile-section__list-item ember-view"]')))
            + experience_section.find_elements_by_xpath(
                (('.//li[@class="pv-profile-section__sortable-item'
                  ' pv-profile-section__section-info-item relative'
                  ' pv-profile-section__list-item sortable-item ember-view"]'))))

        experience_list = []

        for job in experience_items:
            experience_dict = dict.fromkeys(
                ['job_title', 'company', 'date_range', 'total_duration'])
            if job.find_elements_by_xpath('.//ul[contains(@class,"pv-entity__position-group")]'):
                temp = job.find_element_by_xpath(
                    './/div[@class="pv-entity__company-summary-info"]').text.split('\n')
                experience_dict['company'] = temp[1]
                experience_dict['total_duration'] = temp[3]

            else:
                experience_dict['job_title'] = job.find_element_by_tag_name(
                    "h3").text
                experience_dict['company'] = job.find_element_by_xpath(
                    './/span[@class="pv-entity__secondary-title"]').text
                experience_dict['date_range'] = (
                    job.find_element_by_xpath(
                        './/h4[@class="pv-entity__date-range t-14 t-black--light t-normal"]')
                    .text.split('\n')[1])
            experience_list.append(experience_dict)

        # Education section
        education_section = self.driver.find_element_by_id("education-section")
        education_items = education_section.find_elements_by_tag_name('li')

        education_list = []

        for study in education_items:

            degree_info_item = study.find_elements_by_xpath(
                './/div[@class="pv-entity__degree-info"]')
            if degree_info_item:
                education_dict = dict.fromkeys(
                    ['school_name', 'title_name', 'date_range'])
                degree_info = degree_info_item[0].text.split('\n')
                education_dict['school_name'] = degree_info[0]
                if len(degree_info) >= 3:
                    education_dict['title_name'] = ','.join(degree_info[1:])

                date_item = study.find_elements_by_xpath(
                    './/p[@class="pv-entity__dates t-14 t-black--light t-normal"]')
                if date_item:
                    education_dict['date_range'] = date_item[0].text.split('\n')[
                        1]
                education_list.append(education_dict)

        # Store everything in profile dictionary
        user_data['link'] = link
        user_data['name'] = name
        user_data['headline'] = headline
        user_data['description'] = description
        user_data['experience'] = experience_list
        user_data['education'] = education_list

        return user_data

    def scrape_profiles(self, profiles_links):
        '''
        Given a list of links of Linkedin profiles, this method enters
        each link and scrapes everything.
        '''
        for link in profiles_links:

            link_id = list(filter(None, link.split('/')))[-1]
            stored_profiles = os.listdir(self.results_dir)

            if '{}.json'.format(link_id) not in stored_profiles:
                user_data = self.get_profile_data(link)
                self.data.append(user_data)
                write_json(
                    user_data, '{}/{}.json'.format(self.results_dir, link_id))

    def main(self, pages):
        '''
        Method that runs the scraper a given number of pages. Currently, max number
        of pages is 100 for a non-premium linkedin account
        '''

        self.login()
        start_time = time.time()
        for page in range(1, pages+1):
            profile_links_in_page = self.get_profile_links(page)

            self.scrape_profiles(profile_links_in_page)
        end_time = time.time()
        # time to scrape x number of pages (in minutes)
        self.wall_time = (end_time - start_time)/60
        print(self.wall_time)
