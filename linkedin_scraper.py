

import time
import numpy as np
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

'''
CURRENTLY I HAVE 2 ERRORS: 
1) NOT ALL LINKS ARE LOADING.
2) NOT SCRAPING EXPERIENCES WITH GROUPS FOR THE SAME COMPANY 
'''
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

    def login(self):
        '''
        This method enters linkedin with a given username and password
        '''
        self.driver.get("https://linkedin.com")
        username_item = self.driver.find_element_by_xpath('//input[@id="login-email"]')
        password_item = self.driver.find_element_by_xpath('//input[@id="login-password"]')
        username_item.send_keys(self.username)
        password_item.send_keys(self.password)
        self.driver.find_element_by_xpath('//input[@class="login submit-button"]').click()

    def url_location_mapper(self):
        '''
        Method that maps a location like "Colombia" to the corresponding code that
        needs to be inserted in the linkedin url in order to see only results of 
        people in colombia.
        '''
        mapping = {"Colombia":"co"}
        return mapping[self.location]

    def infinite_scroller(self):
        '''
        This function is used to scroll down to the bottom of a page with
        infinite scrolling
        '''
        SCROLL_PAUSE_TIME = 0.5

        # Get scroll height
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while True:
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Wait to load page
            time.sleep(SCROLL_PAUSE_TIME)

            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def get_profile_links(self, page):
        '''
        Given a keyword, location and a page number (of the total number of pages),
        this method returns the links of the profiles found in that page.
        '''


        mapped_location = self.url_location_mapper()
        search_url = "https://www.linkedin.com/search/results/people/?facetGeoRegion=%5B%22{}%3A0%22%5D&keywords={}&origin=FACETED_SEARCH&page={}".\
                     format(mapped_location, self.keyword, page)
        self.driver.get(search_url)

        #Load all page by scrolling to bottom
        self.infinite_scroller()
        
        time.sleep(5)

        profile_links_items = WebDriverWait(self.driver,10).until(
                              EC.presence_of_all_elements_located((
                              By.XPATH,'//a[@class="search-result__result-link ember-view"]')))
        
        #We extract all profile links. We use set to ensure there are no duplicates
        profile_links = list(set([profile.get_attribute('href') for profile in profile_links_items]))

        return profile_links

    def expand_all(self):
        '''
        There are many elements in a linkedin profile were you need to click on a 
        "show more" button in order to see full information. This method clicks on
        all buttons needed so everything is expanded and full info is available.
        '''
        #First we need to scroll down to completely load the page
        self.infinite_scroller()        

        #Last thing to load on a linkedin page is the interests box
        #So we know page if loaded when we can find this element. 
        WebDriverWait(self.driver,10).until(
                              EC.presence_of_element_located((
                              By.XPATH,'//section[@class="pv-profile-section pv-interests-section artdeco-container-card ember-view"]')))
        time.sleep(3)
        
        #Expand description box
        try:
            WebDriverWait(self.driver,10).until(
                                EC.element_to_be_clickable((
                                By.XPATH,'//li-icon[@class="pv-top-card-section__summary-toggle-button-icon"]'))).click()
        except TimeoutException:
            pass

        #Expand everythin else: Exeperience, education, etc...  

        while True:
            try:
                WebDriverWait(self.driver,5).until(
                                    EC.element_to_be_clickable((
                                    By.XPATH,'//li-icon[@class="pv-profile-section__toggle-detail-icon" and contains(@type,"chevron-down-icon")]'))).click() 
            except TimeoutException:
                break

        #Expand skills section
        try:
            self.driver.find_element_by_xpath(
                    '//li-icon[@class="pv-skills-section__chevron-icon"]').click()
        except EC.NoSuchElementException:
            pass


    def get_profile_data(self, profile_link):
        '''
        This function scrapes relevant data of a profile given its profile linke
        '''

        #Enter the profile link
        self.driver.get(profile_link)

        #We expand everything we need to scrape
        self.expand_all()

        #Create dictionary conatining user data
        user_data = dict.fromkeys(['link','name','headline','description',
                                 'experience','education','aptitudes'])                                 
        link = profile_link
        name = self.driver.find_element_by_xpath(
            '//h1[@class="pv-top-card-section__name inline t-24 t-black t-normal"]').text
        headline = self.driver.find_element_by_xpath(
        '//h2[@class="pv-top-card-section__headline mt1 t-18 t-black t-normal"]').text
        description = self.driver.find_element_by_xpath(
            '//div[@class="pv-top-card-section__summary pv-top-card-section__summary--with-content mt4 ember-view"]').find_element_by_tag_name('p').text

        #Experience section
        experience_section = self.driver.find_element_by_id("experience-section") 

        experience_items = experience_section.find_elements_by_xpath(('.//div[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]')) + experience_section.find_elements_by_xpath(
            ('.//li[@class="pv-profile-section__sortable-item pv-profile-section__section-info-item relative pv-profile-section__list-item sortable-item ember-view"]'))

        experience_list = []

        for job in experience_items:
            experience_dict = dict.fromkeys(['job_title','company','date_range'])
            experience_dict['job_title'] = job.find_element_by_tag_name("h3").text
            experience_dict['company'] = job.find_element_by_xpath('.//span[@class="pv-entity__secondary-title"]').text
            experience_dict['date_range'] = job.find_element_by_xpath('.//h4[@class="pv-entity__date-range t-14 t-black--light t-normal"]').text.split('\n')[1]
            experience_list.append(experience_dict)


        #Education section
        education_section = self.driver.find_element_by_id("education-section") 
        education_items = education_section.find_elements_by_tag_name('li')

        education_list = []

        for study in education_items:
            education_dict = dict.fromkeys(['school_name','title_name','date_range'])
            degree_info=study.find_element_by_xpath('.//div[@class="pv-entity__degree-info"]').text.split('\n')
            education_dict['school_name'] = degree_info[0]
            education_dict['title_name'] = degree_info[2]
            education_dict['date_range'] = study.find_element_by_xpath('.//p[@class="pv-entity__dates t-14 t-black--light t-normal"]').text.split('\n')[1]
            education_list.append(education_dict)
        
        #Store everything in profile dictionary
        user_data['link'] = link
        user_data['name'] = name
        user_data['headline'] = headline
        user_data['description'] = description
        user_data['experience'] = experience_list
        user_data['education'] = education_list

        return user_data



    def scrape_profiles(self,profiles_links):
        '''
        Given a list of links of Linkedin profiles, this method enters
        each link and scrapes everything.
        '''
        for link in profiles_links:

            user_data = self.get_profile_data(link)
            self.data.append(user_data)


    def main(self,pages):

        self.login()
        for page in range(pages+1):
            profile_links_in_page = self.get_profile_links(page)
            
            self.scrape_profiles(profile_links_in_page)

            
            





