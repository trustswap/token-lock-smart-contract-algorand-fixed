from pyteal import *

def logicsig():

    on_optin = Or(    
       And(
           Txn.type_enum() == TxnType.AssetTransfer,
           Txn.fee() <= Global.min_txn_fee() * Int(2),

           #Sender and receiver of asset transfer must be the same account
           Txn.sender() == Txn.asset_receiver(),

           Txn.close_remainder_to() == Global.zero_address(),
           Txn.rekey_to() == Global.zero_address(), 
       ),
       And(
           Txn.on_completion() == OnComplete.OptIn,
           Txn.fee() <= Global.min_txn_fee() * Int(2),

           #Must opt in to specified stateful contract
           Txn.application_id() == Int(state_manager_id)
       )
    )

    on_withdraw = And(
        Gtxn[0].type_enum() == TxnType.ApplicationCall,

        #App call must be to specified stateful contract
        Gtxn[0].application_id() == Int(state_manager_id),
        Gtxn[0].on_completion() == OnComplete.NoOp,
       
        Gtxn[1].type_enum() == TxnType.AssetTransfer,
        Gtxn[1].asset_receiver() != Global.current_application_address(),

        #Txn should not be of type rekeying or asset closing
        Gtxn[1].asset_close_to() == Global.zero_address(),
        Gtxn[1].rekey_to() == Global.zero_address(),

        Gtxn[1].fee() <= Global.min_txn_fee() * Int(2)
    )

    program = Cond(
        [Global.group_size() == Int(2), on_withdraw],
        [Global.group_size() == Int(1), on_optin]
    )

    return compileTeal(program, Mode.Signature, version=5)

state_manager_id = 80819571

if __name__ == "__main__":
    with open('build/escrow_account.teal', 'w') as f:
        compiled = logicsig()
        f.write(compiled)
