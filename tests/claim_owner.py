import os
import base64
from dotenv import load_dotenv
load_dotenv()
from algosdk.v2client import algod, indexer
from algosdk import mnemonic, account, encoding
from algosdk.future import transaction

ALGOD_ENDPOINT = os.getenv('ALGOD_ENDPOINT')
ALGOD_TOKEN = os.getenv('ALGOD_TOKEN')
INDEXER_ENDPOINT = os.getenv('INDEXER_ENDPOINT')
INDEXER_TOKEN = os.getenv('INDEXER_TOKEN')

TEST_ACCOUNT_MNEMONICS = os.getenv('TEST_ACCOUNT_MNEMONICS')
TEST_ACCOUNT_PRIVATE_KEY = mnemonic.to_private_key(TEST_ACCOUNT_MNEMONICS)
TEST_ACCOUNT_ADDRESS = account.address_from_private_key(TEST_ACCOUNT_PRIVATE_KEY)

DEV_ACCOUNT_MNEMONICS = os.getenv('DEV_ACCOUNT_MNEMONICS')
DEVELOPER_ACCOUNT_PRIVATE_KEY = mnemonic.to_private_key(DEV_ACCOUNT_MNEMONICS)
DEVELOPER_ACCOUNT_ADDRESS = account.address_from_private_key(DEVELOPER_ACCOUNT_PRIVATE_KEY)

OTHER_ACCOUNT_MNEMONICS = os.getenv('OTHER_ACCOUNT_MNEMONICS')
OTHER_ACCOUNT_PRIVATE_KEY = mnemonic.to_private_key(OTHER_ACCOUNT_MNEMONICS)
OTHER_ACCOUNT_ADDRESS = account.address_from_private_key(OTHER_ACCOUNT_PRIVATE_KEY)

ESCROW_LOGICSIG = os.getenv('ESCROW_LOGICSIG')
ESCROW_ADDRESS = os.getenv('ESCROW_ADDRESS')

STATE_MANAGER_INDEX = int(os.getenv('STATE_MANAGER_INDEX'))
TEST_TOKEN_INDEX = int(os.getenv('TEST_TOKEN_INDEX'))

TEST_TOKEN_LOCK_AMOUNT = 100
TEST_DEPOSIT_ID = 1
OTHER_DEPOSIT_ID = 1
TEST_END_ROUND = 1631599575
TEST_TOKEN_TIMESTAMP = 1631599575
KEY1 = str(TEST_ACCOUNT_ADDRESS) + str(TEST_DEPOSIT_ID) 

NOTE = 'ClaimLock' + '-' + str(TEST_DEPOSIT_ID) + "-" + str(TEST_ACCOUNT_ADDRESS) 

algod_client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_ENDPOINT, headers={
  "x-api-key": ALGOD_TOKEN
})
indexer_client = indexer.IndexerClient(INDEXER_TOKEN, INDEXER_ENDPOINT, headers={
  "x-api-key": INDEXER_TOKEN
})

def wait_for_transaction(transaction_id):
    suggested_params = algod_client.suggested_params()
    algod_client.status_after_block(suggested_params.first + 4)
    result = indexer_client.search_transactions(txid=transaction_id)
    assert len(result['transactions']) == 1, result
    return result['transactions'][0]

def read_state(address):
  time_period = 0
  account_info = algod_client.account_info(address)
  local_state = account_info['apps-local-state']
  for block in local_state:
    if block['id'] == STATE_MANAGER_INDEX:
      for kvs in block['key-value']:
        decoded_key = base64.b64decode(kvs['key'])
        #key = decoded_key.decode('utf-8')
        #print(key)
        value = int(kvs['value']['uint'])
        print(value)

def format_state(state):
   formatted = {}
   for item in state:
     key = item['key']
     value = item['value']
     formatted_key = base64.b64decode(key).decode('utf-8')
     if value['type'] == 1:
        if formatted_key == 'voted':
           formatted_value = base64.b64decode(value['bytes']).decode('utf-8')
        else:
           formatted_value = value['bytes']
        formatted[formatted_key] = formatted_value
     else:
        formatted[formatted_key] = value['uint']
   print(formatted)     
   return formatted

def read_global_state(addr, app_id) :   
    results = algod_client.account_info(addr)
    apps_created = results['created-apps']
    for app in apps_created :
        if app['id'] == app_id :
            state = app['params']['global-state']
            format_state(state)

def claim_lock_owner():

  encoded_app_args = [
    bytes("C", "utf-8"),
    (TEST_TOKEN_INDEX).to_bytes(8, 'big'),
    (TEST_DEPOSIT_ID).to_bytes(8, 'big'),
    (TEST_TOKEN_LOCK_AMOUNT).to_bytes(8, 'big'),
    (OTHER_DEPOSIT_ID).to_bytes(8, 'big'),
    (TEST_TOKEN_TIMESTAMP).to_bytes(8, 'big'),
  ]

  # Transaction to State manager
  txn_1 = transaction.ApplicationCallTxn(
    sender=OTHER_ACCOUNT_ADDRESS,
    sp=algod_client.suggested_params(),
    index=STATE_MANAGER_INDEX,
    on_complete=transaction.OnComplete.NoOpOC,
    accounts=[TEST_ACCOUNT_ADDRESS],
    app_args=encoded_app_args,
    note = NOTE.encode()
  )

  # Sign transaction
  stxn_1 = txn_1.sign(OTHER_ACCOUNT_PRIVATE_KEY)

  tx_id = algod_client.send_transaction(stxn_1)

  wait_for_transaction(tx_id)

  print(f"Ownership claim made successfully! Tx ID: https://testnet.algoexplorer.io/tx/{tx_id}")

  print()

if __name__ == "__main__":
  claim_lock_owner()
  read_global_state(DEVELOPER_ACCOUNT_ADDRESS, STATE_MANAGER_INDEX)
