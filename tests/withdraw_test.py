import os
import base64
from dotenv import load_dotenv
load_dotenv()
from algosdk.v2client import algod, indexer
from algosdk import mnemonic, account, encoding
from algosdk.future import transaction
import algosdk

ALGOD_ENDPOINT = os.getenv('ALGOD_ENDPOINT')
ALGOD_TOKEN = os.getenv('ALGOD_TOKEN')
INDEXER_ENDPOINT = os.getenv('INDEXER_ENDPOINT')
INDEXER_TOKEN = os.getenv('INDEXER_TOKEN')

TEST_ACCOUNT_MNEMONICS = os.getenv('TEST_ACCOUNT_MNEMONICS')
TEST_ACCOUNT_PRIVATE_KEY = mnemonic.to_private_key(TEST_ACCOUNT_MNEMONICS)
TEST_ACCOUNT_ADDRESS = account.address_from_private_key(TEST_ACCOUNT_PRIVATE_KEY)

STATE_MANAGER_INDEX = int(os.getenv('STATE_MANAGER_INDEX'))
STATE_MANAGER_ADDRESS = algosdk.logic.get_application_address(STATE_MANAGER_INDEX)
TEST_TOKEN_INDEX = int(os.getenv('TEST_TOKEN_INDEX'))


TEST_TOKEN_LOCK_AMOUNT = 200 * 10**6
TEST_DEPOSIT_ID = 12
NOTE = 'Withdraw' + '-' + str(TEST_DEPOSIT_ID)
TEST_LOCK_TIMESTAMP = 1656607445

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


def withdraw_tokens():
  print("Building atomic transaction group...")

  encoded_app_args = [
    bytes("W", "utf-8"),
    (TEST_LOCK_TIMESTAMP).to_bytes(8, 'big'),
    (TEST_DEPOSIT_ID).to_bytes(8, 'big'),
    (TEST_TOKEN_INDEX).to_bytes(8, 'big'),
    (TEST_TOKEN_LOCK_AMOUNT).to_bytes(8, 'big')
  ]


  # Transaction to State manager
  txn_1 = transaction.ApplicationCallTxn(
    sender=TEST_ACCOUNT_ADDRESS,
    sp=algod_client.suggested_params(),
    index=STATE_MANAGER_INDEX,
    on_complete=transaction.OnComplete.NoOpOC,
    foreign_assets=[TEST_TOKEN_INDEX],
    app_args=encoded_app_args,
  )

  txn_2 = transaction.PaymentTxn(
    sender=TEST_ACCOUNT_ADDRESS,
    sp=algod_client.suggested_params(),
    receiver=STATE_MANAGER_ADDRESS,
    amt=1000
  )


  # Get group ID and assign to transactions
  gid = transaction.calculate_group_id([txn_1, txn_2])
  txn_1.group = gid
  txn_2.group = gid

  # Sign transactions
  stxn_1 = txn_1.sign(TEST_ACCOUNT_PRIVATE_KEY)
  stxn_2 = txn_2.sign(TEST_ACCOUNT_PRIVATE_KEY)

  # Broadcast the transactions
  signed_txns = [stxn_1, stxn_2]
  tx_id = algod_client.send_transactions(signed_txns)

  # Wait for transaction
  wait_for_transaction(tx_id)

  print(f"Tokens unlocked successfully! Tx ID: https://testnet.algoexplorer.io/tx/{tx_id}")

  print()

if __name__ == "__main__":
  withdraw_tokens()
  read_state(TEST_ACCOUNT_ADDRESS)