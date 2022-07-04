# TrustSwap - Algorand: Token Lock Smart Contract

The Trustswap application on Algorand is built by employing a Layer-1 Algorand Smart contract (ASC1). The stateful smart contract manages the global contract storage and local account storage for the application. The locked tokens are also held inside the stateful contract. After maturity of the lock, the contract will send back the tokens via Inner Txns, when claimed by the lock owner.

## Deploy smart contract
The contract is deployed and managed by a multi-signature account, giving multiple parties control over the application. Follow the subsequent steps to deploy the smart contract on the Algorand network.

### Export environmental variables
```
ALGOD_ENDPOINT = "<insert-algod-server-URL>"
ALGOD_TOKEN = "<insert-algod-token>"
INDEXER_ENDPOINT = "<insert-indexer-server-URL>"
INDEXER_TOKEN = "<insert-indexer-token>"

ADMIN_ACCOUNT_1_MNEMONICS = "<insert-admin-account1-mnemonics>"
ADMIN_ACCOUNT_2_MNEMONICS = "<insert-admin-account2-mnemonics>"
ADMIN_ACCOUNT_3_MNEMONICS = "<insert-admin-account3-mnemonics>"
```

### Install Python dependencies inside a virtual environment
#### Minimum version:
Python 3.10
pyteal 0.13.0
```
python3 -m pip install -r requirements.txt
```

### Install Javascript dependencies
```
yarn install
```

### Compile pyteal contract to TEAL
On compiling, the TEAL programs are generated in the build folder
```
$ cd contracts
$ python3 state_manager.py
$ cd ..
```

### Generate Multisignature account
The contract is deployed and can later be updated by a multi-signature account. To generate a multi-signature txn follow these steps, 
 - Include the mnemonic keys of all the admin accounts in .env file as described earlier. 
 - Import the mnemonics into the mnemonics array in config.js.
    ```
    //config.js line 11
    let mnemonics = [process.env.ACCOUNT_1_MNEMONICS, process.env.ACCOUNT_2_MNEMONICS, process.env.ACCOUNT_3_MNEMONICS]
    ```
 - Two command-line arguments are to be passed to the main function            
   1. generate_multisig_acc
   2. the threshold signature count (integer)      
    ```
    $ node deploy.js generate_multisig_acc <integer-representing-threshold-sig-count>
    ```

   The createMultsigAccount() function returns an Algorand address. 
 - Fund the account with ALGOs to deploy the contract.
 - Update the .env file to include the multi-signature account address and threshold count.
    ```
    MULTISIG_ADDRESS = "<insert-multisignature-account-address>"
    THRESHOLD = <integer-representing-threshold-sig-count>
    ```


### Deploy stateful smart contract
To deploy the smart contract to the Algorand network, follow the subsequent steps. 
 - Pass the command line argument to deploy the contract as given below. The function deployStatefulContract() returns the ID of the newly deployed contract.
    ```
    node deploy.js deploy_stateful
    ```
 - Update the stateful app ID in the .env file
    ```
    STATEFUL_APP_ID = <insert app ID>
    ```

### Opt-in the user to stateful contract
User must be opted-in, to enable interaction with the contract. This allows a contract to store data in the user's account. The deposit info and details regarding locked tokens are stored in the local state of the user.


### Lock the tokens in the contract
This is a group txn:
 - First txn is an app call, arguments must include the timestamp when the tokens can be unlocked and a deposit id for uniqueness
 - Second txn is an axfer txn, the user transfers the tokens to be locked to the stateful contract's address
 - Third txn is a payment txn, must only be sent for the very first time that a unique or new ASA ID is locked in the contract. This is to cover the minimum balance for holding an ASA (0.1 Algo) and for the inner txn that opts in the locker contract to the ASA (0.001 Algo).

 ```
 python3 tests/deposit_test.py
 ```

 ### Withdraw the token in the contract
 Also a group txn:
 - First txn is an app call, arguments must include the unlock timestamp, deposit id, deposited token id, and deposited token amount
 - Second txn is a payment txn, to cover txn fees for the inner txn that sends the locked tokens back to the user.

 ```
 python3 tests/withdraw_test.py
 ```

 ### Additional Functions
 - Ability to extend the locked-in period
 - Transfer the ownership of the token lock to a different address
 - The new address must then claim the ownership in a group txn.

 Refer to the files inside the tests directory to find details about building the group txns for these functions.
