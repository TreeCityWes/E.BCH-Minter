import os
import time
import logging
import requests
from web3 import Web3, HTTPProvider
from dotenv import load_dotenv
from colorlog import ColoredFormatter

load_dotenv()

pulsechain_rpc_url = os.getenv('PULSECHAIN_RPC_URL')
erc20_contract_address = os.getenv('ERC20_CONTRACT_ADDRESS')
main_wallet_address = os.getenv('MAIN_WALLET_ADDRESS')
main_wallet_private_key = os.getenv('MAIN_WALLET_PRIVATE_KEY')

w3 = Web3(HTTPProvider(pulsechain_rpc_url))
if not w3.is_connected():
    logging.error("Failed to connect to PulseChain.")
    exit()

erc20_contract_abi = [
    {
        "inputs": [],
        "name": "mint",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "to",
                "type": "address"
            },
            {
                "internalType": "uint256",
                "name": "value",
                "type": "uint256"
            }
        ],
        "name": "transfer",
        "outputs": [
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "account",
                "type": "address"
            }
        ],
        "name": "balanceOf",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

erc20_contract = w3.eth.contract(address=erc20_contract_address, abi=erc20_contract_abi)

def fetch_token_balances():
    try:
        ebch_balance_raw = erc20_contract.functions.balanceOf(main_wallet_address).call()
        ebch_balance = ebch_balance_raw / 10**18
        pls_balance_raw = w3.eth.get_balance(main_wallet_address)
        pls_balance = pls_balance_raw / 10**18
        token_balances = [("E.BCH", ebch_balance), ("PLS", pls_balance)]
        return token_balances
    except Exception as e:
        logging.error(f"Failed to fetch token balances: {e}")

def wait_for_new_block():
    api_url = "https://api.scan.pulsechain.com/api?module=block&action=eth_block_number"
    last_block = w3.eth.block_number
    logging.info(f"Current block: \033[36m{last_block}\033[0m. Waiting for a new block...")  # Cyan color for block number
    while True:
        try:
            response = requests.get(api_url)
            if response.status_code == 200:
                new_block = int(response.json()["result"], 16)
                if new_block > last_block:
                    logging.info(f"New block detected: \033[36m{new_block}\033[0m")  # Cyan color for new block
                    return new_block
                else:
                    logging.debug(f"Current block: \033[36m{last_block}\033[0m. Waiting for a new block...")  # Cyan color for current block
            else:
                logging.warning(f"Failed to fetch the current block number. Status code: {response.status_code}")
            time.sleep(1)
        except Exception as e:
            logging.error(f"Error while fetching the current block: {e}")
            time.sleep(1)

def fetch_gas_prices():
    api_url = "https://beacon.pulsechain.com/api/v1/execution/gasnow"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            gas_prices_data = response.json()['data']
            converted_gas_prices = {
                "rapid": int(gas_prices_data['rapid'] / 1e9),
                "fast": int(gas_prices_data['fast'] / 1e9),
                "standard": int(gas_prices_data['standard'] / 1e9),
                "slow": int(gas_prices_data['slow'] / 1e9)
            }
            return converted_gas_prices
        else:
            logging.error(f"API call unsuccessful with status code {response.status_code}.")
            return None
    except Exception as e:
        logging.error(f"Failed to fetch gas prices: {e}")
        return None

def calculate_gas_fee(gas_limit, base_fee, tip):
    return gas_limit * (base_fee + tip)

def mint_tokens(gas_price):
    try:
        nonce = w3.eth.get_transaction_count(main_wallet_address)
        base_fee = 6901070
        tip = 1.5
        gas_limit = 300000
        gas_fee = calculate_gas_fee(gas_limit, base_fee, tip)
        txn = {
            'nonce': nonce,
            'gasPrice': w3.to_wei(gas_price, 'gwei'),
            'gas': gas_limit,
            'to': erc20_contract_address,
            'data': erc20_contract.encodeABI(fn_name="mint"),
            'value': 0,
            'chainId': w3.eth.chain_id,
        }
        signed_txn = w3.eth.account.sign_transaction(txn, private_key=main_wallet_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        logging.info(f"Mint transaction sent, tx_hash: \033[34m{tx_hash.hex()}\033[0m")  # Blue color for transaction hash
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status == 1:
            logging.info("\033[92mMint transaction successful.\033[0m")  # Green color for success
        else:
            logging.error("\033[91mMint transaction failed.\033[0m")  # Red color for failure
    except Exception as e:
        logging.error(f"An error occurred during the minting process: {e}")

def main():
    # Define log format with colors
    log_format = "%(asctime)s - %(log_color)s%(levelname)s%(reset)s - %(message)s"  # Corrected format string
    colored_formatter = ColoredFormatter(
        log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',  # Using yellow as a stand-in for orange
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%'
    )
    # Create a logger and add the formatter
    logger = logging.getLogger()
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(colored_formatter)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

    logging.info("Starting E.BCH Minting Script")

    # Set a gas price limit in BEATS, adjust according to your requirements
    GAS_PRICE_LIMIT = 650000  # Example limit, adjust as necessary

    while True:
        new_block = wait_for_new_block()
        token_balances = fetch_token_balances()
        gas_prices = fetch_gas_prices()
        if not gas_prices:
            logging.error("Failed to fetch gas prices. Skipping minting process.")
            continue
        if gas_prices['rapid'] > GAS_PRICE_LIMIT:
            # Use WARNING log level to simulate orange color for high gas fee warning
            logging.warning(f" Waiting 30s. Exceeds gas limit of {GAS_PRICE_LIMIT} - Rapid gas price: \033[33m{gas_prices['rapid']}\033")
            time.sleep(30)
            continue  # Correct placement to skip minting if gas price is too high

        # Proceed with minting if gas price is within the limit
        mint_tokens(gas_prices['rapid'])

        logging.info(f"New block detected: \033[36m{new_block}\033[0m")  # Cyan color for new block
        logging.info("")

        for token, balance in token_balances:
            logging.info(f"{token}: \033[33m{balance}\033[0m")  # Yellow color for balance (as close as we can get to orange)
        logging.info("")

if __name__ == "__main__":
    main()
