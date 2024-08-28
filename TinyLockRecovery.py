import os
import sys
from base64 import b64decode
from typing import Any, Dict, List

from algosdk import account, mnemonic
from algosdk.transaction import ApplicationNoOpTxn, AssetTransferTxn, LogicSig, PaymentTxn
from algosdk.v2client.algod import AlgodClient
from pyteal import compileTeal, Mode, Expr, Int
from tinylocker.contracts.algolocker_sig import approval_program as signature_program
from tinyman.utils import TransactionGroup


class Account:
    def __init__(self, privateKey: str) -> None:
        self.sk = privateKey
        self.addr = account.address_from_private_key(privateKey)

    def getAddress(self) -> str:
        return self.addr

    def getPrivateKey(self) -> str:
        return self.sk

    def getMnemonic(self) -> str:
        return mnemonic.from_private_key(self.sk)

    @classmethod
    def FromMnemonic(cls, m: str):
        return cls(mnemonic.to_private_key(m))


def main():
    print("Unofficial Tinylock ASA Recovery Tool!")
    print("Cobbled together hastily by DingusMungus.algo!")
    print("You better donate some Algos if this thingy werks!\n")

    # CONSTANTS
    tinylock_app = 551903720
    tinylock_asa = 551903529
    unlock_asa_id = 0
    unlock_amount = 0

    # Get locked token assetid
    try:
        unlock_asa_id = input('What is the locked Asset ID:\n> ')
        unlock_asa_id = int(unlock_asa_id)
    except Exception:
        print("Asset ID needs to be a number...")
        close_app()
    if unlock_asa_id == 0:
        print("Invalid Asset ID! Enter a valid Asset ID!")
        close_app()

    # Get total locked amount
    try:
        unlock_amount = input('What is the total amount locked (uint64 - no decimals):\n> ')
        unlock_amount = int(unlock_amount)
    except Exception:
        print("Total amount needs to be a number...")
        close_app()
    if unlock_amount == 0:
        print("Total amount needs to be a positive number!")
        close_app()

    client = AlgodClient("", "https://mainnet-api.algonode.cloud", headers={'User-Agent': 'Client'})
    wallet = Account

    mne = input('What is the mnemonic phrase used to lock the asset:\n> ')
    try:
        wallet = Account(mnemonic.to_private_key(mne))
    except Exception:
        print("Invalid mnemonic! Enter all words before hitting enter!")
        close_app()

    print("Using address: " + wallet.getAddress())

    tinylock_signature = getTinylockerSignature(client, unlock_asa_id, tinylock_app, tinylock_asa, wallet.getAddress())
    tinylock_balances = getBalances(client, tinylock_signature.address())

    if unlock_asa_id not in tinylock_balances:
        print("The provided mnemonic does not match this contract! Did you rekey?")
        close_app()

    if unlock_amount > tinylock_balances[unlock_asa_id]:
        print("The unlock amount {unlock_amount} is greater than the available balance of the contract!")
        close_app()

    unlockToken(client, tinylock_signature, tinylock_app, wallet, unlock_amount, unlock_asa_id)
    close_app()


def close_app():
    print()
    os.system('pause')
    sys.exit(0)


def unlockToken(
    client: AlgodClient,
    signature: LogicSig,
    appID: int,
    sender: Account,
    amount: int,
    lock_token: int
):
    signature_address = signature.address()
    suggested_params = client.suggested_params()
    transactions = [
        PaymentTxn(
            sender=sender.getAddress(),
            sp=suggested_params,
            receiver=signature_address,
            amt=2000
        ),
        ApplicationNoOpTxn(
            sender=signature_address,
            sp=suggested_params,
            index=appID,
            app_args=['unlock']
        ),
        AssetTransferTxn(
            sender=signature_address,
            sp=suggested_params,
            receiver=sender.getAddress(),
            amt=amount,
            index=lock_token
        )
    ]
    transaction_group = TransactionGroup(transactions)
    transaction_group.sign_with_logicsig(signature)
    # TODO: Rekey option goes here
    transaction_group.sign_with_private_key(sender.getAddress(), sender.getPrivateKey())
    transaction_group.submit(client, True)


def getTinylockerSignature(
        client: AlgodClient,
        tmpl_asset_id: int,
        tmpl_contract_id: int,
        tmpl_feetoken_id: int,
        tmpl_locker_address: str
) -> LogicSig:
    return LogicSig(program=fullyCompileContract(client, signature_program(
        Int(tmpl_asset_id),
        Int(tmpl_contract_id),
        Int(tmpl_feetoken_id),
        tmpl_locker_address,
        # TODO: Move to constants?
        "Z7DECPOTVR7WEAB47CFYEHTKAROVHX7QBYJCBDRVA5CC4JBKSFXBKQTERE"
    )))


def fullyCompileContract(client: AlgodClient, contract: Expr, mode=Mode.Application) -> bytes:
    return compileContract(client, compileTeal(contract, mode, version=5))


def compileContract(client: AlgodClient, teal: str) -> bytes:
    return b64decode(client.compile(teal)["result"])


def getBalances(client: AlgodClient, address: str) -> Dict[int, int]:
    balances: Dict[int, int] = dict()
    account_info = client.account_info(address)
    # set key 0 to Algo balance
    balances[0] = account_info["amount"]
    assets: List[Dict[str, Any]] = account_info.get("assets", [])
    for assetHolding in assets:
        asset_id = assetHolding["asset-id"]
        amount = assetHolding["amount"]
        balances[asset_id] = amount
    return balances


if __name__ == "__main__":
    main()
