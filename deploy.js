const algosdk = require('algosdk')
const dotenv = require('dotenv').config()
const config = require('./config')
const fs = require('fs').promises
const util = require('util');
const atob = require('atob')
const btoa = require('btoa')

let algodClient = config.algodClient
let maddress = process.env.MULTISIG_ACCOUNT;
let contractId = parseInt(process.env.STATEFUL_APP_ID)

/**
   * Function to create a multisignature account
   * @param threshold integer representing number of threshold signatures required
   * @returns mutisignature account address
   */
async function createMultsigAccount(threshold){
    const mparams = {
        version: 1,
        threshold: threshold,
        addrs: config.adminAddresses
    };

    let multsigaddr = algosdk.multisigAddress(mparams);
    return multsigaddr
}

/**
   * Function to read stateful TEAL code from file
   * @param path
   * @returns program source from file
   */
async function readFile(path){
    let programSource = await fs.readFile(path);
    return programSource
}

/**
   * Function to compile TEAL program
   * @param programSource
   * @returns compiled bytes
   */
async function compileProgram(programSource) {
    let encoder = new util.TextEncoder();
    let programBytes = encoder.encode(programSource);
    let compileResponse = await algodClient.compile(programBytes).do();
    let compiledBytes = new Uint8Array(Buffer.from(compileResponse.result, "base64"));
    return compiledBytes;
  }
  
/**
   * Function to wait for txn to get confirmed
   * @param txId 
   * @returns nil
   */  
async function waitForConfirmation(txId) {
    let status = await algodClient.status().do();
    let lastRound = status["last-round"];
    while (true) {
      const pendingInfo = await algodClient.pendingTransactionInformation(txId).do();
      if (pendingInfo["confirmed-round"] !== null && pendingInfo["confirmed-round"] > 0) {
        console.log("Transaction " + txId + " confirmed in round " + pendingInfo["confirmed-round"]);
        break;
      }
      lastRound++;
      await algodClient.statusAfterBlock(lastRound).do();
    }
  };

/**
 * Function to get bytes array of base64 string
 * @param base64string 
 * @returns bytesArray
 */ 
async function _base64ToArrayBuffer(b64) {
    var binary_string = atob(b64);
    var len = binary_string.length;
    var bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) {
      bytes[i] = binary_string.charCodeAt(i);
    }
    return bytes;
  }  

/**
 * Function to sign txn by multiple parties
 * @param txnObject
 * @returns signedTxn
 */  
async function multisignTxn(txn){
    const mparams = {
        version: 1,
        threshold: parseInt(process.env.THRESHOLD),
        addrs: config.adminAddresses
    };

    let rawSignedTxn = algosdk.signMultisigTransaction(txn, mparams, config.adminAccounts[0].sk).blob;
    for(let i=1; i<config.adminAccounts.length; i++){
        rawSignedTxn = algosdk.appendSignMultisigTransaction(rawSignedTxn, mparams, config.adminAccounts[i].sk).blob;
    }
    return rawSignedTxn
}

/**
 * Function to deploy stateful contract to network
 * @param approvalProgram compiled Approval program
 * @param clearProgram compiled clear program
 * @returns contractId
 */
async function deployStatefulContract(approvalProgram, clearProgram){
    let sender = process.env.MULTISIG_ACCOUNT;
    let onComplete = algosdk.OnApplicationComplete.NoOpOC;
    let params = await algodClient.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    let txn = algosdk.makeApplicationCreateTxn(
        sender,
        params,
        onComplete,
        approvalProgram,
        clearProgram,
        config.localInts,
        config.localBytes,
        config.globalInts,
        config.globalBytes,
    );

    let txId = txn.txID().toString();

    let rawSignedTxn = await multisignTxn(txn)

    await algodClient.sendRawTransaction(rawSignedTxn).do();
    await waitForConfirmation(txId);

    let transactionResponse = await algodClient.pendingTransactionInformation(txId).do();
    let appId = transactionResponse["application-index"];
    console.log("Stateful App ID: ", appId);
    return appId
}

async function updateStatefulContract(approvalProgram, clearProgram){
    let sender = process.env.MULTISIG_ACCOUNT;
    let params = await algodClient.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    let txn = algosdk.makeApplicationUpdateTxn(
        sender,
        params,
        contractId,
        approvalProgram,
        clearProgram
    );

    let txId = txn.txID().toString();

    let rawSignedTxn = await multisignTxn(txn)

    await algodClient.sendRawTransaction(rawSignedTxn).do();
    await waitForConfirmation(txId);

    let transactionResponse = await algodClient.pendingTransactionInformation(txId).do();
    let appId = transactionResponse.txn.txn.apid;
    console.log("Stateful App ID: ", appId);
    return appId
}

const main = async function(){
    try{
        var args = process.argv.slice(2);
        if (args.length <= 0) {
            console.log("Please enter arguments")
            return
        }

        if(args[0] == 'generate_multisig_acc') {
            if(args.length != 2) {
                console.error('second argument must be the threshold signature count')
                throw new Error
            }
            let multisigAddress = await createMultsigAccount(args[1])
            console.log("Multisignature account address: " + multisigAddress)
            console.log("Fund the multisignature account with ALGOs to deploy the contract")
        }

        if(args[0] == 'deploy_stateful'){
            let approvalProgramSource = await readFile('./build/state_manager_approval.teal');
            let clearProgramSource = await readFile('./build/state_manager_clear.teal');
            let approvalProgram = await compileProgram(approvalProgramSource);
            let clearProgram = await compileProgram(clearProgramSource);
            const appId = await deployStatefulContract(approvalProgram, clearProgram)
            return appId
        }

        if(args[0] == 'update_stateful'){
            let approvalProgramSource = await readFile('./build/state_manager_approval.teal');
            let clearProgramSource = await readFile('./build/state_manager_clear.teal');
            let approvalProgram = await compileProgram(approvalProgramSource);
            let clearProgram = await compileProgram(clearProgramSource);

            const appId = await updateStatefulContract(approvalProgram, clearProgram, contractId)
            return appId
        }


    } catch(err){
        console.log(err)
    }
      
}
main()

