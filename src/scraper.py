import json
import logging
import requests
import time
from urllib.parse import quote
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class TokenExpiredException(Exception):
    """Custom exception to indicate that the authentication token has expired."""
    pass


class RateLimitException(Exception):
    """Custom exception to indicate that the account is rate limited."""
    pass


class Scraper():
    """Interface for scraping data from the QYYJT platform using authenticated sessions."""
    def __init__(self, referer: str, silent: bool=True):
        self.referer = referer
        self.silent = silent
        self.token_name = None
        self.token_value = None
        self.user_id = None
        self.cookies = None
        self.base_headers = {}

        options = Options()
        if self.silent is True:
            options.add_argument('--headless')
        else:
            options.add_argument("--start-maximized")

        self.driver = WebDriver(
            service=ChromeService(ChromeDriverManager().install()),
            options=options
        )

    def _check_response_for_errors(self, response_data: dict):
        """Check if the API response contains errors that require special handling, such as rate limiting or token expiration."""
        info = response_data.get('info', '')
        return_code = response_data.get('returncode')

        # Check for token expiration
        if return_code == 104 and "token过时" in info:
            raise TokenExpiredException(f"Token has expired (Code: 104): {info}")

        # Check for API rate limiting, using returncode == 206 as a more reliable indicator
        # Also check if the info text contains "请求过多" for extra safety
        if return_code == 206 and "请求过多" in info:
            raise RateLimitException(f"Account is rate limited (Code: 206): {info}")
    
    def get_authenticated_session(
            self,
            phone_num: str,
            password: str,
            search_term: str,
            login_params: dict
        ):
        """Simulate login and search, then correctly extract the user ID from 'u_info' in localStorage."""
        logging.info(f"[{phone_num}] Login simulating...")

        try:
            self.driver.get(login_params["URLs"]["login_url"])
            wait = WebDriverWait(self.driver, 10)

            # Login and simulate searching
            logging.info(f"[{phone_num}] Waiting for the 'ID and Password Login' tab...")
            login_switch = wait.until(
                EC.element_to_be_clickable((By.XPATH, login_params["XPaths"]["id_password_login_tab"]))
            )
            login_switch.click()
            logging.info(f"[{phone_num}] Switched to 'ID and Password Login'.")
            
            phone_num_input_tab = wait.until(
                EC.visibility_of_element_located((By.XPATH, login_params["XPaths"]["phone_num_input"]))
            )
            password_input_tab = self.driver.find_element(By.XPATH, login_params["XPaths"]["password_input"])

            phone_num_input_tab.clear()
            password_input_tab.clear()
            phone_num_input_tab.send_keys(phone_num)
            password_input_tab.send_keys(password)
            
            logging.info(f"[{phone_num}] ID and password entered.")
            self.driver.find_element(By.XPATH, login_params["XPaths"]["login_button"]).click()
            logging.info(f"[{phone_num}] Clicked the login button.")
            logging.info(f"[{phone_num}] Waiting for login to redirect to homepage...")

            home_search_input = wait.until(
                EC.visibility_of_element_located((By.XPATH, login_params["XPaths"]["home_search_input"]))
            )

            logging.info(f"[{phone_num}] Login successful! Redirected to homepage.")
            logging.info(f"[{phone_num}] Simulating search: '{search_term}'...")
            home_search_input.send_keys(search_term)
            home_search_input.send_keys(Keys.RETURN)
            logging.info(f"[{phone_num}] Waiting for search results page to load...")
            wait.until(EC.presence_of_element_located((By.XPATH, login_params["XPaths"]["search_result_check"])))
            logging.info(f"[{phone_num}] Search results page loaded successfully!")
            time.sleep(2)

            logging.info(f"[{phone_num}] Collecting authentication info from localStorage...")
            
            auth_token = self.driver.execute_script("return window.localStorage.getItem('s_tk');")
            if not auth_token:
                raise ValueError("Can't find 's_tk' token in localStorage.")

            u_info_str = self.driver.execute_script("return window.localStorage.getItem('u_info');")
            if not u_info_str:
                raise ValueError("Can't find 'u_info' object in localStorage.")
            
            u_info_obj = json.loads(u_info_str)
            user_id = u_info_obj.get('user')

            if not user_id:
                raise ValueError("Can't find 'user' key in 'u_info' object.")

            auth_token = auth_token.strip('"')
            user_id = user_id.strip('"')

            token_header_name = "pcuss"
            token_value = auth_token

            cookies = {cookie['name']: cookie['value'] for cookie in self.driver.get_cookies()}
            logging.info(f"[{phone_num}] Successfully extracted authentication Token (s_tk): {token_value[:15]}...")
            logging.info(f"[{phone_num}] Successfully extracted User ID (user): {user_id[:15]}...")

            # Save token and cookies to class attributes
            self.token_name = token_header_name
            self.token_value = token_value
            self.user_id = user_id
            self.cookies = cookies

            self.base_headers = {
                'accept': 'application/json, text/plain, */*',
                'client': 'pc-web;pro',
                self.token_name: self.token_value,
                'user': self.user_id,
                'terminal': 'pc-web;pro',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'referer': self.referer
            }
            return None

        except TimeoutException as e:
            logging.error(f"[{phone_num}] Operation timeout: Error occurred while waiting for element. {e}")
            self.driver.save_screenshot("login_error_timeout.png")
            return None

        except Exception as e:
            logging.error(f"[{phone_num}] Error occurred during login or simulated search: {e}")
            self.driver.save_screenshot("login_error_final.png")
            return None

    def search(self, search_term: str) -> dict | None:
        """Search for an term using the QYYJT API and return the search results."""
        logging.info(f"Searching for term: '{search_term}'...")
        
        params = {
            'pagesize': 10,
            'skip': 0,
            'text': search_term,
            'template': 'list',
            'isRelationSearch': 0
        }
        headers = self.base_headers.copy()
        encoded_search_term = quote(search_term)
        headers['referer'] = f'https://www.qyyjt.cn/search?text={encoded_search_term}'
        try:
            response = requests.get(
                "https://www.qyyjt.cn/finchinaAPP/v1/finchina-search/v1/multipleSearch",
                headers=headers,
                params=params,
                cookies=self.cookies,
            )
            response.raise_for_status()
            response_data = response.json()
            self._check_response_for_errors(response_data)
            # json.dump(response_data, open("search_response_debug.json", "w", encoding="utf-8"), ensure_ascii=False, indent=4)
            if response_data.get('returncode') == 0 and response_data.get('data') and response_data['data'].get('list'):
                if not response_data['data']['list']:
                    logging.info(f"Search for '{search_term}' succeeded but returned no results.")
                    return None
                
                info = response_data['data']['list'][0]
                code = info.get('code', 'N/A')
                name = info.get('name', 'N/A')
                logging.info(f"Search for '{search_term}' succeeded. Found enterprise: {name} (Code: {code})")
                return {'code': code, 'name': name}
            else:
                error_msg = response_data.get('info', response_data.get('message', '未知错误'))
                logging.error(f"Search for '{search_term}' failed. API returned error: {error_msg}")
                return None

        except requests.RequestException as e:
            print(f"Error occurred while searching for '{search_term}': {e}")
            return None

    def open_enterprise_page(self, enterprise_code: str, enterprise_name: str, loading_time: float=5.0) -> bool:
        self.driver.get(f"https://www.qyyjt.cn/detail/enterprise/overview?code={enterprise_code}&type=company")
        time.sleep(loading_time)   # Waiting for the page to load completely, including any dynamic content

        if self.driver.page_source is None or "无法访问此网站" in self.driver.page_source:
            self.driver.save_screenshot(f"page_load_error_{enterprise_name}.png")
            logging.error(f"Failed to load enterprise page for '{enterprise_name}' (Code: {enterprise_code}). Screenshot saved.")
            return False
        
        logging.info(f"Successfully loaded enterprise page for '{enterprise_name}' (Code: {enterprise_code}).")
        return True

    def get_enterprise_basic_info(self, enterprise_name: str) -> dict | None:
        with open("src/query_keys.json", "r", encoding="utf-8") as f:
            query_keys = json.load(f)
        enterprise_basic_info_keys = query_keys.get("enterprise_basic_info", {})

        logging.info(f"Collecting basic information for enterprise '{enterprise_name}'...")
        try:
            basic_info = {}
            basic_info["企业名称"] = self.driver.find_element(By.XPATH, "//span[@class='copy-val name']").text.strip()
            
            for basic_info_key in enterprise_basic_info_keys:
                target_element = self.driver.find_element(By.XPATH, enterprise_basic_info_keys[basic_info_key])
                if target_element is None:
                    logging.warning(f"Failed to find element for '{basic_info_key}' in enterprise '{enterprise_name}'.")
                    basic_info[basic_info_key] = "N/A"
                    continue

                try:
                    value = target_element.find_element(By.XPATH, "./following::span").text.strip()
                    basic_info[basic_info_key] = value if value else "N/A"
                
                except Exception as e:
                    logging.warning(f"Failed to find element for '{basic_info_key}' in enterprise '{enterprise_name}'.")
                    basic_info[basic_info_key] = "N/A"
        
            return basic_info

        except requests.RequestException as e:
            print(f"Request failed while getting info for enterprise  '{enterprise_name}': {e}")
            return None
    
    def get_ownership_penetration_chart(self, enterprise_name: str):
        try:
            wait = WebDriverWait(self.driver, 10)
            chart_tab_locator = (
                By.CSS_SELECTOR,
                'li[role="menuitem"][title="股权穿透图"]'
            )
            chart_tab = wait.until(EC.element_to_be_clickable(chart_tab_locator))
            chart_tab.click()
            logging.info(f"Clicked on '股权穿透图' tab for enterprise '{enterprise_name}'. Waiting for the chart to load...")
            time.sleep(5)

            max_rounds = 10
            expandable = []

            for _ in range(max_rounds):
                node_expands = self.driver.find_elements(By.XPATH, "//*[local-name()='g' and contains(@class, 'node-expand') and contains(@cursor, 'pointer') and contains(@visibility, 'visible')]')")
                for node in node_expands:
                    logging.info(node)
                    vertical_lines = node.find_elements(
                        By.XPATH,
                        ".//*[local-name()='line' and contains(@class, 'vertical-line') and contains(@visibility, 'visible')]"
                    )
                    
                    if vertical_lines:
                        expandable.append(node)
                
                if expandable:
                    for node in expandable:
                        node.click()
                        time.sleep(1)  # Wait for the expansion to complete
                else:
                    break  # No more expandable nodes, exit the loop
            
            logging.info(f"Full ownership penetration chart for enterprise '{enterprise_name}' loaded successfully.")
            output_button = self.driver.find_element(By.XPATH, "//div[@class='style__Button-liBBGb cwnyzm btn' and text()='导出图片']")
            output_button.click()

            time.sleep(2)
        
        except Exception as e:
            logging.warning(f"Failed to find or click the '股权穿透图' menu for enterprise '{enterprise_name}': {e}")
            return None
    
    def open_region_page(self, region_code: str, region_name: str, loading_time: float=5.0) -> bool:
        self.driver.get(f"https://www.qyyjt.cn/{region_code}/area/regionEconomy")
        time.sleep(loading_time)   # Waiting for the page to load completely, including any dynamic content

        if self.driver.page_source is None or "无法访问此网站" in self.driver.page_source:
            self.driver.save_screenshot(f"page_load_error_{region_name}.png")
            logging.error(f"Failed to load region page for '{region_name}'. Screenshot saved.")
            return False
        
        logging.info(f"Successfully loaded region page for '{region_name}'.")
        return True

    def extract_region_economy_info(self, region_name: str, year_range: int=3) -> dict | None:
        with open("src/query_keys.json", "r", encoding="utf-8") as f:
            query_keys = json.load(f)
        region_info_keys = query_keys.get("region_economy_info", {})
        logging.info(f"Collecting economy information for region '{region_name}'...")

        try:
            region_economy_info = {}
            current_year_element = self.driver.find_element(By.XPATH, "//span[contains(text(), '年经济预期目标')]")
            if current_year_element:
                current_year = int(current_year_element.text.strip()[:4])
            else:
                logging.warning(f"Failed to find '年经济预期目标' for region '{region_name}'.")
                current_year = int(time.localtime().tm_year)
            
            for region_info_key in region_info_keys:
                try:
                    target = self.driver.find_element(By.XPATH, region_info_keys[region_info_key])
                    if target is None:
                        logging.warning(f"Failed to find element for '{region_info_key}' in region '{region_name}'.")
                        region_economy_info[region_info_key] = {str(current_year - i - 1): 'N/A' for i in range(year_range)}
                        continue

                    value_elements = target.find_elements(By.XPATH, "./following::td[contains(@style, 'text-align: right;')][position()<=6]")
                    values = [value_element.text.strip() for value_element in value_elements if value_element.text.strip()]
                    region_economy_info[region_info_key] = {str(current_year - i - 1): values[i + 1] for i in range(year_range)}  # Default to 'N/A'
                
                except Exception as e:
                    logging.warning(f"Failed to find element for '{region_info_key}' in region '{region_name}'.")
                    region_economy_info[region_info_key] = {str(current_year - i - 1): 'N/A' for i in range(year_range)}
        
            return region_economy_info

        except requests.RequestException as e:
            logging.error(f"Request failed while getting info for region  '{region_name}': {e}")

        return None
    
    def extract_municipal_bond_info(self, region_name: str) -> dict | None:
        wait = WebDriverWait(self.driver, 10)
        with open("src/query_keys.json", "r", encoding="utf-8") as f:
            query_keys = json.load(f)
        municipal_bond_info_keys = query_keys.get("region_municipal_bond_info", {})
        logging.info(f"Collecting municipal bond information for region '{region_name}'...")

        municipal_bond_info = {}

        try:
            clicker0 = wait.until(
                EC.visibility_of_element_located((By.XPATH, "//li[@title='城投平台']"))
            )
            clicker0.click()

            clicker1 = wait.until(
                EC.visibility_of_element_located((By.XPATH, "//span[contains(text(), '本级')]/preceding::span[@class='ant-radio']"))
            )
            clicker1.click()

            time.sleep(2)
            target_element = self.driver.find_elements(By.XPATH, "//tr[@aria-hidden='true' and @class='ant-table-measure-row']")[0]
            value_elements = target_element.find_elements(By.XPATH, "./following-sibling::tr")
            for i, value_element in enumerate(value_elements):
                current_municipal_bond_info = {}
                current_municipal_bond_info['企业名称'] = value_element.get_attribute('data-row-key')
                children_elements = value_element.find_elements(By.XPATH, "./*")
                for key in municipal_bond_info_keys:
                    current_municipal_bond_info[key] = children_elements[municipal_bond_info_keys[key]].text.strip()
                municipal_bond_info[str(i + 1)] = current_municipal_bond_info
            
            return municipal_bond_info

        except Exception as e:
            logging.warning(f"Failed to find or click the '城投平台' menu for region '{region_name}': {e}")
            return None