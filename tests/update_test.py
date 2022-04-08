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

ESCROW_LOGICSIG = os.getenv('ESCROW_LOGICSIG')
ESCROW_ADDRESS = os.getenv('ESCROW_ADDRESS')

STATE_MANAGER_INDEX = int(os.getenv('STATE_MANAGER_INDEX'))
TEST_TOKEN_INDEX = int(os.getenv('TEST_TOKEN_INDEX'))

OTHER_ACCOUNT_MNEMONICS = os.getenv('OTHER_ACCOUNT_MNEMONICS')
OTHER_ACCOUNT_PRIVATE_KEY = mnemonic.to_private_key(OTHER_ACCOUNT_MNEMONICS)
OTHER_ACCOUNT_ADDRESS = account.address_from_private_key(OTHER_ACCOUNT_PRIVATE_KEY)

TEST_TOKEN_LOCK_AMOUNT = 100
TEST_NEW_TIME_PERIOD = 1851596251
TEST_DEPOSIT_ID = 1
KEY1 = TEST_ACCOUNT_ADDRESS + str(TEST_DEPOSIT_ID)
NOTE = 'UpdateTime' + '-' + str(TEST_DEPOSIT_ID) + "-" + str(TEST_NEW_TIME_PERIOD)
TEST_TOKEN_TIMESTAMP = 1631601265

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
        print(kvs['value'])
        print(kvs['key'])

def update_lock_period():

  encoded_app_args = [
    bytes("U", "utf-8"),
    (TEST_TOKEN_INDEX).to_bytes(8, 'big'),
    (TEST_DEPOSIT_ID).to_bytes(8, 'big'),
    (TEST_TOKEN_LOCK_AMOUNT).to_bytes(8, 'big'),
    (TEST_NEW_TIME_PERIOD).to_bytes(8, 'big'),
    (TEST_TOKEN_TIMESTAMP).to_bytes(8, 'big'),
  ]

  # Transaction to State manager
  txn_1 = transaction.ApplicationCallTxn(
    sender=TEST_ACCOUNT_ADDRESS,
    sp=algod_client.suggested_params(),
    index=STATE_MANAGER_INDEX,
    on_complete=transaction.OnComplete.NoOpOC,
    accounts=[],
    app_args=encoded_app_args,
    note = NOTE.encode()
  )

  # Sign transaction
  stxn_1 = txn_1.sign(TEST_ACCOUNT_PRIVATE_KEY)

  tx_id = algod_client.send_transaction(stxn_1)

  wait_for_transaction(tx_id)

  print(f"Time period increased successfully! Tx ID: https://testnet.algoexplorer.io/tx/{tx_id}")

  print()

if __name__ == "__main__":
  update_lock_period()
  read_state(TEST_ACCOUNT_ADDRESS)
  
