from pyteal import *

TXN_TYPE_SET_ESCROW = Bytes("S")
TXN_TYPE_DEPOSIT_TOKENS = Bytes("D")
TXN_TYPE_WITHDRAW_TOKENS = Bytes("W")
TXN_TYPE_UPDATE_LOCK_PERIOD = Bytes("U")
TXN_TYPE_TRANSFER_LOCK_OWNER = Bytes("T")
TXN_TYPE_CLAIM_LOCK_OWNER = Bytes("C")

KEY_COUNTER = Bytes("COUNT")

def approval_program():

    # Declaring Scratch Variables
    scratchvar_user_deposit_state = ScratchVar(TealType.uint64)
    scratchvar_time_period = ScratchVar(TealType.uint64)
    scratchvar_key = ScratchVar(TealType.bytes)
    scratchvar_new_key = ScratchVar(TealType.bytes)
    scratchvar_transfer_key = ScratchVar(TealType.bytes)
    scratchvar_counter = ScratchVar(TealType.uint64)
    scratchvar_other_account_counter = ScratchVar(TealType.uint64)

    # Read counter from local state of transaction sender
    read_user_counter = App.localGet(Int(0), KEY_COUNTER)

    # Read counter from local state of first additional account in accounts array
    read_other_user_counter = App.localGet(Int(1), KEY_COUNTER)

    # Read local state to check for lock transfer in progress
    def lock_transfer_status(type: int, account: Bytes):
        return App.localGet(Int(type), Concat(Bytes('LOCK'), account, Gtxn[0].application_args[2]))

    # Read lock details from transaction sender's local state
    def read_user_local_state(key: Bytes): return App.localGet(Int(0), key)

    # Read lock details from first additional account's local state
    def read_other_user_local_state(key: Bytes): return App.localGet(Int(1), key)

    # Write lock details to transaction sender's local state
    def write_user_local_state(key: Bytes, lock_in_period: Int):
        return App.localPut(Int(0), key, lock_in_period)

    # Increment lock counter value of transaction sender
    def increment_counter():
        return App.localPut(Int(0), KEY_COUNTER, read_user_counter + Int(1))

    # Decrement lock counter value of transaction sender
    def decrement_counter(type: int, lock_counter: Int):
        return App.localPut(Int(type), KEY_COUNTER, lock_counter - Int(1))

    # Delete lock details from local state
    def delete_user_local_state(key: Bytes): return App.localDel(Int(0), key)

    # Inner Txn to return locked tokens to the user
    @Subroutine(TealType.none)
    def do_asset_transfer(tokenId, tokenAmount, receiver):
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.xfer_asset: tokenId,
                    TxnField.asset_amount: tokenAmount,
                    TxnField.asset_receiver: receiver,
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    self_address = Global.current_application_address()

    # Check if transaction sender is the contract's creator
    is_creator = Txn.sender() == Global.creator_address()

    # Check if transaction inputs are valid
    is_valid_app_call = And(
        Gtxn[0].type_enum() == TxnType.ApplicationCall,
        Gtxn[0].on_completion() == OnComplete.NoOp
    )

    # Check for attempts to rekey
    is_zero_address = And(
        Txn.rekey_to() == Global.zero_address(),
        Txn.asset_sender() == Global.zero_address(),
        Txn.asset_close_to() == Global.zero_address()
    )

    # Check whether contract can recieve the tokens to be locked
    is_app_opted_in = AssetHolding.balance(self_address, Txn.assets[0])

    #Checked when an account opts in to contract
    on_opt_in = Seq([
        Assert(is_zero_address),
        Approve()
    ])

    #Checked when the contract is code is updated
    on_update = Seq([
        Assert(And(is_creator, is_zero_address)),
        Approve()
    ])

    #Checked when an account closes out of contract
    on_closeout = Seq([
        scratchvar_counter.store(read_user_counter),
        Assert(
            And(
                #Account's local state should be empty signifying no active locks
                scratchvar_counter.load() == Int(0),
                #Txn should not be of type rekeying or asset closing
                is_zero_address
            )
        ),
        Approve()
    ])

    on_deposit = Seq([
        #txn-app-arg[0] = D
        #txn-app-arg[1] = unlockTimestamp
        #txn-app-arg[2] = depositId

        #Key - 'tokenId depositId amount lockTimestamp'
        #Value - unlockTimestamp

        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(scratchvar_key.load(), Itob(Gtxn[1].xfer_asset()), Gtxn[0].application_args[2], Itob(Gtxn[1].asset_amount()), Gtxn[0].application_args[1])),
        scratchvar_user_deposit_state.store(read_user_local_state(scratchvar_key.load())),
        scratchvar_counter.store(read_user_counter),

        # check if contract has opted in to the asset, and build opt-in inner txn if not
        is_app_opted_in,
        If(is_app_opted_in.hasValue())
        .Then(Assert(Global.group_size() == Int(2)))
        .Else(
            Seq(Assert(
                    # must fund the contract with microAlgos for min. balance & inner txn
                    And(
                        Global.group_size() == Int(3),
                        Gtxn[2].type_enum() == TxnType.Payment,
                        Gtxn[2].amount() >= Int(101000), # (0.1 + 0.001) Algos
                        Gtxn[2].receiver() == self_address
                    )),
            do_asset_transfer(Gtxn[1].xfer_asset(), Int(0), self_address),
        )),

        Assert(is_valid_app_call),
        Assert(
            And(
                Gtxn[0].application_args.length() == Int(3),

                # Lock in period must be greater than current timestamp
                Btoi(Gtxn[0].application_args[1]) > Global.latest_timestamp(),

                # Deposit Id must be an integer greater than zero
                Btoi(Gtxn[0].application_args[2]) > Int(0),

                # Similar lock with same depositId and lockTimestamp should not already exist
                scratchvar_user_deposit_state.load() == Int(0),
                
                # Locked in asset amount must be greater than zero
                # Txn must be of type Axfer
                # Tokens receiver must be the token lock contract address
                Gtxn[1].asset_amount() > Int(0),
                Gtxn[1].type_enum() == TxnType.AssetTransfer,
                Gtxn[1].asset_receiver() == self_address,
                Gtxn[1].sender() == Gtxn[0].sender(),
                Gtxn[1].xfer_asset() == Txn.assets[0],
            )
        ),
        # Txn should not be of type rekeying or asset closing
        Assert(is_zero_address),

        #Updating lock details to user's local state
        write_user_local_state(
            scratchvar_key.load(),
            Btoi(Gtxn[0].application_args[1])
        ),

        #Incrementing lock counter on creation of new lock
        increment_counter(),
        Approve()
    ])

    on_withdraw = Seq([

        #txn-app-arg[0] = W
        #txn-app-arg[1] = unlockTimestamp
        #txn-app-arg[2] = depositId
        #txn-app-arg[3] = tokenId
        #txn-app-arg[4] = lockedAmount

        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(scratchvar_key.load(), Gtxn[0].application_args[3], Gtxn[0].application_args[2], Gtxn[0].application_args[4], Gtxn[0].application_args[1])),
        scratchvar_time_period.store(read_user_local_state(scratchvar_key.load())),
        scratchvar_counter.store(read_user_counter),

        Assert(
            And(
                is_valid_app_call,

                Global.group_size() == Int(2),
                Gtxn[0].application_args.length() == Int(5),

                # Must be an existing valid lock 
                scratchvar_time_period.load() != Int(0),

                # User must fund the locker contract with Algos for the inner txn
                Gtxn[1].type_enum() == TxnType.Payment,
                # Amount paid must be equal to min. tx fee set up the network
                Gtxn[1].amount() >= Global.min_txn_fee(),
                # Payment of inner tx must be the app caller
                Gtxn[1].sender() == Gtxn[0].sender(),
                # Token receiver must not be token lock contract
                Gtxn[1].receiver() == self_address,

                # Lock transfer must not be in progress
                lock_transfer_status(0, Txn.accounts[0]) == Int(0),

                # Lock details must exist in user's local state
                scratchvar_time_period.load() != Int(0),

                # Lock in period should have elapsed
                Global.latest_timestamp() > scratchvar_time_period.load(),

                # Txn should not be of type rekeying or asset closing
                is_zero_address,
            )
        ),

        # Build and send Inner Txn to return locked tokens to the user
        do_asset_transfer(Btoi(Gtxn[0].application_args[3]), Btoi(Gtxn[0].application_args[4]), Gtxn[0].sender()),

        # Deleting lock details from user's local state
        delete_user_local_state(scratchvar_key.load()),

        # Decrementing lock counter on withdrawal of locked tokens
        decrement_counter(0, scratchvar_counter.load()),
        Approve()
    ])

    on_update_lock_period = Seq([

        #txn-app-arg[0] = U
        #txn-app-arg[1] = tokenId
        #txn-app-arg[2] = depositId
        #txn-app-arg[3] = amount
        #txn-app-arg[4] = new unlockTimestamp
        #txn-app-arg[5] = lockTimestamp

        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(scratchvar_key.load(), Gtxn[0].application_args[1], Gtxn[0].application_args[2], Gtxn[0].application_args[3], Gtxn[0].application_args[5])),
        scratchvar_time_period.store(read_user_local_state(scratchvar_key.load())),

        Assert(
            And(
                is_valid_app_call,
                Global.group_size() == Int(1),

                Gtxn[0].accounts.length() == Int(0),
                Gtxn[0].application_args.length() == Int(6),

                #Lock details must exist in user's local state
                scratchvar_time_period.load() != Int(0),

                #Lock transfer must not be in progress
                lock_transfer_status(0, Txn.accounts[0]) == Int(0),

                #New lock in period should be greater than current period
                Btoi(Gtxn[0].application_args[4]) > scratchvar_time_period.load(),

                is_zero_address
            )
        ),

        #Updating lock details to user's local state
        write_user_local_state(
            scratchvar_key.load(),
            Btoi(Gtxn[0].application_args[4])
        ),

        Approve()
    ])

    on_transfer_lock_owner = Seq([
        #txn-app-arg[0] = T
        #txn-app-arg[1] = tokenId
        #txn-app-arg[2] = depositId
        #txn-app-arg[3] = amount
        #txn-app-arg[4] = lockTimestamp

        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(scratchvar_key.load(), Gtxn[0].application_args[1], Gtxn[0].application_args[2], Gtxn[0].application_args[3], Gtxn[0].application_args[4])),
        scratchvar_time_period.store(read_user_local_state(scratchvar_key.load())),
        scratchvar_transfer_key.store(Bytes('LOCK')),
        scratchvar_transfer_key.store(Concat(scratchvar_key.load(), Txn.accounts[0], Gtxn[0].application_args[2])),

        Assert(
            And(
                is_valid_app_call,

                Global.group_size() == Int(1),
                Gtxn[0].accounts.length() == Int(1),
                Gtxn[0].application_args.length() == Int(5),

                #Lock must not be transferred to current owner
                Txn.accounts[0] != Txn.accounts[1],

                #Lock details must exist in user's local state
                scratchvar_time_period.load() != Int(0),

                #Lock with the same key should not exist in the lock reciever's local state
                read_other_user_local_state(scratchvar_key.load()) == Int(0),

                #Lock transfer must not be in progress
                lock_transfer_status(0, Txn.accounts[0]) == Int(0),

                is_zero_address
            )
        ),

        #Updating local state to store transfer details
        write_user_local_state(
            scratchvar_transfer_key.load(),
            Txn.accounts[1]
        ),
        Approve()
    ])

    on_claim_lock_owner = Seq([
        #txn-app-arg[0] = C
        #txn-app-arg[1] = Token ID
        #txn-app-arg[2] = Old owner depositId
        #txn-app-arg[3] = amount
        #txn-app-arg[4] = New owner depositId
        #txn-app-arg[5] = lockTimestamp

        scratchvar_key.store(Bytes('LOCK')),
        scratchvar_key.store(Concat(scratchvar_key.load(), Gtxn[0].application_args[1],  Gtxn[0].application_args[2], Gtxn[0].application_args[3], Gtxn[0].application_args[5])),
        scratchvar_time_period.store(read_other_user_local_state(scratchvar_key.load())),

        scratchvar_new_key.store(Bytes('LOCK')),
        scratchvar_new_key.store(Concat(scratchvar_new_key.load(), Gtxn[0].application_args[1], Gtxn[0].application_args[4], Gtxn[0].application_args[3], Gtxn[0].application_args[5])),

        scratchvar_transfer_key.store(Bytes('LOCK')),
        scratchvar_transfer_key.store(Concat(scratchvar_transfer_key.load(), Txn.accounts[1], Gtxn[0].application_args[2])),

        scratchvar_counter.store(read_user_counter),

        scratchvar_other_account_counter.store(read_other_user_counter),

        Assert(
            And(
                is_valid_app_call,

                Global.group_size() == Int(1),
                Gtxn[0].accounts.length() == Int(1),
                Gtxn[0].application_args.length() == Int(6),

                #Lock must not be claimed by current owner
                Txn.accounts[0] != Txn.accounts[1],

                #Lock details must exist in original owner's local state
                scratchvar_time_period.load() != Int(0),

                #Lock transfer must be in progress
                lock_transfer_status(1, Txn.accounts[1]) == Txn.accounts[0],

                is_zero_address
            )
        ),

        #Deleting lock details from original owner's local state
        App.localDel(Int(1), scratchvar_key.load()),

        #Deleting local state that represents transfer in progress from original owner
        App.localDel(Int(1), scratchvar_transfer_key.load()),

        #Updating lock details to new owner's local state
        write_user_local_state(
            scratchvar_new_key.load(),
            scratchvar_time_period.load()
        ),

        #Incrementing lock counter of new owner on claiming a lock
        increment_counter(),

        #Decrementing lock counter of original owner on transferring a lock
        decrement_counter(1, scratchvar_other_account_counter.load()),

        Approve()
    ])

    program = Cond(
        [Txn.application_id() == Int(0),
            Approve()],
        [Txn.on_completion() == OnComplete.DeleteApplication,
            Reject()],
        [Txn.on_completion() == OnComplete.CloseOut,
            on_closeout],
        [Txn.on_completion() == OnComplete.OptIn,
            on_opt_in],
        [Txn.on_completion() == OnComplete.UpdateApplication,
            on_update],
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
        Approve()
    ])
    return check

if __name__ == "__main__":

    state_manager_approve_teal_code = compileTeal(approval_program(), Mode.Application, version=6)
    with open('./build/state_manager_approval.teal', 'w') as f:
        f.write(state_manager_approve_teal_code)

    state_manager_clear_teal_code = compileTeal(clear_program(), Mode.Application, version=6)
    with open('./build/state_manager_clear.teal', 'w') as f:
        f.write(state_manager_clear_teal_code)
