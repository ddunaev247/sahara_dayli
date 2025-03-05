import time
import random
from web3 import Web3, HTTPProvider
import logging
from datetime import datetime
from web3.middleware import ExtraDataToPOAMiddleware
import requests

# Настройка логирования
try:
    logging.basicConfig(
        filename='sahara_token_log.txt',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filemode='a'
    )
    logger = logging.getLogger(__name__)
    print("Логирование настроено")
except Exception as e:
    print(f"Ошибка настройки логирования: {e}")
    logger = None

CHAIN_ID = 313313

def get_sahara_rpc(max_retries=3):
    print("Попытка подключения к RPC")
    rpc_url = "https://testnet.saharalabs.ai"
    for attempt in range(max_retries):
        try:
            print(f"Попытка {attempt + 1} из {max_retries}")
            w3 = Web3(HTTPProvider(rpc_url))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            if w3.is_connected():
                print(f"Успешно подключено к {rpc_url}")
                if logger: logger.info(f"Успешно подключено к {rpc_url}")
                return w3
            else:
                print(f"Не удалось подключиться к {rpc_url}")
                if logger: logger.error(f"Не удалось подключиться к {rpc_url}")
                return None
        except Exception as e:
            print(f"Ошибка подключения к {rpc_url}: {e}")
            if logger: logger.error(f"Ошибка подключения к {rpc_url}: {e}")
            if attempt < max_retries - 1:
                print(f"Повторная попытка через 2 секунд...")  # Уменьшено с 5 до 2 секунд
                time.sleep(2)
            else:
                print(f"Не удалось подключиться после {max_retries} попыток")
                return None


def log_result(wallet_address, status, commission, extra_info=""):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"{now} - {wallet_address} - {'Success' if status else 'Failure'} - {commission:.6f} SAHARA {extra_info}"
    print(log_line)
    if logger: logger.info(log_line)

def send_sahara_token(w3, wallet_address, private_key):
    try:
        wallet_address = Web3.to_checksum_address(wallet_address)
        nonce = w3.eth.get_transaction_count(wallet_address)
        base_fee = w3.eth.get_block('latest')['baseFeePerGas'] or w3.to_wei('1', 'gwei')
        max_priority_fee_per_gas = w3.to_wei('0.01', 'gwei')
        max_fee_per_gas = w3.to_wei('1.01', 'gwei')
        gas_limit = 21000
        send_amount = random.uniform(0.000001, 0.000009)
        value = w3.to_wei(send_amount, 'ether')
        tx = {
            'to': wallet_address,
            'value': value,
            'gas': gas_limit,
            'maxFeePerGas': max_fee_per_gas,
            'maxPriorityFeePerGas': max_priority_fee_per_gas,
            'nonce': nonce,
            'chainId': CHAIN_ID,
            'type': 2
        }
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        commission = (receipt.gasUsed * max_fee_per_gas) / (10 ** 18)
        log_result(wallet_address, True, commission, f"Sent {send_amount} SAHARA to self with EIP-1559")
        return True, commission, receipt
    except Exception as e:
        log_result(wallet_address, False, 0, f"Error: {e}")
        return False, 0, None
