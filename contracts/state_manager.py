from pyteal import *

TXN_TYPE_SET_ESCROW = Bytes("S")
TXN_TYPE_DEPOSIT_TOKENS = Bytes("D")
TXN_TYPE_WITHDRAW_TOKENS = Bytes("W")
TXN_TYPE_UPDATE_LOCK_PERIOD = Bytes("U")
TXN_TYPE_TRANSFER_LOCK_OWNER = Bytes("T")
TXN_TYPE_CLAIM_LOCK_OWNER = Bytes("C")

KEY_ESCROW_LOCAL_STATE = Bytes("TRUSTSWAP_ESCROW")
KEY_SET_ESCROW_FLAG = Bytes("SET_ESCROW")
KEY_COUNTER = Bytes("COUNTER")

def approval_program():

    # Declaring Scratch Variables
    scratchvar_user_deposit_state = ScratchVar(TealType.uint64)
    scratchvar_time_period = ScratchVar(TealType.uint64)
    scratchvar_escrow_local_state = ScratchVar(TealType.uint64)
    scratchvar_key = ScratchVar(TealType.bytes)
    scratchvar_new_key = ScratchVar(TealType.bytes)
    scratchvar_transfer_key = ScratchVar(TealType.bytes)
    scratchvar_counter = ScratchVar(TealType.uint64)
    scratchvar_other_account_counter = ScratchVar(TealType.uint64)

    #Read from escrow account's local state 
    read_escrow_local_state = App.localGet(Int(1), KEY_ESCROW_LOCAL_STATE)

    #Read counter from local state of transaction sender
    read_user_counter = App.localGet(Int(0), KEY_COUNTER)

    #Read counter from local state of first additional account in accounts array
    read_other_user_counter = App.localGet(Int(1), KEY_COUNTER)

    #Read global state to check for lock transfer in progress
    def lock_transfer_status(account: Bytes): 
        return App.globalGet(Concat(account, Gtxn[0].application_args[2])) 
    
    #Read lock details from transaction sender's local state
    def read_user_local_state(key: Bytes): return App.localGet(Int(0), key)
    
    #Read lock details from first additional account's local state
    def read_other_user_local_state(key: Bytes) : return App.localGet(Int(1), key)

    #Write lock details to transaction sender's local state
    def write_user_local_state(key: Bytes, lock_in_period: Int): 
        return App.localPut(Int(0), key, lock_in_period)
    
    #Increment lock counter value of transaction sender
    def increment_counter(): 
        return App.localPut(Int(0), KEY_COUNTER, read_user_counter + Int(1))   

    #Decrement lock counter value of transaction sender
    def decrement_counter(): 
        return App.localPut(Int(0), KEY_COUNTER, read_user_counter - Int(1))      

    #Delete lock details from local state 
    def delete_user_local_state(key: Bytes): return App.localDel(Int(0), key)
    
    #Check if transaction sender is the contract's creator
    is_creator = Txn.sender() == Global.creator_address()

    #Checked when contract is deployed
    on_create = Int(1)

    #Checked when an account opts in to contract
    on_opt_in = Seq([
        Assert(
            And(
                Txn.asset_close_to() == Global.zero_address(),
                Txn.rekey_to() == Global.zero_address(),
            )
        ),
        Int(1)
    ])

    #Checked when the contract is code is updated
    on_update = Seq([
        Assert(is_creator),
        Int(1)
    ])

    #Checked when an account closes out of contract
    on_closeout = Seq([
        scratchvar_counter.store(read_user_counter),
        
        #Account's local state should be empty signifying no active locks
        Assert(
            And(
                scratchvar_counter.load() == Int(0),
                #Txn should not be of type rekeying or asset closing
                Txn.asset_close_to() == Global.zero_address(),
                Txn.rekey_to() == Global.zero_address(),
            )
        ),
        Int(1)
    ])
  
    on_set_escrow = Seq([
        Assert(
            And(
                #Only the contract creator must be able to use this feature
                is_creator,

                #Escrow must not be set previously
                App.globalGet(KEY_SET_ESCROW_FLAG) == Int(0),

                Txn.type_enum() == TxnType.ApplicationCall,
                Txn.on_completion() == OnComplete.NoOp,
                Txn.asset_close_to() == Global.zero_address(),
                Txn.rekey_to() == Global.zero_address(),
                Global.group_size() == Int(1)
            )
        ),

        #Updating global state to set flag denoting escrow being set
        App.globalPut(KEY_SET_ESCROW_FLAG, Int(1)),

        #Writing to escrow accounts's local state to uniquely identify as escrow
        App.localPut(Int(1), KEY_ESCROW_LOCAL_STATE, Int(1)),      
        Int(1)
    ])

    on_deposit = Seq([
        #txn-app-arg[0] = D
        #txn-app-arg[1] = unlockTimestamp
        #txn-app-arg[2] = depositId
        
        #Key - 'tokenId depositId amount lockTimestamp' 
        #Value - unlockTimestamp
        
        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(Itob(Gtxn[1].xfer_asset()), Gtxn[0].application_args[2], Itob(Gtxn[1].asset_amount()), Itob(Global.latest_timestamp()))),
        scratchvar_user_deposit_state.store(read_user_local_state(scratchvar_key.load())),
        scratchvar_escrow_local_state.store(read_escrow_local_state),
        scratchvar_counter.store(read_user_counter),

        Assert(
            And(
                Global.group_size() == Int(2),

                Gtxn[0].type_enum() == TxnType.ApplicationCall,
                Gtxn[0].accounts.length() == Int(1),
                Gtxn[0].application_args.length() == Int(3),
                Gtxn[0].on_completion() == OnComplete.NoOp,

                #Lock in period must be greater than current timestamp
                Btoi(Gtxn[0].application_args[1]) > Global.latest_timestamp(),  

                #Deposit Id must be an integer greater than zero
                Btoi(Gtxn[0].application_args[2]) > Int(0),         
                
                #Locked in asset amount must be greater than zero
                Gtxn[1].asset_amount() > Int(0),

                #Similar lock with same depositId and lockTimestamp should not already exist
                scratchvar_user_deposit_state.load() == Int(0),     

                #Escrow account must have special identifying state   
                scratchvar_escrow_local_state.load() == Int(1),         

                Gtxn[1].type_enum() == TxnType.AssetTransfer,
                Gtxn[1].sender() == Gtxn[0].sender(),

                #Tokens receiver must be escrow account
                Gtxn[1].asset_receiver() == Txn.accounts[1],

                #Txn should not be of type rekeying or asset closing
                Gtxn[1].asset_close_to() == Global.zero_address(),
                Gtxn[1].rekey_to() == Global.zero_address(),  
            )
        ),
 
        #Updating lock details to user's local state
        write_user_local_state(
            scratchvar_key.load(),
            Btoi(Gtxn[0].application_args[1])
        ),

        #Incrementing lock counter on creation of new lock
        increment_counter(),
        Int(1)    
    ])
    
    on_withdraw = Seq([
        
        #txn-app-arg[0] = W
        #txn-app-arg[1] = lockTimestamp
        #txn-app-arg[2] = depositId

        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(Itob(Gtxn[1].xfer_asset()), Gtxn[0].application_args[2], Itob(Gtxn[1].asset_amount()), Gtxn[0].application_args[1])), 
        scratchvar_time_period.store(read_user_local_state(scratchvar_key.load())),
        scratchvar_escrow_local_state.store(read_escrow_local_state),
        
        Assert(
            And(
                Global.group_size() == Int(2),

                Gtxn[0].type_enum() == TxnType.ApplicationCall,
                Gtxn[0].accounts.length() == Int(1),
                Gtxn[0].application_args.length() == Int(3),
                Gtxn[0].on_completion() == OnComplete.NoOp,

                Gtxn[1].type_enum() == TxnType.AssetTransfer,

                #Txn should not be of type rekeying or asset closing
                Gtxn[1].asset_close_to() == Global.zero_address(),
                Gtxn[1].rekey_to() == Global.zero_address(), 

                #Asset receiver must be the transaction sender
                Gtxn[1].asset_receiver() == Gtxn[0].sender(),
                
                #Escrow account must have special identifying state  
                scratchvar_escrow_local_state.load() == Int(1),

                #Lock transfer must not be in progress
                lock_transfer_status(Txn.accounts[0]) == Int(0), 

                #Lock details must exist in user's local state
                scratchvar_time_period.load() != Int(0),         

                #Lock in period should have elapsed    
                Global.latest_timestamp() > scratchvar_time_period.load(),                
            )
        ),

        #Deleting lock details from user's local state
        delete_user_local_state(scratchvar_key.load()),

        #Decrementing lock counter on withdrawal of locked tokens
        decrement_counter(),
        Int(1)
    ])

    on_update_lock_period = Seq([
        
        #txn-app-arg[0] = U
        #txn-app-arg[1] = tokenId
        #txn-app-arg[2] = depositId
        #txn-app-arg[3] = amount
        #txn-app-arg[4] = new unlockTimestamp
        #txn-app-arg[5] = lockTimestamp

        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(Gtxn[0].application_args[1], Gtxn[0].application_args[2], 
                                     Gtxn[0].application_args[3], Gtxn[0].application_args[5])), 
        scratchvar_time_period.store(read_user_local_state(scratchvar_key.load())),

        Assert(
            And(
                Global.group_size() == Int(1),

                Gtxn[0].type_enum() == TxnType.ApplicationCall,
                Gtxn[0].accounts.length() == Int(0),
                Gtxn[0].application_args.length() == Int(6),
                Gtxn[0].on_completion() == OnComplete.NoOp,

                Gtxn[0].asset_close_to() == Global.zero_address(),
                Gtxn[0].rekey_to() == Global.zero_address(),
                
                #Lock details must exist in user's local state
                scratchvar_time_period.load() != Int(0),      

                #Lock transfer must not be in progress
                lock_transfer_status(Txn.accounts[0]) == Int(0),     

                #New lock in period should be greater than current period
                Btoi(Gtxn[0].application_args[4]) > scratchvar_time_period.load()  
            ) 
        ),
       
        #Updating lock details to user's local state       
        write_user_local_state(
            scratchvar_key.load(),
            Btoi(Gtxn[0].application_args[4])
        ),
        
        Int(1)   
    ])

    on_transfer_lock_owner = Seq([
        #txn-app-arg[0] = T
        #txn-app-arg[1] = tokenId
        #txn-app-arg[2] = depositId
        #txn-app-arg[3] = amount
        #txn-app-arg[4] = lockTimestamp

        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(Gtxn[0].application_args[1], Gtxn[0].application_args[2], Gtxn[0].application_args[3], Gtxn[0].application_args[4])), 
        scratchvar_time_period.store(read_user_local_state(scratchvar_key.load())),
        scratchvar_transfer_key.store(Bytes('')),
        scratchvar_transfer_key.store(Concat(Txn.accounts[0], Gtxn[0].application_args[2])),        

        Assert(
            And(
                Global.group_size() == Int(1),

                Gtxn[0].type_enum() == TxnType.ApplicationCall,
                Gtxn[0].accounts.length() == Int(1),
                Gtxn[0].application_args.length() == Int(5),
                Gtxn[0].on_completion() == OnComplete.NoOp,
                Gtxn[0].asset_close_to() == Global.zero_address(),
                Gtxn[0].rekey_to() == Global.zero_address(),

                #Lock must not be transferred to current owner
                Txn.accounts[0] != Txn.accounts[1],
            
                #Lock details must exist in user's local state
                scratchvar_time_period.load() != Int(0),
                
                #Lock with the same key should not exist in the lock reciever's local state
                read_other_user_local_state(scratchvar_key.load()) == Int(0),

                #Lock transfer must not be in progress
                lock_transfer_status(Txn.accounts[0]) == Int(0),        
            ) 
        ),
       
        #Updating global state to store transfer details       
        App.globalPut(scratchvar_transfer_key.load(), Txn.accounts[1]),
        Int(1)   
    ])

    on_claim_lock_owner = Seq([
        #txn-app-arg[0] = C
        #txn-app-arg[1] = Token ID
        #txn-app-arg[2] = Old owner depositId
        #txn-app-arg[3] = amount
        #txn-app-arg[4] = New owner depositId
        #txn-app-arg[5] = lockTimestamp
        
        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(Gtxn[0].application_args[1],  Gtxn[0].application_args[2], Gtxn[0].application_args[3], Gtxn[0].application_args[5])), 
        scratchvar_time_period.store(read_other_user_local_state(scratchvar_key.load())),
        
        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_new_key.store(Concat(Gtxn[0].application_args[1], Gtxn[0].application_args[4], Gtxn[0].application_args[3], Gtxn[0].application_args[5])), 

        scratchvar_key.store(Bytes('')),
        scratchvar_transfer_key.store(Concat(Txn.accounts[1], Gtxn[0].application_args[2])),        

        scratchvar_counter.store(read_user_counter),
        
        scratchvar_other_account_counter.store(read_other_user_counter),

        Assert(
            And(
                Global.group_size() == Int(1),

                Gtxn[0].type_enum() == TxnType.ApplicationCall,
                Gtxn[0].accounts.length() == Int(1),
                Gtxn[0].application_args.length() == Int(6),
                Gtxn[0].on_completion() == OnComplete.NoOp,

                Gtxn[0].asset_close_to() == Global.zero_address(),
                Gtxn[0].rekey_to() == Global.zero_address(),

                #Lock must not be claimed by current owner
                Txn.accounts[0] != Txn.accounts[1],
                
                #Lock details must exist in original owner's local state
                scratchvar_time_period.load() != Int(0),  

                #Lock transfer must be in progress
                lock_transfer_status(Txn.accounts[1]) == Txn.accounts[0],  
            )  
        ),
        
        #Deleting lock details from original owner's local state
        App.localDel(Int(1), scratchvar_key.load()),

        #Deleting global state that represents transfer in progress
        App.globalDel(scratchvar_transfer_key.load()),
 
        #Updating lock details to new owner's local state
        write_user_local_state(
            scratchvar_new_key.load(),
            scratchvar_time_period.load()
        ),
        
        #Incrementing lock counter of new owner on claiming a lock
        increment_counter(),

        #Incrementing lock counter of original owner on transferring a lock
        App.localPut(Int(1), KEY_COUNTER, scratchvar_other_account_counter.load() - Int(1)),
        Int(1)    
    ])

    program = Cond(
        [Txn.application_id() == Int(0),
            on_create],
        [Txn.on_completion() == OnComplete.CloseOut,
            on_closeout],
        [Txn.on_completion() == OnComplete.OptIn,
            on_opt_in], 
        [Txn.on_completion() == OnComplete.UpdateApplication,
            on_update],           
        [Txn.application_args[0] == TXN_TYPE_SET_ESCROW,
            on_set_escrow],    
        [Txn.application_args[0] == TXN_TYPE_DEPOSIT_TOKENS,
            on_deposit],
        [Txn.application_args[0] == TXN_TYPE_WITHDRAW_TOKENS,
            on_withdraw],       
        [Txn.application_args[0] == TXN_TYPE_UPDATE_LOCK_PERIOD,
            on_update_lock_period],  
        [Txn.application_args[0] == TXN_TYPE_TRANSFER_LOCK_OWNER,
            on_transfer_lock_owner],      
        [Txn.application_args[0] == TXN_TYPE_CLAIM_LOCK_OWNER,
            on_claim_lock_owner],    
    )

    return program

def clear_program():
    check = Seq([
        Assert(App.localGet(Int(0), KEY_COUNTER) == Int(0)),
        Int(1)
    ])

    return check

if __name__ == "__main__":

    state_manager_approve_teal_code = compileTeal(approval_program(), Mode.Application, version=5)
    with open('./build/state_manager_approval.teal', 'w') as f:
        f.write(state_manager_approve_teal_code)

    state_manager_clear_teal_code = compileTeal(clear_program(), Mode.Application, version=5)    
    with open('./build/state_manager_clear.teal', 'w') as f:
        f.write(state_manager_clear_teal_code)
