import logging
import json
import traceback
import time
import random
import pandas as pd
from pathlib import Path
from src.read import load_accounts, load_login_params, load_enterprise_list
from src.scraper import Scraper


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

    # Load enterprise list
    enterprises = load_enterprise_list('queries/enterprises.csv')
    if not enterprises:
        logging.error("Failed to load enterprise list. Exiting.")
        exit(1)
    
    enterprises_cnt = len(enterprises)
    
    if not accounts or not login_params or not enterprises:
        logging.error("One or more critical resources failed to load. Please check the logs for details.")
        exit(1)

    # Create an empty dict to store all extracted data
    all_extracted_data = {}

    scraper = Scraper(login_params["URLs"]["homepage_url"], silent=True)
    while accounts:
        try:
            scraper.get_authenticated_session(
                phone_num=accounts[0]['phone'],
                password=accounts[0]['password'],
                search_term=enterprises[0],
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

    while enterprises:
        current_query = enterprises[0]
        logging.info(f"Starting processing for enterprise: '{current_query}'")
        try:
            logging.info("="*50)
            logging.info(f"Process: [{enterprises_cnt - len(enterprises) + 1}/{enterprises_cnt}] | Account: {accounts[0]['phone']}")
            logging.info(f"Target: '{current_query}'")
            logging.info("="*50)

            enterprise_details = scraper.search_enterprise(current_query)
            if enterprise_details is None:
                logging.warning(f"Search API did not return results for '{current_query}'. Skipping this enterprise.")
                enterprises.pop(0)
                continue

            basic_info = scraper.get_info(enterprise_details["code"], enterprise_details["name"])
            logging.info(f"Successfully retrieved information for '{current_query}'. Extracting data...")
            # json.dump(basic_info, open(f"debug_info/{current_query}_basic_info.json", "w", encoding="utf-8"), ensure_ascii=False, indent=4)
            all_extracted_data[current_query] = basic_info
            enterprises.pop(0)
        
        except Exception as e:
            logging.error(f"An unexpected error occurred during scraping for '{current_query}': {e}")
            error_message = traceback.format_exc()
            logging.error(f"{error_message}")
            logging.info("To avoid deadlock, removing the current query from the pool and trying the next one.")
            enterprises.pop(0)
            time.sleep(5)

    print("\n\n" + "#"*60)
    print("Scraping process completed.")
    scraper.driver.quit()
    if not enterprises:
        print("All enterprises in the list have been processed. Program ended.")
    else:
        print(f"Remaining enterprises that were not processed: {enterprises}")
    print("#"*60)
    json.dump(all_extracted_data, open("output/extracted_data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=4)
    # print(f"已爬取的公司代码列表: {code_dict}")


if __name__ == "__main__":
    main()