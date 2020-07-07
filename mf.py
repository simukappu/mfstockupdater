from logzero import logger
import logzero

import selenium 
from selenium import webdriver 
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

import requests

import os, time, datetime
import imaplib, email, re, pyotp, pytz

class MoneyForward():
    def init(self):
        logger.info("selenium initializing...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280x3200")
        options.add_argument("--disable-application-cache")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-sandbox")
        options.add_argument("--hide-scrollbars")
        options.add_argument("--v=99")
        options.add_argument("--single-process")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--homedir=/tmp")
        options.add_argument('--user-agent=Mozilla/5.0')
        options.add_experimental_option("prefs", {'profile.managed_default_content_settings.images':2})
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 5)
        if not 'ALPHAVANTAGE_API_KEY' in os.environ:
            raise ValueError("env ALPHAVANTAGE_API_KEY is not found.")
        self.alphavantage_apikey = os.environ['ALPHAVANTAGE_API_KEY']

    def login(self):
        self.driver.execute_script("window.open()")
        if not 'MF_ID' in os.environ or not 'MF_PASS' in os.environ:
            raise ValueError("env MF_ID and/or MF_PASS are not found.")
        mf_id = os.environ['MF_ID']
        mf_pass = os.environ['MF_PASS']

        self.driver.get('https://moneyforward.com/')
        self.wait.until(ec.presence_of_all_elements_located)
        self.driver.find_element_by_xpath('//*[@href="/sign_in"]').click()
        self.wait.until(ec.presence_of_all_elements_located)
        self.driver.get(self.driver.current_url.replace('/sign_in/new', '/sign_in/email'))
        self.wait.until(ec.presence_of_all_elements_located)

        login_time = datetime.datetime.now(pytz.timezone('Asia/Tokyo'))
        self.send_to_element('//*[@type="email"]', mf_id)
        self.driver.find_element_by_xpath('//*[@type="submit"]').click()
        self.wait.until(ec.presence_of_all_elements_located)
        self.send_to_element('//*[@type="password"]', mf_pass)
        self.driver.find_element_by_xpath('//*[@type="submit"]').click()
        self.wait.until(ec.presence_of_all_elements_located)

        if self.driver.find_elements_by_class_name("me-home"):
            logger.info("successfully logged in.")
        # MoneyForward two step verifications
        elif self.driver.current_url.startswith('https://id.moneyforward.com/two_factor_auth/totp'):
            self.confirm_two_step_verification_param()
            if os.environ['MF_TWO_STEP_VERIFICATION'].lower() == "totp":
                confirmation_code = self.get_confirmation_code_from_totp()
            else:
                raise ValueError("unsupported two step verification is found. check your env MF_TWO_STEP_VERIFICATION.")
            self.send_to_element('//*[@name="otp_attempt"]', confirmation_code)
            self.driver.find_element_by_xpath('//*[@type="submit"]').click()
            self.wait.until(ec.presence_of_all_elements_located)
            if self.driver.find_elements_by_class_name("me-home"):
                logger.info("successfully logged in.")
            else:
                raise ValueError("failed to log in.")
        else:
            raise ValueError("failed to log in.")

    def portfolio(self):
        # Get current exchange rate
        usdrate = self.usdrate()
        logger.info("USDJPY: " + str(usdrate))

        # Get personal stock assets list
        self.driver.get('https://moneyforward.com/personal_assets/4')
        self.wait.until(ec.presence_of_all_elements_located)
        elements = self.driver.find_elements_by_xpath('//table[@class="mdc-data-table__table"]/tbody/tr')
        asset_list = []
        for tr in elements:
            tds = tr.find_elements_by_tag_name('td')
            name = tds[0].text
            if name[0:1] == "#":
                asset_url = tds[7].get_attribute('data-asset-request-url')
                asset_list.append((name, asset_url))

        # Update stock assets value
        self.stock_price_dict = {}
        for asset in asset_list:
            name = asset[0]
            asset_url = asset[1]
            entry = name.split('-')
            stock_price = self.stock_price(entry[1])
            stock_count = int(entry[2])
            logger.info(entry[0] + ": " + entry[1] + ' is ' + str(stock_price) + " USD (" + str(int(usdrate * stock_price)) + " JPY) x " + str(stock_count))
            self.driver.get('https://moneyforward.com/' + asset_url + '/edit')
            self.wait.until(ec.presence_of_all_elements_located)
            det_value = self.driver.find_element_by_id('manual_assets_value')
            submit = self.driver.find_element_by_name('button')
            time.sleep(1)
            self.send_to_element_direct(det_value, str(int(usdrate * stock_price) * stock_count))
            submit.click()
            time.sleep(1)
            logger.info(entry[0] + " is updated.")

    def stock_price(self, tick):
        if tick not in self.stock_price_dict:
          r = requests.get(f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={tick}&apikey={self.alphavantage_apikey}')
          if r.status_code != 200:
              raise ConnectionRefusedError()
          data = r.json()
          self.stock_price_dict[tick] = float(data['Global Quote']['05. price'])
        return self.stock_price_dict[tick]

    def usdrate(self):
        r = requests.get(f'https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=USD&to_currency=JPY&apikey={self.alphavantage_apikey}')
        if r.status_code != 200:
            raise ConnectionRefusedError()
        data = r.json()
        return float(data['Realtime Currency Exchange Rate']['5. Exchange Rate'])

    def close(self):
        try:
            self.driver.close()
        except:
            logger.debug("Ignore exception (close)")
        try:
            self.driver.quit()
        except:
            logger.debug("Ignore exception (quit)")


################## Two step verification ###################

    def confirm_two_step_verification_param(self):
        logger.info("two step verification is enabled.")
        if not 'MF_TWO_STEP_VERIFICATION' in os.environ:
            raise ValueError("env MF_TWO_STEP_VERIFICATION is not found.")

    def get_confirmation_code_from_totp(self):
        if not 'MF_TWO_STEP_VERIFICATION_TOTP_SECRET_KEY' in os.environ:
            raise ValueError("env MF_TWO_STEP_VERIFICATION_TOTP_SECRET_KEY are not found.")
        confirmation_code = pyotp.TOTP(os.getenv("MF_TWO_STEP_VERIFICATION_TOTP_SECRET_KEY")).now()
        return confirmation_code

############################################################

    def print_html(self):
        html = self.driver.execute_script("return document.getElementsByTagName('html')[0].innerHTML")
        print(html)

    def send_to_element(self, xpath, keys):
        element = self.driver.find_element_by_xpath(xpath)
        element.clear()
        logger.debug("[send_to_element] " + xpath)
        element.send_keys(keys)

    def send_to_element_direct(self, element, keys):
        element.clear()
        logger.debug("[send_to_element] " + element.get_attribute('id'))
        element.send_keys(keys)

if __name__ == "__main__":
    if "LOG_LEVEL" in os.environ:
        logzero.loglevel(int(os.environ["LOG_LEVEL"]))
    mf = MoneyForward()
    try:
        mf.init()
        mf.login()
        mf.portfolio()
    finally:
        mf.close()
