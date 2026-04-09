import os
import logging
import json
import traceback
import time
import pandas as pd
import requests
from src.read import load_accounts, load_login_params, load_enterprise_list
from src.scraper import Scraper


def get_region_dict(base_url: str, pagesize: int=500) -> dict:
    if os.path.exists("src/region_dict.json"):
        with open("src/region_dict.json", "r", encoding="utf-8") as f:
            return json.load(f)

    region_dict = {}
    params = {
        "pageNum": 1,
        "pageSize": pagesize,
    }
    try:
        total_code = requests.get(base_url, params=params, timeout=15).json()
        data = total_code.get("data", {})
        for province in data:
            region_dict[province["name"]] = province["code"] + "0000"
            for city in province['children']:
                region_dict[city["name"]] = city["code"] + "00"
                for district in city['children']:
                    region_dict[district["name"]] = district["code"]
        logging.info(f"Successfully retrieved {len(region_dict)} region codes from API.")
        json.dump(region_dict, open("src/region_dict.json", "w", encoding="utf-8"), ensure_ascii=False, indent=4)

    except requests.RequestException as e:
        logging.error(f"Failed to retrieve region codes from API: {e}")
    
    return region_dict

def main():
    # Set up logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("log.txt", mode='w', encoding='utf-8')
        ]
    )
    logging.info("This will be logged both to the console and a log file.")

    # Load account pool
    accounts = load_accounts('accounts.json')
    if not accounts:
        logging.error("Failed to load accounts. Exiting.")
        exit(1)

    # Load login parameters
    login_params = load_login_params('src/login_params.json')
    if not login_params:
        logging.error("Failed to load login parameters. Exiting.")
        exit(1)

    # Load region list
    regions = load_enterprise_list('queries/regions.csv')
    if not regions:
        logging.error("Failed to load region list. Exiting.")
        exit(1)
    
    regions_cnt = len(regions)
    
    if not accounts or not login_params or not regions:
        logging.error("One or more critical resources failed to load. Please check the logs for details.")
        exit(1)
    
    region_dict = get_region_dict(login_params["URLs"]["region_code_api_url"])
    if len(region_dict) == 0:
        logging.error("Failed to load region codes. Exiting.")
        exit(1)

    # Create an empty dict to store all extracted data
    all_extracted_data = {}

    scraper = Scraper(login_params["URLs"]["homepage_url"], silent=True)
    while accounts:
        try:
            scraper.get_authenticated_session(
                phone_num=accounts[0]['phone'],
                password=accounts[0]['password'],
                search_term=regions[0],
                login_params=login_params,
            )
            if not scraper.base_headers:
                logging.error(f"Authentication failed for account {accounts[0]['phone']}. Removing from pool.")
                accounts.pop(0)
                if not accounts:
                    logging.error("No more accounts available in the pool. Exiting.")
                    exit(1)
            else:
                break  # Exit the loop if authentication is successful
        except Exception as e:
            logging.warning(f"An error occurred during authentication for account {accounts[0]['phone']}: {e}")

    logging.info(f"Authentication successful for account {accounts[0]['phone']}.")

    while regions:
        current_query = regions[0]
        logging.info(f"Starting processing for region: '{current_query}'")
        try:
            logging.info("="*50)
            logging.info(f"Process: [{regions_cnt - len(regions) + 1}/{regions_cnt}] | Account: {accounts[0]['phone']}")
            logging.info(f"Target: '{current_query}', Region Code: {region_dict.get(current_query, 'N/A')}")
            logging.info("="*50)

            if scraper.open_region_page(region_dict.get(current_query, 'N/A'), current_query) is False:
                logging.warning(f"Failed to load region page for '{current_query}'. Skipping this region.")
                regions.pop(0)
                continue

            region_economy_info = scraper.extract_region_economy_info(current_query)
            logging.info(f"Successfully retrieved information for '{current_query}'. Extracting data...")
            df_data = pd.DataFrame.from_dict(region_economy_info, orient='index')
            df_data.to_csv(f"output/{current_query}_region_economy_info.csv", encoding="utf-8-sig")

            regions.pop(0)
        
        except Exception as e:
            logging.error(f"An unexpected error occurred during scraping for '{current_query}': {e}")
            error_message = traceback.format_exc()
            logging.error(f"{error_message}")
            logging.info("To avoid deadlock, removing the current query from the pool and trying the next one.")
            regions.pop(0)
            time.sleep(5)

    print("\n\n" + "#"*60)
    print("Scraping process completed.")
    scraper.driver.quit()
    if not regions:
        print("All regions in the list have been processed. Program ended.")
    else:
        print(f"Remaining regions that were not processed: {regions}")
    print("#"*60)

if __name__ == "__main__":
    main()