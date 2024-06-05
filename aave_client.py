"""
PACKAGE REQUIREMENTS INSTALL COMMAND:

pip install --upgrade web3 requests
"""

from pprint import pprint
import json
import os
import time
from datetime import datetime
import requests

'''
outdated imports:
import web3.eth
from web3 import Web3
from web3._utils.encoding import HexBytes
from web3.gas_strategies.time_based import *
from web3.middleware import geth_poa_middleware

'''

from web3 import Web3
from web3._utils.encoding import HexBytes
from web3.gas_strategies.time_based import fast_gas_price_strategy, medium_gas_price_strategy, slow_gas_price_strategy, glacial_gas_price_strategy
from web3.middleware import geth_poa_middleware
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

"""------------------------------ Dataclass to Reference Aave Reserve Token Attributes ------------------------------"""
@dataclass
class ReserveToken:
    """Dataclass for easily accessing Aave reserve token properties"""
    aTokenAddress: str
    aTokenSymbol: str
    stableDebtTokenAddress: str
    variableDebtTokenAddress: str
    symbol: str
    address: str
    decimals: int

"""--------------------------- Dataclass to Neatly Handle Transaction Receipts ----------------------------"""
@dataclass
class AaveTrade:
    """Dataclass for easily accessing transaction receipt properties"""
    hash: str
    timestamp: int
    datetime: str
    contract_address: str
    from_address: str
    to_address: str
    gas_price: float
    asset_symbol: str
    asset_address: str
    asset_amount: float
    asset_amount_decimal_units: int
    interest_rate_mode: str
    operation: str

"""------------------------------------------ MAIN AAVE STAKING CLIENT ----------------------------------------------"""
class AaveClient:
    """Fully plug-and-play AAVE staking client in Python3"""
    def __init__(self, WALLET_ADDRESS: str, PRIVATE_WALLET_KEY: str,
                 MAINNET_RPC_URL: str = None, KOVAN_RPC_URL: str = None, 
                 MUMBAI_RPC_URL: str = None, POLYGON_RPC_URL: str = None, 
                 ARBITRUM_RPC_URL: str = None, GAS_STRATEGY: str = "fast"):

        self.private_key = PRIVATE_WALLET_KEY
        self.wallet_address = Web3.to_checksum_address(WALLET_ADDRESS)

        rpc_urls = [KOVAN_RPC_URL, MAINNET_RPC_URL, MUMBAI_RPC_URL, POLYGON_RPC_URL, ARBITRUM_RPC_URL]
        active_rpc_urls = [url for url in rpc_urls if url is not None]

        if len(active_rpc_urls) == 0:
            raise Exception("Missing RPC URLs for all available choices. Must use at least one network configuration.")
        elif len(active_rpc_urls) > 1:
            raise Exception("Only one active network supported at a time. Please use either: Kovan, Mumbai, Mainnet, Polygon, or Arbitrum network.")
        else:
            if KOVAN_RPC_URL is not None:
                self.active_network = KovanConfig(KOVAN_RPC_URL) 
            elif MAINNET_RPC_URL is not None:
                self.active_network = MainnetConfig(MAINNET_RPC_URL)
            elif MUMBAI_RPC_URL is not None:
                self.active_network = MumbaiConfig(MUMBAI_RPC_URL)
            elif POLYGON_RPC_URL is not None:
                self.active_network = PolygonConfig(POLYGON_RPC_URL)
            elif ARBITRUM_RPC_URL is not None:
                self.active_network = ArbitrumConfig(ARBITRUM_RPC_URL)


        self.w3 = self._connect()
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        if GAS_STRATEGY.lower() == "fast":
            """Transaction mined within 60 seconds."""
            self.w3.eth.set_gas_price_strategy(fast_gas_price_strategy)
            self.timeout = 60
        elif GAS_STRATEGY.lower() == "medium":
            """Transaction mined within 5 minutes."""
            self.w3.eth.set_gas_price_strategy(medium_gas_price_strategy)
            self.timeout = 60 * 5
        elif GAS_STRATEGY.lower() == "slow":
            """Transaction mined within 1 hour."""
            self.w3.eth.set_gas_price_strategy(slow_gas_price_strategy)
            self.timeout = 60 * 60
        elif GAS_STRATEGY.lower() == "glacial":
            """Transaction mined within 24 hours."""
            self.w3.eth.set_gas_price_strategy(glacial_gas_price_strategy)
            self.timeout = 60 * 1440
        else:
            raise ValueError("Invalid gas strategy. Available gas strategies are 'fast', 'medium', 'slow', or 'glacial'")

    def _connect(self) -> Web3:
        try:
            return Web3(Web3.HTTPProvider(self.active_network.rpc_url))
        except:
            raise ConnectionError(f"Could not connect to {self.active_network.net_name} network with RPC URL: "
                                  f"{self.active_network.rpc_url}")

    def process_transaction_receipt(self, tx_hash: HexBytes, asset_amount: float,
                                    reserve_token: ReserveToken, operation: str, interest_rate_mode: str = None,
                                    approval_gas_cost: float = 0) -> AaveTrade:
        print(f"Awaiting transaction receipt for transaction hash: {tx_hash.hex()} (timeout = {self.timeout} seconds)")
        receipt = dict(self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=self.timeout))

        verification_timestamp = datetime.utcnow()
        gas_fee = self.w3.from_wei(int(receipt['effectiveGasPrice']) * int(receipt['gasUsed']), 'ether') + approval_gas_cost

        return AaveTrade(hash=tx_hash.hex(),
                         timestamp=int(datetime.timestamp(verification_timestamp)),
                         datetime=verification_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                         contract_address=receipt['contractAddress'],
                         from_address=receipt['from'],
                         to_address=receipt['to'],
                         gas_price=gas_fee,
                         asset_symbol=reserve_token.symbol, asset_address=reserve_token.address,
                         asset_amount=asset_amount,
                         asset_amount_decimal_units=self.convert_to_decimal_units(reserve_token, asset_amount),
                         interest_rate_mode=interest_rate_mode, operation=operation)

    def convert_eth_to_weth(self, amount_in_eth: float) -> AaveTrade:
        """Mints WETH by depositing ETH, then returns the transaction hash string"""
        print(f"Converting {amount_in_eth} ETH to WETH...")
        amount_in_wei = self.w3.to_wei(amount_in_eth, 'ether')
        nonce = self.w3.eth.get_transaction_count(self.wallet_address)
        weth_address = self.w3.to_checksum_address(self.active_network.weth_token)
        weth = self.w3.eth.contract(address=weth_address, abi=ABIReference.weth_abi)
        function_call = weth.functions.deposit()
        transaction = function_call.build_transaction(
            {
                "chainId": self.active_network.chain_id,
                "from": self.wallet_address,
                "nonce": nonce,
                "value": amount_in_wei
            }
        )
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction, private_key=self.private_key
        )
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        receipt = self.process_transaction_receipt(tx_hash, asset_amount=amount_in_eth,
                                                   reserve_token=self.get_reserve_token("WETH"),
                                                   operation="Convert ETH to WETH")
        print("Received WETH!")
        return receipt

    def get_lending_pool(self):
        try:
            pool_addresses_provider_address = self.w3.to_checksum_address(
                self.active_network.pool_addresses_provider
            )
            pool_addresses_provider = self.w3.eth.contract(
                address=pool_addresses_provider_address,
                abi=ABIReference.pool_addresses_provider_abi,
            )
            lending_pool_address = (
                pool_addresses_provider.functions.getPool().call()
            )
            lending_pool = self.w3.eth.contract(
                address=lending_pool_address, abi=ABIReference.pool_abi)
            return lending_pool
        except Exception as exc:
            raise Exception(f"Could not fetch the Aave lending pool smart contract - Error: {exc}")

    def approve_erc20(self, erc20_address: str, lending_pool_contract, amount_in_decimal_units: int,
                      nonce=None) -> tuple:
        """
        Approve the smart contract to take the tokens out of the wallet
        For lending pool transactions, the 'lending_pool_contract' is the lending pool contract's address.

        Returns a tuple of the following:
            (transaction hash string, approval gas cost)
        """
        nonce = nonce if nonce else self.w3.eth.get_transaction_count(self.wallet_address)

        lending_pool_address = self.w3.to_checksum_address(lending_pool_contract.address)
        erc20_address = self.w3.to_checksum_address(erc20_address)
        erc20 = self.w3.eth.contract(address=erc20_address, abi=ABIReference.erc20_abi)
        function_call = erc20.functions.approve(lending_pool_address, amount_in_decimal_units)
        transaction = function_call.build_transaction(
            {
                "chainId": self.active_network.chain_id,
                "from": self.wallet_address,
                "nonce": nonce,
            }
        )
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction, private_key=self.private_key
        )
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        receipt = dict(self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=self.timeout))

        print(f"Approved {amount_in_decimal_units} of {erc20_address} for contract {lending_pool_address}")
        return tx_hash.hex(), self.w3.from_wei(int(receipt['effectiveGasPrice']) * int(receipt['gasUsed']), 'ether')

    def withdraw(self, withdraw_token: ReserveToken, withdraw_amount: float, lending_pool_contract,
                 nonce=None) -> AaveTrade:
        """
        Withdraws the amount of the withdraw_token from Aave, and burns the corresponding aToken.

        Parameters:
            withdraw_token: The ReserveToken object of the token to be withdrawn from Aave.

            withdraw_amount:  The amount of the 'withdraw_token' to withdraw from Aave (e.g. 0.001 WETH)

            lending_pool_contract: The lending pool contract object, obstantiated using self.get_lending_pool()

            nonce: Manually specify the transaction count/ID. Leave as None to get the current transaction count from
                   the user's wallet set at self.wallet_address.

        Returns:
            The AaveTrade object - See line 52 for datapoints reference

        Smart Contract Reference:
            https://docs.aave.com/developers/v/2.0/the-core-protocol/lendingpool#withdraw
        """

        '''
        Uncomment the gasPrice line below to replace a stuck tx. The line below must be used in case of the 
        "Replacement transaction underpriced" error. Once a new tx has replaced the old one, comment again the line below.
        Alternatively, if a tx doesnt go through and last indefinitely --> set GAS_STRATEGY to 'fast' in deposit_collateral_example.py script
        '''
        nonce = nonce if nonce else self.w3.eth.get_transaction_count(self.wallet_address)
        amount_in_decimal_units = self.convert_to_decimal_units(withdraw_token, withdraw_amount)

        print(f"Approving transaction to withdraw {withdraw_amount:.{withdraw_token.decimals}f} of {withdraw_token.symbol} from Aave...")
        try:
            approval_hash, approval_gas = self.approve_erc20(erc20_address=withdraw_token.address,
                                                             lending_pool_contract=lending_pool_contract,
                                                             amount_in_decimal_units=amount_in_decimal_units,
                                                             nonce=nonce)
        except Exception as exc:
            raise UserWarning(f"Could not approve withdraw transaction - Error Code {exc}")

        print(f"Withdrawing {withdraw_amount} of {withdraw_token.symbol} from Aave...")
        function_call = lending_pool_contract.functions.withdraw(withdraw_token.address,
                                                                 amount_in_decimal_units,
                                                                 self.wallet_address)
        transaction = function_call.build_transaction(
            {
                "chainId": self.active_network.chain_id,
                "from": self.wallet_address,
                "nonce": nonce + 1,
            }
        )
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction, private_key=self.private_key
        )
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        receipt = self.process_transaction_receipt(tx_hash, withdraw_amount, withdraw_token,
                                                   operation="Withdraw", approval_gas_cost=approval_gas)
        print(f"Successfully withdrew {withdraw_amount:.{withdraw_token.decimals}f} of {withdraw_token.symbol} from Aave")
        return receipt

    def withdraw_percentage(self, withdraw_token: ReserveToken, withdraw_percentage: float,
                            lending_pool_contract, nonce=None) -> AaveTrade:
        """Same parameters as the self.withdraw() function, except instead of 'withdraw_amount', you will pass the
        percentage of total available collateral on Aave that you would like to withdraw from in the 'withdraw_percentage'
        parameter in the following format: 0.0 (0% of borrowing power) to 1.0 (100% of borrowing power)"""

        if withdraw_percentage > 1.0:
            raise ValueError("Cannot withdraw more than 100% of available collateral of Aave. "
                             "Please pass a value between 0.0 and 1.0")

        total_collateral = self.get_user_data(lending_pool_contract)[2]
        weth_to_withdraw_asset = self.get_asset_price(base_address=self.get_reserve_token("WETH").address,
                                                      quote_address=withdraw_token.address)
        withdraw_amount = weth_to_withdraw_asset * (total_collateral * withdraw_percentage)

        return self.withdraw(withdraw_token, withdraw_amount, lending_pool_contract, nonce)

    def deposit(self, deposit_token: ReserveToken, deposit_amount: float,
                lending_pool_contract, nonce=None) -> AaveTrade:
        """
        Deposits the 'deposit_amount' of the 'deposit_token' to Aave collateral.

        Parameters:
            deposit_token: The ReserveToken object of the token to be deposited/collateralized on Aave

            deposit_amount: The amount of the 'deposit_token' to deposit on Aave (e.g. 0.001 WETH)

            lending_pool_contract: The lending pool contract object, obstantiated using self.get_lending_pool()

            nonce: Manually specify the transaction count/ID. Leave as None to get the current transaction count from
                   the user's wallet set at self.wallet_address.

        Returns:
            The AaveTrade object - See line 52 for datapoints reference

        Smart Contract Reference:
            https://docs.aave.com/developers/v/2.0/the-core-protocol/lendingpool#deposit
        """
        
        '''
        replace a stuck tx. The line below must be used if error "Replacement transaction underpriced"
        if tx doesnt go through and last indefinitely --> set GAS_STRATEGY to 'fast' in deposit_collateral_example.py script
        '''
        gasPrice = self.w3.eth.gas_price
        
        nonce = nonce if nonce else self.w3.eth.get_transaction_count(self.wallet_address)

        amount_in_decimal_units = self.convert_to_decimal_units(deposit_token, deposit_amount)

        print(f"Approving transaction to deposit {deposit_amount} of {deposit_token.symbol} to Aave...")
        try:
            approval_hash, approval_gas = self.approve_erc20(erc20_address=deposit_token.address,
                                                             lending_pool_contract=lending_pool_contract,
                                                             amount_in_decimal_units=amount_in_decimal_units,
                                                             nonce=nonce)
        except Exception as exc:
            raise UserWarning(f"Could not approve deposit transaction - Error Code {exc}")

        print(f"Depositing {deposit_amount} of {deposit_token.symbol} to Aave...")
        function_call = lending_pool_contract.functions.deposit(deposit_token.address,
                                                                amount_in_decimal_units,
                                                                self.wallet_address,
                                                                0)
        transaction = function_call.build_transaction(
            {
                "chainId": self.active_network.chain_id,
                "from": self.wallet_address,
                "nonce": nonce + 1,
            }
        )
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction, private_key=self.private_key
        )
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        receipt = self.process_transaction_receipt(tx_hash, deposit_amount, deposit_token,
                                                   operation="Deposit", approval_gas_cost=approval_gas)
        print(f"Successfully deposited {deposit_amount} of {deposit_token.symbol}")
        return receipt

    def get_user_data(self, lending_pool_contract) -> tuple:
        """
        - Fetches user account data (shown below) across all reserves
        - Only returns the borrowing power (in ETH), and the total user debt (in ETH)

        Parameters:
            lending_pool_contract: The Web3.eth.Contract object fetched from self.get_lending_pool() to represent the
            Aave lending pool smart contract.

        https://docs.aave.com/developers/v/2.0/the-core-protocol/lendingpool#getuseraccountdata
        """
        user_data = lending_pool_contract.functions.getUserAccountData(self.wallet_address).call()
        try:
            (
                total_collateral_base,
                total_debt_base,
                available_borrow_base,
                current_liquidation_threshold,
                ltv,
                health_factor,
            ) = user_data
        except TypeError:
            raise Exception(f"Could not unpack user data due to a TypeError - Received: {user_data}")

        available_borrow_base = self.w3.from_wei(available_borrow_base, "ether")
        total_collateral_base = self.w3.from_wei(total_collateral_base, "ether")
        total_debt_base = self.w3.from_wei(total_debt_base, "ether")
        return float(available_borrow_base), float(total_debt_base), float(total_collateral_base)

    def get_protocol_data(self, function_name="getAllReservesTokens", *args, **kwargs) -> tuple:
        """
        Peripheral contract to collect and pre-process information from the Pool.

        Parameters:
        - function_name: defines the function we want to call from the contract. Possible function
        names are:
            - getAllReservesTokens(): Returns list of the existing reserves in the pool.
            - getAllATokens(): Returns list of the existing ATokens in the pool.
            - getReserveConfigurationData(address asset): Returns the configuration data of the reserve as described below (see docs)
            - getReserveEModeCategory(address asset): Returns reserve's efficiency mode category.
            - getReserveCaps(address asset): Returns the caps parameters of the reserve
            - getPaused(address asset): Returns True if the pool is paused.
            - getSiloedBorrowing(address asset): Returns True if the asset is siloed for borrowing.
            - getLiquidationProtocolFee(address asset): Returns the protocol fee on the liquidation bonus.
            - getUnbackedMintCap(address asset): Returns the unbacked mint cap of the reserve
            - getDebtCeiling(): Returns the debt ceiling of the reserve
            - getDebtCeilingDecimals(address asset): Returns the debt ceiling decimals
            - getReserveData(address asset): Returns the following reserve data (see docs)
            - getATokenTotalSupply(address asset)
            - getTotalDebt(address asset)
            - getUserReserveData(address asset, address user)
            - getReserveTokensAddresses(address asset)
            - getInterestRateStrategyAddress(address asset)

        https://docs.aave.com/developers/core-contracts/aaveprotocoldataprovider
        """

        pool_data_address = self.w3.to_checksum_address(self.active_network.pool_data_provider)
        
        pool_data_contract = self.w3.eth.contract(address=pool_data_address, abi=ABIReference.pool_data_provider_abi)
        
        try:
            # Get the function dynamically
            contract_function = getattr(pool_data_contract.functions, function_name)
            # Call the function with provided arguments
            result = contract_function(*args, **kwargs).call()
        except AttributeError:
            raise ValueError(f"Function {function_name} does not exist in the contract.")
        except Exception as e:
            raise Exception(f"An error occurred while calling the function {function_name}: {e}")

        return result

    def get_pool_data(self, pool_contract, function_name="getReserveData", *args, **kwargs) -> dict:
        """
        The pool.sol contract is the main user facing contract of the protocol. It exposes the 
        liquidity management methods that can be invoked using either Solidity or Web3 libraries.

        Parameters:
        - function_name: defines the function we want to call from the contract. Possible function
        names are:
            - getReserveData(address asset): Returns the state and configuration of the reserve.
            - getUserAccountData(address user): Returns the user account data across all the reserves
            - getConfiguration(address asset): Returns the configuration of the reserve
            - getUserConfiguration(address user): Returns the configuration of the user across all the reserves
            - getReserveNormalizedIncome(address asset): Returns the ongoing normalized income for the reserve.
            ...

        https://docs.aave.com/developers/core-contracts/aaveprotocoldataprovider
        """

        try:
            # Get the function dynamically
            contract_function = getattr(pool_contract.functions, function_name)
            # Call the function with provided arguments
            result = contract_function(*args, **kwargs).call()

            # Handle specific case for getReserveData
            if function_name == "getReserveData":
                try:
                    (
                        configuration,
                        liquidityIndex,
                        currentLiquidityRate,
                        variableBorrowIndex,
                        currentVariableBorrowRate,
                        currentStableBorrowRate,
                        lastUpdateTimestamp,
                        id,
                        aTokenAddress,
                        stableDebtTokenAddress,
                        variableDebtTokenAddress,
                        interestRateStrategyAddress,
                        accruedToTreasury,
                        unbacked,
                        isolationModeTotalDebt,
                    ) = result

                    # Convert ray values to human-readable format
                    def from_ray(value):
                        return value / 10**27

                    result = {
                        "configuration": configuration,
                        "liquidityIndex": from_ray(liquidityIndex),
                        "currentLiquidityRate": from_ray(currentLiquidityRate),
                        "variableBorrowIndex": from_ray(variableBorrowIndex),
                        "currentVariableBorrowRate": from_ray(currentVariableBorrowRate),
                        "currentStableBorrowRate": from_ray(currentStableBorrowRate),
                        "lastUpdateTimestamp": lastUpdateTimestamp,
                        "id": id,
                        "aTokenAddress": aTokenAddress,
                        "stableDebtTokenAddress": stableDebtTokenAddress,
                        "variableDebtTokenAddress": variableDebtTokenAddress,
                        "interestRateStrategyAddress": interestRateStrategyAddress,
                        "accruedToTreasury": accruedToTreasury,
                        "unbacked": unbacked,
                        "isolationModeTotalDebt": isolationModeTotalDebt,
                    }
                except TypeError:
                    raise Exception(f"Could not unpack reserve data due to a TypeError - Received: {result}")

            elif function_name == "getUserAccountData":
                try:
                    (
                        totalCollateralBase,
                        totalDebtBase,
                        availableBorrowsBase,
                        currentLiquidationThreshold,
                        ltv,
                        healthFactor,
                    ) = result

                    # Convert ray values to human-readable format
                    def from_ray(value):
                        return value / 10**27

                    result = {
                        "totalCollateralBase": totalCollateralBase,
                        "totalDebtBase": totalDebtBase,
                        "availableBorrowsBase": availableBorrowsBase,
                        "currentLiquidationThreshold": currentLiquidationThreshold,
                        "ltv": ltv,
                        "healthFactor": healthFactor,
                    }
                except TypeError:
                    raise Exception(f"Could not unpack reserve data due to a TypeError - Received: {result}")


        except AttributeError:
            raise ValueError(f"Method {function_name} does not exist in the contract.")
        except Exception as e:
            raise Exception(f"An error occurred while calling the method {function_name}: {e}")

        return result


'''
OUTDATED CONFIG WITH V2 INSTEAD OF V3
class KovanConfig:
    def __init__(self, kovan_rpc_url: str):
        self.net_name = "Kovan"
        self.chain_id = 42
        self.pool_addresses_provider = '0x88757f2f99175387aB4C6a4b3067c77A695b0349'
        self.weth_token = '0xd0a1e359811322d97991e03f863a0c30c2cf029c'
        self.rpc_url = kovan_rpc_url
        self.aave_tokenlist_url = "https://aave.github.io/aave-addresses/kovan.json"
        self.aave_tokens = [ReserveToken(**token_data) for token_data in self.fetch_aave_tokens()]

    def fetch_aave_tokens(self) -> dict:
        try:
            return requests.get(self.aave_tokenlist_url).json()['proto']
        except:
            raise ConnectionError("Could not fetch Aave tokenlist for the Kovan network from URL: "
                                  "https://aave.github.io/aave-addresses/kovan.json")

class MumbaiConfig:
    def __init__(self, mumbai_rpc_url: str):
        self.net_name = "Mumbai"
        self.chain_id = 80001
        self.pool_addresses_provider = '0x178113104fEcbcD7fF8669a0150721e231F0FD4B'
        self.weth_token = '0x3C68CE8504087f89c640D02d133646d98e64ddd9'
        self.wmatic = '0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889'
        self.usdc = '0xe11A86849d99F524cAC3E7A0Ec1241828e332C62'
        self.rpc_url = mumbai_rpc_url
        self.aave_tokenlist_url = "https://aave.github.io/aave-addresses/mumbai.json"
        self.aave_tokens = [ReserveToken(**token_data) for token_data in self.fetch_aave_tokens()]

    def fetch_aave_tokens(self) -> dict:
        try:
            return requests.get(self.aave_tokenlist_url).json()['matic']
        except:
            raise ConnectionError("Could not fetch Aave tokenlist for the Mumbai network from URL: "
                                  "https://aave.github.io/aave-addresses/mumbai.json")

class MainnetConfig:
    def __init__(self, mainnet_rpc_url: str):
        self.net_name = "Mainnet"
        self.chain_id = 1337
        self.pool_addresses_provider = '0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5'
        self.weth_token = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
        self.link_token = '0x514910771af9ca656af840dff83e8264ecf986ca'
        self.rpc_url = mainnet_rpc_url
        self.aave_tokenlist_url = "https://aave.github.io/aave-addresses/mainnet.json"
        self.aave_tokens = [ReserveToken(**token_data) for token_data in self.fetch_aave_tokens()]

    def fetch_aave_tokens(self) -> dict:
        try:
            return requests.get(self.aave_tokenlist_url).json()['proto']
        except:
            raise ConnectionError("Could not fetch Aave tokenlist for the Mainnet network from URL: "
                                  "https://aave.github.io/aave-addresses/mainnet.json")

'''
class PolygonConfig:
    def __init__(self, polygon_rpc_url: str):
        self.net_name = "Polygon"
        self.chain_id = 137
        self.pool_addresses_provider = '0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb'
        self.pool_data_provider = '0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654'
        self.weth_token = '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619'
        self.usdc_token = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        self.usdt_token = '0xc2132D05D31c914a87C6611C10748AEb04B58e8F'
        self.dai_token = '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063'
        self.rpc_url = polygon_rpc_url
        self.aave_tokenlist_url = "https://aave.github.io/aave-addresses/polygon.json"
        self.aave_tokens = self.fetch_aave_tokens()

    def fetch_aave_tokens(self) -> list:
        try:
            tokens = requests.get(self.aave_tokenlist_url).json()
            # Extract the first key dynamically
            network_key = next(iter(tokens))
            return [ReserveToken(**token_data) for token_data in tokens[network_key]]
        except Exception as e:
            raise ConnectionError(f"Could not fetch Aave tokenlist for the Polygon network from URL: {self.aave_tokenlist_url} - Error: {e}")


class ArbitrumConfig:
    def __init__(self, arbitrum_rpc_url: str):
        self.net_name = "Arbitrum"
        self.chain_id = 42161
        self.pool_addresses_provider = '0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb'
        self.pool_data_provider = '0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654'
        self.weth_token = '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1'
        self.usdc_token = '0xaf88d065e77c8cC2239327C5EDb3A432268e5831' 
        self.usdce_token = '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8' 
        self.usdt_token = '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9'
        self.dai_token = '0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1'        
        self.rpc_url = arbitrum_rpc_url
        #self.aave_tokenlist_url = "https://aave.github.io/aave-addresses/arbitrum.json"
        #self.aave_tokens = self.fetch_aave_tokens()

    '''
    USE getAllReservesTokens instead!!!
    def fetch_aave_tokens(self) -> list:
        try:
            tokens = requests.get(self.aave_tokenlist_url).json()
            # Extract the first key dynamically
            network_key = next(iter(tokens))
            return [ReserveToken(**token_data) for token_data in tokens[network_key]]
        except Exception as e:
            raise ConnectionError(f"Could not fetch Aave tokenlist for the Polygon network from URL: {self.aave_tokenlist_url} - Error: {e}")
    '''

class ABIReference:
    """
    This class contains full JSON ABIs for the smart contracts being called in this client.

    Eventually, I will implement a method to call these ABIs from the etherscan API when they are needed, instead of
    utilizing this class structure which results in hundreds of redundant lines.

    Disregard all past this line, unless you need to add an ABI to implement more smart contracts.
    """
    weth_abi = [
        {
            "constant": True,
            "inputs": [],
            "name": "name",
            "outputs": [{"name": "tokenName", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "spender", "type": "address"},
                {"name": "value", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"name": "success", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"name": "totalTokensIssued", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
            ],
            "name": "transferFrom",
            "outputs": [{"name": "success", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "decimalPlaces", "type": "uint8"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "tokenSymbol", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
            ],
            "name": "transfer",
            "outputs": [{"name": "success", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [],
            "name": "deposit",
            "outputs": [],
            "payable": True,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"},
            ],
            "name": "allowance",
            "outputs": [{"name": "remaining", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
    ]

    price_feed_abi = [
        {
            "inputs": [],
            "name": "decimals",
            "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "description",
            "outputs": [{"internalType": "string", "name": "", "type": "string"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "uint80", "name": "_roundId", "type": "uint80"}],
            "name": "getRoundData",
            "outputs": [
                {"internalType": "uint80", "name": "roundId", "type": "uint80"},
                {"internalType": "int256", "name": "answer", "type": "int256"},
                {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
                {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
                {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"},
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "latestRoundData",
            "outputs": [
                {"internalType": "uint80", "name": "roundId", "type": "uint80"},
                {"internalType": "int256", "name": "answer", "type": "int256"},
                {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
                {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
                {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"},
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "version",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
    ]

    erc20_abi = [
        {
            "inputs": [
                {"internalType": "address", "name": "owner", "type": "address"},
                {"internalType": "address", "name": "spender", "type": "address"},
            ],
            "name": "allowance",
            "outputs": [
                {"internalType": "uint256", "name": "remaining", "type": "uint256"}
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "spender", "type": "address"},
                {"internalType": "uint256", "name": "value", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"internalType": "bool", "name": "success", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"internalType": "uint256", "name": "balance", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "decimals",
            "outputs": [
                {"internalType": "uint8", "name": "decimalPlaces", "type": "uint8"}
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "spender", "type": "address"},
                {"internalType": "uint256", "name": "addedValue", "type": "uint256"},
            ],
            "name": "decreaseApproval",
            "outputs": [{"internalType": "bool", "name": "success", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "spender", "type": "address"},
                {"internalType": "uint256", "name": "subtractedValue", "type": "uint256"},
            ],
            "name": "increaseApproval",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "name",
            "outputs": [{"internalType": "string", "name": "tokenName", "type": "string"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "symbol",
            "outputs": [
                {"internalType": "string", "name": "tokenSymbol", "type": "string"}
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "totalSupply",
            "outputs": [
                {"internalType": "uint256", "name": "totalTokensIssued", "type": "uint256"}
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "uint256", "name": "value", "type": "uint256"},
            ],
            "name": "transfer",
            "outputs": [{"internalType": "bool", "name": "success", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "uint256", "name": "value", "type": "uint256"},
                {"internalType": "bytes", "name": "data", "type": "bytes"},
            ],
            "name": "transferAndCall",
            "outputs": [{"internalType": "bool", "name": "success", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "from", "type": "address"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "uint256", "name": "value", "type": "uint256"},
            ],
            "name": "transferFrom",
            "outputs": [{"internalType": "bool", "name": "success", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]

    pool_addresses_provider_abi = [
        {"inputs":
         [
             {"internalType":"string","name":"marketId","type":"string"},
             {"internalType":"address","name":"owner","type":"address"}],
             "stateMutability":"nonpayable",
             "type":"constructor"
        },{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"oldAddress","type":"address"},{"indexed":True,"internalType":"address","name":"newAddress","type":"address"}],"name":"ACLAdminUpdated","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"oldAddress","type":"address"},{"indexed":True,"internalType":"address","name":"newAddress","type":"address"}],"name":"ACLManagerUpdated","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"bytes32","name":"id","type":"bytes32"},{"indexed":True,"internalType":"address","name":"oldAddress","type":"address"},{"indexed":True,"internalType":"address","name":"newAddress","type":"address"}],"name":"AddressSet","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"bytes32","name":"id","type":"bytes32"},{"indexed":True,"internalType":"address","name":"proxyAddress","type":"address"},{"indexed":False,"internalType":"address","name":"oldImplementationAddress","type":"address"},{"indexed":True,"internalType":"address","name":"newImplementationAddress","type":"address"}],"name":"AddressSetAsProxy","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"string","name":"oldMarketId","type":"string"},{"indexed":True,"internalType":"string","name":"newMarketId","type":"string"}],"name":"MarketIdSet","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"previousOwner","type":"address"},{"indexed":True,"internalType":"address","name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"oldAddress","type":"address"},{"indexed":True,"internalType":"address","name":"newAddress","type":"address"}],"name":"PoolConfiguratorUpdated","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"oldAddress","type":"address"},{"indexed":True,"internalType":"address","name":"newAddress","type":"address"}],"name":"PoolDataProviderUpdated","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"oldAddress","type":"address"},{"indexed":True,"internalType":"address","name":"newAddress","type":"address"}],"name":"PoolUpdated","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"oldAddress","type":"address"},{"indexed":True,"internalType":"address","name":"newAddress","type":"address"}],"name":"PriceOracleSentinelUpdated","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"oldAddress","type":"address"},{"indexed":True,"internalType":"address","name":"newAddress","type":"address"}],"name":"PriceOracleUpdated","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"bytes32","name":"id","type":"bytes32"},{"indexed":True,"internalType":"address","name":"proxyAddress","type":"address"},{"indexed":True,"internalType":"address","name":"implementationAddress","type":"address"}],"name":"ProxyCreated","type":"event"},{"inputs":[],"name":"getACLAdmin","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getACLManager","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes32","name":"id","type":"bytes32"}],"name":"getAddress","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getMarketId","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getPool","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getPoolConfigurator","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getPoolDataProvider","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getPriceOracle","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getPriceOracleSentinel","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"renounceOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newAclAdmin","type":"address"}],"name":"setACLAdmin","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newAclManager","type":"address"}],"name":"setACLManager","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"bytes32","name":"id","type":"bytes32"},{"internalType":"address","name":"newAddress","type":"address"}],"name":"setAddress","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"bytes32","name":"id","type":"bytes32"},{"internalType":"address","name":"newImplementationAddress","type":"address"}],"name":"setAddressAsProxy","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"string","name":"newMarketId","type":"string"}],"name":"setMarketId","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newPoolConfiguratorImpl","type":"address"}],"name":"setPoolConfiguratorImpl","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newDataProvider","type":"address"}],"name":"setPoolDataProvider","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newPoolImpl","type":"address"}],"name":"setPoolImpl","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newPriceOracle","type":"address"}],"name":"setPriceOracle","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newPriceOracleSentinel","type":"address"}],"name":"setPriceOracleSentinel","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"}
        ]

    lending_pool_abi = [
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "reserve",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "address",
                    "name": "user",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "onBehalfOf",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "amount",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "borrowRateMode",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "borrowRate",
                    "type": "uint256",
                },
                {
                    "indexed": True,
                    "internalType": "uint16",
                    "name": "referral",
                    "type": "uint16",
                },
            ],
            "name": "Borrow",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "reserve",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "address",
                    "name": "user",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "onBehalfOf",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "amount",
                    "type": "uint256",
                },
                {
                    "indexed": True,
                    "internalType": "uint16",
                    "name": "referral",
                    "type": "uint16",
                },
            ],
            "name": "Deposit",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "target",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "initiator",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "asset",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "amount",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "premium",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint16",
                    "name": "referralCode",
                    "type": "uint16",
                },
            ],
            "name": "FlashLoan",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "collateralAsset",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "debtAsset",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "user",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "debtToCover",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "liquidatedCollateralAmount",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "address",
                    "name": "liquidator",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "bool",
                    "name": "receiveAToken",
                    "type": "bool",
                },
            ],
            "name": "LiquidationCall",
            "type": "event",
        },
        {"anonymous": False, "inputs": [], "name": "Paused", "type": "event"},
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "reserve",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "user",
                    "type": "address",
                },
            ],
            "name": "RebalanceStableBorrowRate",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "reserve",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "user",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "repayer",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "amount",
                    "type": "uint256",
                },
            ],
            "name": "Repay",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "reserve",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "liquidityRate",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "stableBorrowRate",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "variableBorrowRate",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "liquidityIndex",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "variableBorrowIndex",
                    "type": "uint256",
                },
            ],
            "name": "ReserveDataUpdated",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "reserve",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "user",
                    "type": "address",
                },
            ],
            "name": "ReserveUsedAsCollateralDisabled",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "reserve",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "user",
                    "type": "address",
                },
            ],
            "name": "ReserveUsedAsCollateralEnabled",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "reserve",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "user",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "rateMode",
                    "type": "uint256",
                },
            ],
            "name": "Swap",
            "type": "event",
        },
        {"anonymous": False, "inputs": [], "name": "Unpaused", "type": "event"},
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "reserve",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "user",
                    "type": "address",
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "to",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "amount",
                    "type": "uint256",
                },
            ],
            "name": "Withdraw",
            "type": "event",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"},
                {"internalType": "uint256", "name": "interestRateMode", "type": "uint256"},
                {"internalType": "uint16", "name": "referralCode", "type": "uint16"},
                {"internalType": "address", "name": "onBehalfOf", "type": "address"},
            ],
            "name": "borrow",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"},
                {"internalType": "address", "name": "onBehalfOf", "type": "address"},
                {"internalType": "uint16", "name": "referralCode", "type": "uint16"},
            ],
            "name": "deposit",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "address", "name": "from", "type": "address"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"},
                {"internalType": "uint256", "name": "balanceFromAfter", "type": "uint256"},
                {"internalType": "uint256", "name": "balanceToBefore", "type": "uint256"},
            ],
            "name": "finalizeTransfer",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "receiverAddress", "type": "address"},
                {"internalType": "address[]", "name": "assets", "type": "address[]"},
                {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"},
                {"internalType": "uint256[]", "name": "modes", "type": "uint256[]"},
                {"internalType": "address", "name": "onBehalfOf", "type": "address"},
                {"internalType": "bytes", "name": "params", "type": "bytes"},
                {"internalType": "uint16", "name": "referralCode", "type": "uint16"},
            ],
            "name": "flashLoan",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "getAddressesProvider",
            "outputs": [
                {
                    "internalType": "contract ILendingPoolAddressesProvider",
                    "name": "",
                    "type": "address",
                }
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "address", "name": "asset", "type": "address"}],
            "name": "getConfiguration",
            "outputs": [
                {
                    "components": [
                        {"internalType": "uint256", "name": "data", "type": "uint256"}
                    ],
                    "internalType": "struct DataTypes.ReserveConfigurationMap",
                    "name": "",
                    "type": "tuple",
                }
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "address", "name": "asset", "type": "address"}],
            "name": "getReserveData",
            "outputs": [
                {
                    "components": [
                        {
                            "components": [
                                {
                                    "internalType": "uint256",
                                    "name": "data",
                                    "type": "uint256",
                                }
                            ],
                            "internalType": "struct DataTypes.ReserveConfigurationMap",
                            "name": "configuration",
                            "type": "tuple",
                        },
                        {
                            "internalType": "uint128",
                            "name": "liquidityIndex",
                            "type": "uint128",
                        },
                        {
                            "internalType": "uint128",
                            "name": "variableBorrowIndex",
                            "type": "uint128",
                        },
                        {
                            "internalType": "uint128",
                            "name": "currentLiquidityRate",
                            "type": "uint128",
                        },
                        {
                            "internalType": "uint128",
                            "name": "currentVariableBorrowRate",
                            "type": "uint128",
                        },
                        {
                            "internalType": "uint128",
                            "name": "currentStableBorrowRate",
                            "type": "uint128",
                        },
                        {
                            "internalType": "uint40",
                            "name": "lastUpdateTimestamp",
                            "type": "uint40",
                        },
                        {
                            "internalType": "address",
                            "name": "aTokenAddress",
                            "type": "address",
                        },
                        {
                            "internalType": "address",
                            "name": "stableDebtTokenAddress",
                            "type": "address",
                        },
                        {
                            "internalType": "address",
                            "name": "variableDebtTokenAddress",
                            "type": "address",
                        },
                        {
                            "internalType": "address",
                            "name": "interestRateStrategyAddress",
                            "type": "address",
                        },
                        {"internalType": "uint8", "name": "id", "type": "uint8"},
                    ],
                    "internalType": "struct DataTypes.ReserveData",
                    "name": "",
                    "type": "tuple",
                }
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "address", "name": "asset", "type": "address"}],
            "name": "getReserveNormalizedIncome",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "address", "name": "asset", "type": "address"}],
            "name": "getReserveNormalizedVariableDebt",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "getReservesList",
            "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
            "name": "getUserAccountData",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "totalCollateralETH",
                    "type": "uint256",
                },
                {"internalType": "uint256", "name": "totalDebtETH", "type": "uint256"},
                {
                    "internalType": "uint256",
                    "name": "availableBorrowsETH",
                    "type": "uint256",
                },
                {
                    "internalType": "uint256",
                    "name": "currentLiquidationThreshold",
                    "type": "uint256",
                },
                {"internalType": "uint256", "name": "ltv", "type": "uint256"},
                {"internalType": "uint256", "name": "healthFactor", "type": "uint256"},
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
            "name": "getUserConfiguration",
            "outputs": [
                {
                    "components": [
                        {"internalType": "uint256", "name": "data", "type": "uint256"}
                    ],
                    "internalType": "struct DataTypes.UserConfigurationMap",
                    "name": "",
                    "type": "tuple",
                }
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "reserve", "type": "address"},
                {"internalType": "address", "name": "aTokenAddress", "type": "address"},
                {"internalType": "address", "name": "stableDebtAddress", "type": "address"},
                {
                    "internalType": "address",
                    "name": "variableDebtAddress",
                    "type": "address",
                },
                {
                    "internalType": "address",
                    "name": "interestRateStrategyAddress",
                    "type": "address",
                },
            ],
            "name": "initReserve",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "collateralAsset", "type": "address"},
                {"internalType": "address", "name": "debtAsset", "type": "address"},
                {"internalType": "address", "name": "user", "type": "address"},
                {"internalType": "uint256", "name": "debtToCover", "type": "uint256"},
                {"internalType": "bool", "name": "receiveAToken", "type": "bool"},
            ],
            "name": "liquidationCall",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "paused",
            "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "address", "name": "user", "type": "address"},
            ],
            "name": "rebalanceStableBorrowRate",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"},
                {"internalType": "uint256", "name": "rateMode", "type": "uint256"},
                {"internalType": "address", "name": "onBehalfOf", "type": "address"},
            ],
            "name": "repay",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "reserve", "type": "address"},
                {"internalType": "uint256", "name": "configuration", "type": "uint256"},
            ],
            "name": "setConfiguration",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "bool", "name": "val", "type": "bool"}],
            "name": "setPause",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "reserve", "type": "address"},
                {
                    "internalType": "address",
                    "name": "rateStrategyAddress",
                    "type": "address",
                },
            ],
            "name": "setReserveInterestRateStrategyAddress",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "bool", "name": "useAsCollateral", "type": "bool"},
            ],
            "name": "setUserUseReserveAsCollateral",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "uint256", "name": "rateMode", "type": "uint256"},
            ],
            "name": "swapBorrowRateMode",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"},
                {"internalType": "address", "name": "to", "type": "address"},
            ],
            "name": "withdraw",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]

    aave_price_oracle_abi = [
        {
            "inputs": [
                {
                    "internalType": "address[]",
                    "name": "_assets",
                    "type": "address[]"
                },
                {
                    "internalType": "address[]",
                    "name": "_sources",
                    "type": "address[]"
                },
                {
                    "internalType": "address",
                    "name": "_fallbackOracle",
                    "type": "address"
                }
            ],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "constructor"
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "asset",
                    "type": "address"
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "source",
                    "type": "address"
                }
            ],
            "name": "AssetSourceUpdated",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "fallbackOracle",
                    "type": "address"
                }
            ],
            "name": "FallbackOracleUpdated",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "previousOwner",
                    "type": "address"
                },
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "newOwner",
                    "type": "address"
                }
            ],
            "name": "OwnershipTransferred",
            "type": "event"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "isOwner",
            "outputs": [
                {
                    "internalType": "bool",
                    "name": "",
                    "type": "bool"
                }
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "owner",
            "outputs": [
                {
                    "internalType": "address",
                    "name": "",
                    "type": "address"
                }
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [],
            "name": "renounceOwnership",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {
                    "internalType": "address",
                    "name": "newOwner",
                    "type": "address"
                }
            ],
            "name": "transferOwnership",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {
                    "internalType": "address[]",
                    "name": "_assets",
                    "type": "address[]"
                },
                {
                    "internalType": "address[]",
                    "name": "_sources",
                    "type": "address[]"
                }
            ],
            "name": "setAssetSources",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {
                    "internalType": "address",
                    "name": "_fallbackOracle",
                    "type": "address"
                }
            ],
            "name": "setFallbackOracle",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {
                    "internalType": "address",
                    "name": "_asset",
                    "type": "address"
                }
            ],
            "name": "getAssetPrice",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "",
                    "type": "uint256"
                }
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {
                    "internalType": "address[]",
                    "name": "_assets",
                    "type": "address[]"
                }
            ],
            "name": "getAssetsPrices",
            "outputs": [
                {
                    "internalType": "uint256[]",
                    "name": "",
                    "type": "uint256[]"
                }
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {
                    "internalType": "address",
                    "name": "_asset",
                    "type": "address"
                }
            ],
            "name": "getSourceOfAsset",
            "outputs": [
                {
                    "internalType": "address",
                    "name": "",
                    "type": "address"
                }
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "getFallbackOracle",
            "outputs": [
                {
                    "internalType": "address",
                    "name": "",
                    "type": "address"
                }
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        }
    ]

    pool_data_provider_abi = [{"inputs":[{"internalType":"contract IPoolAddressesProvider","name":"addressesProvider","type":"address"}],"stateMutability":"nonpayable","type":"constructor"},{"inputs":[],"name":"ADDRESSES_PROVIDER","outputs":[{"internalType":"contract IPoolAddressesProvider","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getATokenTotalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getAllATokens","outputs":[{"components":[{"internalType":"string","name":"symbol","type":"string"},{"internalType":"address","name":"tokenAddress","type":"address"}],"internalType":"struct AaveProtocolDataProvider.TokenData[]","name":"","type":"tuple[]"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getAllReservesTokens","outputs":[{"components":[{"internalType":"string","name":"symbol","type":"string"},{"internalType":"address","name":"tokenAddress","type":"address"}],"internalType":"struct AaveProtocolDataProvider.TokenData[]","name":"","type":"tuple[]"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getDebtCeiling","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getDebtCeilingDecimals","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"pure","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getInterestRateStrategyAddress","outputs":[{"internalType":"address","name":"irStrategyAddress","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getLiquidationProtocolFee","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getPaused","outputs":[{"internalType":"bool","name":"isPaused","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getReserveCaps","outputs":[{"internalType":"uint256","name":"borrowCap","type":"uint256"},{"internalType":"uint256","name":"supplyCap","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getReserveConfigurationData","outputs":[{"internalType":"uint256","name":"decimals","type":"uint256"},{"internalType":"uint256","name":"ltv","type":"uint256"},{"internalType":"uint256","name":"liquidationThreshold","type":"uint256"},{"internalType":"uint256","name":"liquidationBonus","type":"uint256"},{"internalType":"uint256","name":"reserveFactor","type":"uint256"},{"internalType":"bool","name":"usageAsCollateralEnabled","type":"bool"},{"internalType":"bool","name":"borrowingEnabled","type":"bool"},{"internalType":"bool","name":"stableBorrowRateEnabled","type":"bool"},{"internalType":"bool","name":"isActive","type":"bool"},{"internalType":"bool","name":"isFrozen","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getReserveData","outputs":[{"internalType":"uint256","name":"unbacked","type":"uint256"},{"internalType":"uint256","name":"accruedToTreasuryScaled","type":"uint256"},{"internalType":"uint256","name":"totalAToken","type":"uint256"},{"internalType":"uint256","name":"totalStableDebt","type":"uint256"},{"internalType":"uint256","name":"totalVariableDebt","type":"uint256"},{"internalType":"uint256","name":"liquidityRate","type":"uint256"},{"internalType":"uint256","name":"variableBorrowRate","type":"uint256"},{"internalType":"uint256","name":"stableBorrowRate","type":"uint256"},{"internalType":"uint256","name":"averageStableBorrowRate","type":"uint256"},{"internalType":"uint256","name":"liquidityIndex","type":"uint256"},{"internalType":"uint256","name":"variableBorrowIndex","type":"uint256"},{"internalType":"uint40","name":"lastUpdateTimestamp","type":"uint40"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getReserveEModeCategory","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getReserveTokensAddresses","outputs":[{"internalType":"address","name":"aTokenAddress","type":"address"},{"internalType":"address","name":"stableDebtTokenAddress","type":"address"},{"internalType":"address","name":"variableDebtTokenAddress","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getSiloedBorrowing","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getTotalDebt","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getUnbackedMintCap","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"address","name":"user","type":"address"}],"name":"getUserReserveData","outputs":[{"internalType":"uint256","name":"currentATokenBalance","type":"uint256"},{"internalType":"uint256","name":"currentStableDebt","type":"uint256"},{"internalType":"uint256","name":"currentVariableDebt","type":"uint256"},{"internalType":"uint256","name":"principalStableDebt","type":"uint256"},{"internalType":"uint256","name":"scaledVariableDebt","type":"uint256"},{"internalType":"uint256","name":"stableBorrowRate","type":"uint256"},{"internalType":"uint256","name":"liquidityRate","type":"uint256"},{"internalType":"uint40","name":"stableRateLastUpdated","type":"uint40"},{"internalType":"bool","name":"usageAsCollateralEnabled","type":"bool"}],"stateMutability":"view","type":"function"}]

    pool_abi = [{"inputs":[{"internalType":"contract IPoolAddressesProvider","name":"provider","type":"address"}],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":True,"internalType":"address","name":"backer","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"fee","type":"uint256"}],"name":"BackUnbacked","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":False,"internalType":"address","name":"user","type":"address"},{"indexed":True,"internalType":"address","name":"onBehalfOf","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":False,"internalType":"enum DataTypes.InterestRateMode","name":"interestRateMode","type":"uint8"},{"indexed":False,"internalType":"uint256","name":"borrowRate","type":"uint256"},{"indexed":True,"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"Borrow","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"target","type":"address"},{"indexed":False,"internalType":"address","name":"initiator","type":"address"},{"indexed":True,"internalType":"address","name":"asset","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":False,"internalType":"enum DataTypes.InterestRateMode","name":"interestRateMode","type":"uint8"},{"indexed":False,"internalType":"uint256","name":"premium","type":"uint256"},{"indexed":True,"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"FlashLoan","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"asset","type":"address"},{"indexed":False,"internalType":"uint256","name":"totalDebt","type":"uint256"}],"name":"IsolationModeTotalDebtUpdated","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"collateralAsset","type":"address"},{"indexed":True,"internalType":"address","name":"debtAsset","type":"address"},{"indexed":True,"internalType":"address","name":"user","type":"address"},{"indexed":False,"internalType":"uint256","name":"debtToCover","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"liquidatedCollateralAmount","type":"uint256"},{"indexed":False,"internalType":"address","name":"liquidator","type":"address"},{"indexed":False,"internalType":"bool","name":"receiveAToken","type":"bool"}],"name":"LiquidationCall","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":False,"internalType":"address","name":"user","type":"address"},{"indexed":True,"internalType":"address","name":"onBehalfOf","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":True,"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"MintUnbacked","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":False,"internalType":"uint256","name":"amountMinted","type":"uint256"}],"name":"MintedToTreasury","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":True,"internalType":"address","name":"user","type":"address"}],"name":"RebalanceStableBorrowRate","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":True,"internalType":"address","name":"user","type":"address"},{"indexed":True,"internalType":"address","name":"repayer","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":False,"internalType":"bool","name":"useATokens","type":"bool"}],"name":"Repay","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":False,"internalType":"uint256","name":"liquidityRate","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"stableBorrowRate","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"variableBorrowRate","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"liquidityIndex","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"variableBorrowIndex","type":"uint256"}],"name":"ReserveDataUpdated","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":True,"internalType":"address","name":"user","type":"address"}],"name":"ReserveUsedAsCollateralDisabled","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":True,"internalType":"address","name":"user","type":"address"}],"name":"ReserveUsedAsCollateralEnabled","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":False,"internalType":"address","name":"user","type":"address"},{"indexed":True,"internalType":"address","name":"onBehalfOf","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":True,"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"Supply","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":True,"internalType":"address","name":"user","type":"address"},{"indexed":False,"internalType":"enum DataTypes.InterestRateMode","name":"interestRateMode","type":"uint8"}],"name":"SwapBorrowRateMode","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"user","type":"address"},{"indexed":False,"internalType":"uint8","name":"categoryId","type":"uint8"}],"name":"UserEModeSet","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"reserve","type":"address"},{"indexed":True,"internalType":"address","name":"user","type":"address"},{"indexed":True,"internalType":"address","name":"to","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"}],"name":"Withdraw","type":"event"},{"inputs":[],"name":"ADDRESSES_PROVIDER","outputs":[{"internalType":"contract IPoolAddressesProvider","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"BRIDGE_PROTOCOL_FEE","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"FLASHLOAN_PREMIUM_TOTAL","outputs":[{"internalType":"uint128","name":"","type":"uint128"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"FLASHLOAN_PREMIUM_TO_PROTOCOL","outputs":[{"internalType":"uint128","name":"","type":"uint128"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"MAX_NUMBER_RESERVES","outputs":[{"internalType":"uint16","name":"","type":"uint16"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"MAX_STABLE_RATE_BORROW_SIZE_PERCENT","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"POOL_REVISION","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"fee","type":"uint256"}],"name":"backUnbacked","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"interestRateMode","type":"uint256"},{"internalType":"uint16","name":"referralCode","type":"uint16"},{"internalType":"address","name":"onBehalfOf","type":"address"}],"name":"borrow","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint8","name":"id","type":"uint8"},{"components":[{"internalType":"uint16","name":"ltv","type":"uint16"},{"internalType":"uint16","name":"liquidationThreshold","type":"uint16"},{"internalType":"uint16","name":"liquidationBonus","type":"uint16"},{"internalType":"address","name":"priceSource","type":"address"},{"internalType":"string","name":"label","type":"string"}],"internalType":"struct DataTypes.EModeCategory","name":"category","type":"tuple"}],"name":"configureEModeCategory","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"address","name":"onBehalfOf","type":"address"},{"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"deposit","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"dropReserve","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"balanceFromBefore","type":"uint256"},{"internalType":"uint256","name":"balanceToBefore","type":"uint256"}],"name":"finalizeTransfer","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"receiverAddress","type":"address"},{"internalType":"address[]","name":"assets","type":"address[]"},{"internalType":"uint256[]","name":"amounts","type":"uint256[]"},{"internalType":"uint256[]","name":"interestRateModes","type":"uint256[]"},{"internalType":"address","name":"onBehalfOf","type":"address"},{"internalType":"bytes","name":"params","type":"bytes"},{"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"flashLoan","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"receiverAddress","type":"address"},{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"bytes","name":"params","type":"bytes"},{"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"flashLoanSimple","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getConfiguration","outputs":[{"components":[{"internalType":"uint256","name":"data","type":"uint256"}],"internalType":"struct DataTypes.ReserveConfigurationMap","name":"","type":"tuple"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint8","name":"id","type":"uint8"}],"name":"getEModeCategoryData","outputs":[{"components":[{"internalType":"uint16","name":"ltv","type":"uint16"},{"internalType":"uint16","name":"liquidationThreshold","type":"uint16"},{"internalType":"uint16","name":"liquidationBonus","type":"uint16"},{"internalType":"address","name":"priceSource","type":"address"},{"internalType":"string","name":"label","type":"string"}],"internalType":"struct DataTypes.EModeCategory","name":"","type":"tuple"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint16","name":"id","type":"uint16"}],"name":"getReserveAddressById","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getReserveData","outputs":[{"components":[{"components":[{"internalType":"uint256","name":"data","type":"uint256"}],"internalType":"struct DataTypes.ReserveConfigurationMap","name":"configuration","type":"tuple"},{"internalType":"uint128","name":"liquidityIndex","type":"uint128"},{"internalType":"uint128","name":"currentLiquidityRate","type":"uint128"},{"internalType":"uint128","name":"variableBorrowIndex","type":"uint128"},{"internalType":"uint128","name":"currentVariableBorrowRate","type":"uint128"},{"internalType":"uint128","name":"currentStableBorrowRate","type":"uint128"},{"internalType":"uint40","name":"lastUpdateTimestamp","type":"uint40"},{"internalType":"uint16","name":"id","type":"uint16"},{"internalType":"address","name":"aTokenAddress","type":"address"},{"internalType":"address","name":"stableDebtTokenAddress","type":"address"},{"internalType":"address","name":"variableDebtTokenAddress","type":"address"},{"internalType":"address","name":"interestRateStrategyAddress","type":"address"},{"internalType":"uint128","name":"accruedToTreasury","type":"uint128"},{"internalType":"uint128","name":"unbacked","type":"uint128"},{"internalType":"uint128","name":"isolationModeTotalDebt","type":"uint128"}],"internalType":"struct DataTypes.ReserveData","name":"","type":"tuple"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getReserveNormalizedIncome","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getReserveNormalizedVariableDebt","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getReservesList","outputs":[{"internalType":"address[]","name":"","type":"address[]"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"user","type":"address"}],"name":"getUserAccountData","outputs":[{"internalType":"uint256","name":"totalCollateralBase","type":"uint256"},{"internalType":"uint256","name":"totalDebtBase","type":"uint256"},{"internalType":"uint256","name":"availableBorrowsBase","type":"uint256"},{"internalType":"uint256","name":"currentLiquidationThreshold","type":"uint256"},{"internalType":"uint256","name":"ltv","type":"uint256"},{"internalType":"uint256","name":"healthFactor","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"user","type":"address"}],"name":"getUserConfiguration","outputs":[{"components":[{"internalType":"uint256","name":"data","type":"uint256"}],"internalType":"struct DataTypes.UserConfigurationMap","name":"","type":"tuple"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"user","type":"address"}],"name":"getUserEMode","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"address","name":"aTokenAddress","type":"address"},{"internalType":"address","name":"stableDebtAddress","type":"address"},{"internalType":"address","name":"variableDebtAddress","type":"address"},{"internalType":"address","name":"interestRateStrategyAddress","type":"address"}],"name":"initReserve","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"contract IPoolAddressesProvider","name":"provider","type":"address"}],"name":"initialize","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"collateralAsset","type":"address"},{"internalType":"address","name":"debtAsset","type":"address"},{"internalType":"address","name":"user","type":"address"},{"internalType":"uint256","name":"debtToCover","type":"uint256"},{"internalType":"bool","name":"receiveAToken","type":"bool"}],"name":"liquidationCall","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address[]","name":"assets","type":"address[]"}],"name":"mintToTreasury","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"address","name":"onBehalfOf","type":"address"},{"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"mintUnbacked","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"address","name":"user","type":"address"}],"name":"rebalanceStableBorrowRate","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"interestRateMode","type":"uint256"},{"internalType":"address","name":"onBehalfOf","type":"address"}],"name":"repay","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"interestRateMode","type":"uint256"}],"name":"repayWithATokens","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"interestRateMode","type":"uint256"},{"internalType":"address","name":"onBehalfOf","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"permitV","type":"uint8"},{"internalType":"bytes32","name":"permitR","type":"bytes32"},{"internalType":"bytes32","name":"permitS","type":"bytes32"}],"name":"repayWithPermit","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"rescueTokens","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"resetIsolationModeTotalDebt","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"components":[{"internalType":"uint256","name":"data","type":"uint256"}],"internalType":"struct DataTypes.ReserveConfigurationMap","name":"configuration","type":"tuple"}],"name":"setConfiguration","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"address","name":"rateStrategyAddress","type":"address"}],"name":"setReserveInterestRateStrategyAddress","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint8","name":"categoryId","type":"uint8"}],"name":"setUserEMode","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"bool","name":"useAsCollateral","type":"bool"}],"name":"setUserUseReserveAsCollateral","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"address","name":"onBehalfOf","type":"address"},{"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"supply","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"address","name":"onBehalfOf","type":"address"},{"internalType":"uint16","name":"referralCode","type":"uint16"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"permitV","type":"uint8"},{"internalType":"bytes32","name":"permitR","type":"bytes32"},{"internalType":"bytes32","name":"permitS","type":"bytes32"}],"name":"supplyWithPermit","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"interestRateMode","type":"uint256"}],"name":"swapBorrowRateMode","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"protocolFee","type":"uint256"}],"name":"updateBridgeProtocolFee","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint128","name":"flashLoanPremiumTotal","type":"uint128"},{"internalType":"uint128","name":"flashLoanPremiumToProtocol","type":"uint128"}],"name":"updateFlashloanPremiums","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"address","name":"to","type":"address"}],"name":"withdraw","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]