from email.mime import application
import os
import base64
import time
from dotenv import load_dotenv
load_dotenv()

from algosdk.v2client import algod, indexer
from algosdk.future import transaction
from algosdk import encoding, account, mnemonic, error
from pyteal import compileTeal, Mode
from contracts import state_manager

ALGOD_ENDPOINT = "https://testnet-algorand.api.purestake.io/ps2"
ALGOD_TOKEN = "Cg6qehffpc37kn9VLLf0eqjRK0R0WGt7giDFIfo5"
INDEXER_ENDPOINT = "https://testnet-algorand.api.purestake.io/idx2"
INDEXER_TOKEN = "Cg6qehffpc37kn9VLLf0eqjRK0R0WGt7giDFIfo5"

TEST_ACCOUNT_MNEMONICS = "vital cloud master govern muscle add silver dial party inner main forest found cluster code current mirror have cool toddler grow viable minor abstract arena" # os.getenv('TEST_ACCOUNT_MNEMONICS')
TEST_ACCOUNT_PRIVATE_KEY = mnemonic.to_private_key(TEST_ACCOUNT_MNEMONICS)
TEST_ACCOUNT_ADDRESS = account.address_from_private_key(TEST_ACCOUNT_PRIVATE_KEY)
DEV_ACCOUNT_MNEMONICS = "prosper type goddess input turn ripple butter upgrade island rhythm jelly globe blur lava recall easily effort column nurse strategy write animal circle abstract history" #os.getenv('DEV_ACCOUNT_MNEMONICS')
DEVELOPER_ACCOUNT_PRIVATE_KEY = mnemonic.to_private_key(DEV_ACCOUNT_MNEMONICS)
DEVELOPER_ACCOUNT_ADDRESS = account.address_from_private_key(DEVELOPER_ACCOUNT_PRIVATE_KEY)

TEST_TOKEN_ASSET_NAME = 'Rizzy'
TEST_TOKEN_UNIT_NAME = 'RZ'

manager_app_id = int(os.getenv('STATE_MANAGER_INDEX'))
token_id = int(os.getenv('TEST_TOKEN_INDEX'))

algod_client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_ENDPOINT, headers={
    "x-api-key": ALGOD_TOKEN})
indexer_client = indexer.IndexerClient(INDEXER_TOKEN, INDEXER_ENDPOINT, headers={
    "x-api-key": INDEXER_TOKEN})


def wait_for_transaction(transaction_id):
    suggested_params = algod_client.suggested_params()
    algod_client.status_after_block(suggested_params.first + 4)
    result = indexer_client.search_transactions(txid=transaction_id)
    assert len(result['transactions']) == 1, result
    return result['transactions'][0]

def compile_escrow_account():
    from contracts import escrow_account

    print("Compiling exchange escrow logicsig...")
    escrow_logicsig_teal_code = escrow_account.logicsig()
    compile_response = algod_client.compile(escrow_logicsig_teal_code)
    escrow_logicsig = compile_response['result']
    escrow_logicsig_bytes = base64.b64decode(escrow_logicsig)
    ESCROW_BYTECODE_LEN = len(escrow_logicsig_bytes)
    ESCROW_ADDRESS = compile_response['hash']
    print(
        f"Escrow | {ESCROW_BYTECODE_LEN}/1000 bytes ({ESCROW_ADDRESS})")

    print(f"Escrow logicsig compiled with address {ESCROW_ADDRESS} and logic signature")
    print()
    print(escrow_logicsig)

    print()

    return escrow_logicsig


def compile_state_manager():
    print("Compiling application...")

    manager_approve_teal_code = compileTeal(
        state_manager.approval_program(), Mode.Application, version=6)
    compile_response = algod_client.compile(manager_approve_teal_code)
    manager_approve_code = base64.b64decode(compile_response['result'])
    MANAGER_APPROVE_BYTECODE_LEN = len(manager_approve_code)
    MANAGER_APPROVE_ADDRESS = compile_response['hash']

    manager_clear_teal_code = compileTeal(
        state_manager.clear_program(), Mode.Application, version=6)
    compile_response = algod_client.compile(manager_clear_teal_code)
    manager_clear_code = base64.b64decode(compile_response['result'])
    MANAGER_CLEAR_BYTECODE_LEN = len(manager_clear_code)
    MANAGER_CLEAR_ADDRESS = compile_response['hash']

    print(
        f"State Manager | Approval: {MANAGER_APPROVE_BYTECODE_LEN}/1024 bytes ({MANAGER_APPROVE_ADDRESS}) | Clear: {MANAGER_CLEAR_BYTECODE_LEN}/1024 bytes ({MANAGER_CLEAR_ADDRESS})")

    print()

    return manager_approve_code, manager_clear_code


def deploy_state_manager(manager_approve_code, manager_clear_code):
    print("Deploying state manager application...")

    create_manager_transaction = transaction.ApplicationCreateTxn(
        sender=DEVELOPER_ACCOUNT_ADDRESS,
        sp=algod_client.suggested_params(),
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=manager_approve_code,
        clear_program=manager_clear_code,
        global_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
        local_schema=transaction.StateSchema(num_uints=16, num_byte_slices=0),
    ).sign(DEVELOPER_ACCOUNT_PRIVATE_KEY)
    tx_id = algod_client.send_transaction(create_manager_transaction)
    manager_app_id = wait_for_transaction(tx_id)['created-application-index']
    print(
        f"State Manager deployed with Application ID: {manager_app_id} (Txn ID: https://testnet.algoexplorer.io/tx/{tx_id})"
    )

    print()

    return manager_app_id


def update_state_manager(manager_approve_code, manager_clear_code, appIndex):
    print("Updating exchange state manager application...")

    update_manager_tx = transaction.ApplicationUpdateTxn(
        sender=DEVELOPER_ACCOUNT_ADDRESS,
        sp=algod_client.suggested_params(),
        index=appIndex,
        approval_program=manager_approve_code,
        clear_program=manager_clear_code
    ).sign(DEVELOPER_ACCOUNT_PRIVATE_KEY)

    tx_id = algod_client.send_transaction(update_manager_tx)
    manager_app_id = wait_for_transaction(tx_id)['application-transaction']['application-id']
    print(
        f"Exchange State Manager updated with Application ID: {manager_app_id} (Txn ID: https://testnet.algoexplorer.io/tx/{tx_id})"
    )

    print()

    return manager_app_id



def create_test_token():
    print(
        f"Deploying token {TEST_TOKEN_ASSET_NAME} ({TEST_TOKEN_UNIT_NAME})"
    )

    txn_1 = transaction.AssetConfigTxn(
        sender=DEVELOPER_ACCOUNT_ADDRESS,
        sp=algod_client.suggested_params(),
        total= 2**64 - 1,
        default_frozen=False,
        unit_name=TEST_TOKEN_UNIT_NAME,
        asset_name=TEST_TOKEN_ASSET_NAME,
        manager=DEVELOPER_ACCOUNT_ADDRESS,
        reserve=DEVELOPER_ACCOUNT_ADDRESS,
        freeze=DEVELOPER_ACCOUNT_ADDRESS,
        clawback=DEVELOPER_ACCOUNT_ADDRESS,
        decimals=0
    ).sign(DEVELOPER_ACCOUNT_PRIVATE_KEY)

    tx_id_1 = algod_client.send_transaction(txn_1)

    token_id = wait_for_transaction(tx_id_1)['created-asset-index']

    print(
        f"Deployed {TEST_TOKEN_ASSET_NAME} ({TEST_TOKEN_UNIT_NAME}) with Asset ID: {token_id} | Tx ID: https://testnet.algoexplorer.io/tx/{tx_id_1}"
    )

    print()

    return token_id

def opt_escrow_into_token(escrow_logicsig, token_idx):
    print(
        f"Opting Escrow into Token with Asset ID: {token_idx}..."
    )
    program = base64.b64decode(escrow_logicsig)

    lsig = transaction.LogicSig(program)

    txn = transaction.AssetTransferTxn(
        sender=lsig.address(),
        sp=algod_client.suggested_params(),
        receiver=lsig.address(),
        amt=0,
        index=token_idx,
    )

    lsig_txn = transaction.LogicSigTransaction(txn, lsig)

    tx_id = algod_client.send_transaction(lsig_txn)

    wait_for_transaction(tx_id)

    print(
        f"Opted Escrow into Token with Asset ID: {token_idx} successfully! Tx ID: https://testnet.algoexplorer.io/tx/{tx_id}"
    )

    print()


def opt_escrow_into_manager(escrow_logicsig, manager_app_id):
    print("Opting Escrow into Manager contract...")

    program = base64.b64decode(escrow_logicsig)

    lsig = transaction.LogicSig(program)

    txn = transaction.ApplicationOptInTxn(
        sender=lsig.address(),
        sp=algod_client.suggested_params(),
        index=manager_app_id
    )

    lsig_txn = transaction.LogicSigTransaction(txn, lsig)

    tx_id = algod_client.send_transaction(lsig_txn)

    wait_for_transaction(tx_id)

    print(
        f"Opted Escrow into Manager contract successfully! Tx ID: https://testnet.algoexplorer.io/tx/{tx_id}"
    )

    print()


def opt_user_into_contract(app_id):
    print(
        f"Opting user into contract with App ID: {app_id}..."
    )

    txn = transaction.ApplicationOptInTxn(
        sender=TEST_ACCOUNT_ADDRESS,
        sp=algod_client.suggested_params(),
        index=app_id
    ).sign(TEST_ACCOUNT_PRIVATE_KEY)

    tx_id = algod_client.send_transaction(txn)

    wait_for_transaction(tx_id)

    print(
        f"Opted user into contract with App ID: {app_id} successfully! Tx ID: https://testnet.algoexplorer.io/tx/{tx_id}"
    )

    print()


def opt_user_into_token(asset_id):
    print(
        f"Opting user into token with Asset ID: {asset_id}..."
    )

    txn = transaction.AssetTransferTxn(
        sender=TEST_ACCOUNT_ADDRESS,
        sp=algod_client.suggested_params(),
        receiver=TEST_ACCOUNT_ADDRESS,
        amt=0,
        index=asset_id
    ).sign(TEST_ACCOUNT_PRIVATE_KEY)

    tx_id = algod_client.send_transaction(txn)

    wait_for_transaction(tx_id)

    print(
        f"Opted user into token with Asset ID: {asset_id} successfully! Tx ID: https://testnet.algoexplorer.io/tx/{tx_id}"
    )

    print()

def transfer_tokens_to_user(token_id):
    print(
        f"Transferring tokens to User..."
    )
    amount = 10000 * 10 ** 6
    txn_1 = transaction.AssetTransferTxn(
        sender=DEVELOPER_ACCOUNT_ADDRESS,
        sp=algod_client.suggested_params(),
        receiver=TEST_ACCOUNT_ADDRESS,
        amt=amount,
        index=token_id
    ).sign(DEVELOPER_ACCOUNT_PRIVATE_KEY)

    
    tx_id_1 = algod_client.send_transaction(txn_1)

    wait_for_transaction(tx_id_1)

    print(
        f"Transferred tokens with Asset ID: {token_id} to User successfully! Tx ID: https://testnet.algoexplorer.io/tx/{tx_id_1}"
    )

    print()


if __name__ == "__main__":
    print("Starting deployment process...")
    
    manager_approve_code, manager_clear_code = compile_state_manager()

    # manager_app_id = deploy_state_manager(
    #     manager_approve_code, manager_clear_code)

    # print(f"State Manager App ID = {manager_app_id}")

    manager_app_id = update_state_manager(
        manager_approve_code, manager_clear_code, manager_app_id)

    print(f"State Manager App ID = {manager_app_id}")
    
    # token_id = create_test_token()
    # opt_user_into_token(token_id)

    # escrow_logicsig = compile_escrow_account()

    # opt_escrow_into_token(escrow_logicsig, token_id)

    # opt_user_into_contract(manager_app_id)

    # opt_escrow_into_manager(escrow_logicsig, manager_app_id)

    # transfer_tokens_to_user(token_id)

    print("Deployment completed successfully!")
