import logging
import json
import pandas as pd
from pathlib import Path


def load_accounts(accounts_file: Path | str) -> list[dict] | None:
    """Load the account pool from a specified JSON file."""
    try:
        with open(accounts_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            accounts = data.get('accounts', [])
            if not accounts:
                logging.error(f"Error: No account found in {accounts_file}.")
                return None
            logging.info(f"Success: Loaded {len(accounts)} accounts.")
            return accounts
    except FileNotFoundError:
        logging.error(f"Error: Account file not found -> {accounts_file}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Error: Account file {accounts_file} has incorrect format.")
        return None


def load_login_params(path: Path | str) -> dict | None:
    """
    Load the login parameters from a specified JSON file.
    :param path: The path to the JSON file containing the login parameters. Defaults to 'login_params.json'.
    :return: A dictionary containing the login parameters or None if an error occurs.
    """
    xpath_keys ={
        "id_password_login_tab",
        "phone_num_input",
        "password_input",
        "login_button",
        "home_search_input",
        "search_result_check",
        "home_page"
    }
    url_keys = {
        "login_url",
        "homepage_url",
        "region_code_api_url",
    }
    try:
        with open(path, 'r', encoding='utf-8') as f:
            params_dict = json.load(f)
            if not xpath_keys.issubset(params_dict.get("XPaths", {}).keys()):
                logging.error(f"Error: The loaded login parameters do not contain the expected keys. Please check the file {path}.")
                return None
            if not url_keys.issubset(params_dict.get("URLs", {}).keys()):
                logging.error(f"Error: The loaded login parameters do not contain the expected URLs. Please check the file {path}.")
                return None
            logging.info(f"Successfully loaded login parameters with {len(params_dict.get('XPaths', {}))} XPaths and {len(params_dict.get('URLs', {}))} URLs.")
            return params_dict
    except FileNotFoundError:
        logging.error(f"Error: Login parameters file not found -> {path}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Error: Login parameters file {path} has incorrect format.")
        return None


def load_enterprise_list(csv_file: Path | str) -> list[str] | None:
    """Load the list of enterprises from a specified CSV file."""
    try:
        df = pd.read_csv(csv_file, header=None, encoding='utf-8')
        enterprises = df.iloc[:, 0].dropna().unique().tolist()
        logging.info(f"Successfully loaded {len(enterprises)} unique enterprise names from CSV.")
        return enterprises
    
    except FileNotFoundError:
        logging.error(f"Error: Enterprise list file not found -> {csv_file}")
        return None
    except Exception as e:
        logging.error(f"Error occurred while reading the CSV file: {e}")
        return None