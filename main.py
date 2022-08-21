import os  # For fetching environment variables
from aave_client import AaveStakingClient

########################
#SELECT PARAMETERS
########################
network = 'mumbai' #options are: kovan, mumbai
function = 'deposit' #options are: deposit, withdraw
#asset = 'WMATIC'
amount = 0.001
WALLET_ADDRESS=os.getenv('WALLET_ADDRESS')
PRIVATE_WALLET_KEY=os.getenv('PRIVATE_WALLET_KEY')
GAS_STRATEGY="fast"
########################


########################
#MAIN CODE
########################
def deposit_function(network, WALLET_ADDRESS, PRIVATE_WALLET_KEY, RPC_URL, GAS_STRATEGY, amount):
    if network == 'kovan':
        """Obstantiate the client using the Kovan testnet"""
        aave_client_testnet = AaveStakingClient(WALLET_ADDRESS=WALLET_ADDRESS,
                                            PRIVATE_WALLET_KEY=PRIVATE_WALLET_KEY,
                                            KOVAN_RPC_URL=RPC_URL,
                                            GAS_STRATEGY=GAS_STRATEGY)  # see the __init__ function for available gas strategies
        """Obstantiate the client using the Ethereum Mainnet"""
        # aave_client_mainnet = AaveStakingClient(WALLET_ADDRESS=os.getenv('WALLET_ADDRESS'),
        #                                         PRIVATE_WALLET_KEY=os.getenv('PRIVATE_WALLET_KEY'),
        #                                         MAINNET_RPC_URL=os.getenv('MAINNET_RPC_URL'),
        #                                         GAS_STRATEGY="medium")

        """Obstantiate the instance of the Aave lending pool smart contract"""
        lending_pool_contract = aave_client_testnet.get_lending_pool()

        """Get the ReserveToken object for the desired underlying asset to deposit"""
        deposit_token = aave_client_testnet.get_reserve_token(symbol="WETH")

        """Deposit tokens"""
        DEPOSIT_AMOUNT = amount  # As in 'amount' WETH to be deposited
        deposit_hash = aave_client_testnet.deposit(deposit_token=deposit_token, deposit_amount=DEPOSIT_AMOUNT,
                                                lending_pool_contract=lending_pool_contract)
        print("Transaction Hash:", deposit_hash)


    elif network == 'mumbai':
        """Obstantiate the client using the Mumbai testnet"""
        aave_client_testnet = AaveStakingClient(WALLET_ADDRESS=WALLET_ADDRESS,
                                            PRIVATE_WALLET_KEY=PRIVATE_WALLET_KEY,
                                            MUMBAI_RPC_URL=RPC_URL,
                                            GAS_STRATEGY=GAS_STRATEGY)  # see the __init__ function for available gas strategies
        """Obstantiate the client using the MATIC Mainnet"""
        # aave_client_mainnet = AaveStakingClient(WALLET_ADDRESS=os.getenv('WALLET_ADDRESS'),
        #                                         PRIVATE_WALLET_KEY=os.getenv('PRIVATE_WALLET_KEY'),
        #                                         MAINNET_RPC_URL=os.getenv('MATIC_RPC_URL'),
        #                                         GAS_STRATEGY="medium")

        """Obstantiate the instance of the Aave lending pool smart contract"""
        lending_pool_contract = aave_client_testnet.get_lending_pool()

        """Get the ReserveToken object for the desired underlying asset to deposit"""
        deposit_token = aave_client_testnet.get_reserve_token(symbol="WMATIC")

        """Deposit tokens"""
        DEPOSIT_AMOUNT = amount  # As in 'amount' WMATIC to be deposited
        deposit_hash = aave_client_testnet.deposit(deposit_token=deposit_token, deposit_amount=DEPOSIT_AMOUNT,
                                                lending_pool_contract=lending_pool_contract)
        print("Transaction Hash:", deposit_hash)


def withdraw_function(network, WALLET_ADDRESS, PRIVATE_WALLET_KEY, RPC_URL, GAS_STRATEGY, amount):
    if network == 'kovan':

        """Obstantiate the client using the Kovan testnet"""
        aave_client_testnet = AaveStakingClient(WALLET_ADDRESS=WALLET_ADDRESS,
                                            PRIVATE_WALLET_KEY=PRIVATE_WALLET_KEY,
                                            KOVAN_RPC_URL=RPC_URL,
                                            GAS_STRATEGY=GAS_STRATEGY)  # see the __init__ function for available gas strategies
        """Obstantiate the client using the Ethereum Mainnet"""
        # aave_client_mainnet = AaveStakingClient(WALLET_ADDRESS=os.getenv('WALLET_ADDRESS'),
        #                                         PRIVATE_WALLET_KEY=os.getenv('PRIVATE_WALLET_KEY'),
        #                                         MAINNET_RPC_URL=os.getenv('MAINNET_RPC_URL'),
        #                                         GAS_STRATEGY="medium")


        """Obstantiate the instance of the Aave lending pool smart contract"""
        lending_pool_contract = aave_client_testnet.get_lending_pool()

        """Get the ReserveToken object for the desired underlying asset to withdraw"""
        withdraw_token = aave_client_testnet.get_reserve_token(symbol="WETH")

        """Withdraw tokens"""
        WITHDRAW_AMOUNT = amount  # As in 'amount' WETH to be withdrawn from Aave
        withdraw_transaction_receipt = aave_client_testnet.withdraw(withdraw_token=withdraw_token, withdraw_amount=WITHDRAW_AMOUNT,
                                                                lending_pool_contract=lending_pool_contract)
        print("AaveTrade Object:", withdraw_transaction_receipt)

    elif network == 'mumbai':

        """Obstantiate the client using the mumbai testnet"""
        aave_client_testnet = AaveStakingClient(WALLET_ADDRESS=WALLET_ADDRESS,
                                            PRIVATE_WALLET_KEY=PRIVATE_WALLET_KEY,
                                            MUMBAI_RPC_URL=RPC_URL,
                                            GAS_STRATEGY=GAS_STRATEGY)  # see the __init__ function for available gas strategies
        """Obstantiate the client using the MATIC Mainnet"""
        # aave_client_mainnet = AaveStakingClient(WALLET_ADDRESS=os.getenv('WALLET_ADDRESS'),
        #                                         PRIVATE_WALLET_KEY=os.getenv('PRIVATE_WALLET_KEY'),
        #                                         MAINNET_RPC_URL=os.getenv('MAINNET_RPC_URL'),
        #                                         GAS_STRATEGY="medium")


        """Obstantiate the instance of the Aave lending pool smart contract"""
        lending_pool_contract = aave_client_testnet.get_lending_pool()

        """Get the ReserveToken object for the desired underlying asset to withdraw"""
        withdraw_token = aave_client_testnet.get_reserve_token(symbol="WMATIC")

        """Withdraw tokens"""
        WITHDRAW_AMOUNT = amount  # As in 'amount' WMatic to be withdrawn from Aave
        withdraw_transaction_receipt = aave_client_testnet.withdraw(withdraw_token=withdraw_token, withdraw_amount=WITHDRAW_AMOUNT,
                                                                lending_pool_contract=lending_pool_contract)
        print("AaveTrade Object:", withdraw_transaction_receipt)

if network == 'kovan':
    RPC_URL=os.getenv("KOVAN_RPC_URL")
elif network == 'mumbai':
    RPC_URL=os.getenv("MUMBAI_RPC_URL")

if function == 'deposit':
    deposit_function(network, WALLET_ADDRESS, PRIVATE_WALLET_KEY, RPC_URL, GAS_STRATEGY, amount)

elif function == 'withdraw':
    withdraw_function(network, WALLET_ADDRESS, PRIVATE_WALLET_KEY, RPC_URL, GAS_STRATEGY, amount)
