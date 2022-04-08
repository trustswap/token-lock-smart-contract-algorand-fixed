const algosdk = require("algosdk");

let algodServer = process.env.ALGOD_ENDPOINT
let algodToken = {
    'X-API-Key': process.env.ALGOD_TOKEN
  };
let algodPort = '';  

let algodClient =  new algosdk.Algodv2(algodToken, algodServer, algodPort);

let mnemonics = [process.env.ACCOUNT_1_MNEMONICS, process.env.ACCOUNT_2_MNEMONICS, process.env.ACCOUNT_3_MNEMONICS]
let adminAccounts = []; 
let adminAddresses = [];

//generating accounts from mnemonics
for(let i=0; i<mnemonics.length; i++){
    let account = algosdk.mnemonicToSecretKey(mnemonics[i])
    adminAccounts.push(account)
    adminAddresses.push(account.addr)
}

//application state storage schema
const localInts = 16;
const localBytes = 0;
const globalInts = 1;
const globalBytes = 15;

module.exports = {
  localInts,
  localBytes,
  globalInts,
  globalBytes,
  algodClient,
  adminAccounts,
  adminAddresses
}
