# Trustswap - Algorand : Smart contracts

The Trustswap application on Algorand is built by employing two Layer-1 Algorand Smart contracts (ASC1). A stateful smart contract manages the global contract storage and local account storage for the application. The stateless escrow contract is resposible for holding and managing the funds locked using the application. 

## Deploy smart contract
The contract is deployed and managed by a multisignature account, giving multiple parties control over the application. Follow the subsequent steps to deploy the smart contract on the Algorand network.

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

### Install Python dependencies
```
Python 3.9.6
pyteal 0.8.0
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
The contract is deployed and can later be updated by a multisignature account. To generate a multisignature follow the steps, 
 - Include the mnemonic keys of the all the admin accounts in .env file as described earlier. 
 - Import the mnemonics into the mnemonics array in config.js.
    ```
    //config.js line 11
    let mnemonics = [process.env.ACCOUNT_1_MNEMONICS, process.env.ACCOUNT_2_MNEMONICS, process.env.ACCOUNT_3_MNEMONICS]
    ```
 - Two command line arguments are to be passed to the main function            
   1. generate_multisig_acc
   2. the threshold signature count (integer)      

    ```
    $ node deploy.js generate_multisig_acc <integer-representing-threshold-sig-count>
    ```

   The createMultsigAccount() function returns an Algorand address. 
 - Fund the account with ALGOs to deploy the contract.
 - Update the .env file to include the multisignature account address and threshold count
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


### Compile stateless smart contract
To generate the escrow account, 
 - Replace the new state manager app id in the escrow contract in the file contracts/escrow_account.py line 41.
 - Compile the contract to generate the TEAL code in build/escrow_account.teal
    ```
    $ cd contracts
    $ python3 escrow_account.py
    $ cd ..
    ```
 -  Generate the escrow account's address and logic signature
    ```
    node deploy.js generate_escrow
    ```
 - Update the escrow address and logic signature in the .env file.
   ```
   ESCROW_ADDRESS = <insert-escrow-address>
   ESCROW_LOGIC_SIGNATURE = <insert-logic-signature>
   ```   
 - Fund the escrow account with ALGOs to opt-in to stateful smart contract  


### Opt-in escrow account to stateful smart contract
After funding the escrow account,
 - Run the following command to opt in to the stateful contract
   ```
   node deploy.js escrow_optin
   ```


### Set local state of escrow account
- To intialise the escrow account, the local state has to be set. Run the following command to set up the escrow. 
   ```
   node deploy.js set_escrow
   ```