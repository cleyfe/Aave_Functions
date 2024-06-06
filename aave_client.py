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

from concurrent.futures import ThreadPoolExecutor

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
                self.active_network = KovanConfig(KOVAN_RPC_URL, self) 
            elif MAINNET_RPC_URL is not None:
                self.active_network = MainnetConfig(MAINNET_RPC_URL, self)
            elif MUMBAI_RPC_URL is not None:
                self.active_network = MumbaiConfig(MUMBAI_RPC_URL, self)
            elif POLYGON_RPC_URL is not None:
                self.active_network = PolygonConfig(POLYGON_RPC_URL, self)
            elif ARBITRUM_RPC_URL is not None:
                self.active_network = ArbitrumConfig(ARBITRUM_RPC_URL, self)

        self.w3 = self._connect()
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        if GAS_STRATEGY.lower() == "fast":
            self.w3.eth.set_gas_price_strategy(fast_gas_price_strategy)
            self.timeout = 60
        elif GAS_STRATEGY.lower() == "medium":
            self.w3.eth.set_gas_price_strategy(medium_gas_price_strategy)
            self.timeout = 60 * 5
        elif GAS_STRATEGY.lower() == "slow":
            self.w3.eth.set_gas_price_strategy(slow_gas_price_strategy)
            self.timeout = 60 * 60
        elif GAS_STRATEGY.lower() == "glacial":
            self.w3.eth.set_gas_price_strategy(glacial_gas_price_strategy)
            self.timeout = 60 * 1440
        else:
            raise ValueError("Invalid gas strategy. Available gas strategies are 'fast', 'medium', 'slow', or 'glacial'")

        self.active_network.aave_tokens = self.active_network.fetch_aave_tokens()

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

    def approve_erc20(self, erc20_address: str, spender_address: str, amount_in_decimal_units: int, nonce=None) -> tuple:
        """
        Approve the smart contract to take the tokens out of the wallet
        For lending pool transactions, the 'spender_address' is the lending pool contract's address.

        Returns a tuple of the following:
            (transaction hash string, approval gas cost)
        """
        nonce = nonce if nonce else self.w3.eth.get_transaction_count(self.wallet_address)

        spender_address = self.w3.to_checksum_address(spender_address)
        erc20_address = self.w3.to_checksum_address(erc20_address)
        erc20 = self.w3.eth.contract(address=erc20_address, abi=ABIReference.erc20_abi)
        function_call = erc20.functions.approve(spender_address, amount_in_decimal_units)
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

        print(f"Approved {amount_in_decimal_units} of {erc20_address} for contract {spender_address}")
        return tx_hash.hex(), self.w3.from_wei(int(receipt['effectiveGasPrice']) * int(receipt['gasUsed']), 'ether')

    def withdraw(self, withdraw_token: ReserveToken, withdraw_amount: float,
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
        lending_pool_contract = self.get_lending_pool()


        print(f"Approving transaction to withdraw {withdraw_amount:.{withdraw_token.decimals}f} of {withdraw_token.symbol} from Aave...")
        try:
            approval_hash, approval_gas = self.approve_erc20(erc20_address=withdraw_token.address,
                                                             spender_address=lending_pool_contract.address,
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

    def deposit(self, deposit_token: ReserveToken, deposit_amount: float, nonce=None) -> AaveTrade:
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

        Smart Contract Reference ((outdated)):
            https://docs.aave.com/developers/v/2.0/the-core-protocol/lendingpool#deposit
        """
        
        '''
        replace a stuck tx. The line below must be used if error "Replacement transaction underpriced"
        if tx doesnt go through and last indefinitely --> set GAS_STRATEGY to 'fast' in deposit_collateral_example.py script
        '''
        gasPrice = self.w3.eth.gas_price
        lending_pool_contract = self.get_lending_pool()
        
        nonce = nonce if nonce else self.w3.eth.get_transaction_count(self.wallet_address)

        amount_in_decimal_units = self.convert_to_decimal_units(deposit_token, deposit_amount)

        print(f"Approving transaction to deposit {deposit_amount} of {deposit_token.symbol} to Aave...")
        try:
            approval_hash, approval_gas = self.approve_erc20(erc20_address=self.w3.to_checksum_address(deposit_token.address),
                                                             spender_address=self.w3.to_checksum_address(lending_pool_contract.address),
                                                             amount_in_decimal_units=amount_in_decimal_units,
                                                             nonce=nonce)
            print("Transaction approved!")
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

        #available_borrow_base = self.w3.from_wei(available_borrow_base, "ether")
        #total_collateral_base = self.w3.from_wei(total_collateral_base, "ether")
        #total_debt_base = self.w3.from_wei(total_debt_base, "ether")
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
            - getUserReserveData(address asset, address user): output is described below
            - getReserveTokensAddresses(address asset)
            - getInterestRateStrategyAddress(address asset)


            if function is getUserReserveData, output has 9 values:
                1) The current AToken balance of the user
                2) The current stable debt of the user
                3) The current variable debt of the user
                4) The principal stable debt of the user
                5) The scaled variable debt of the user
                6) The stable borrow rate of the user
                7) The liquidity rate of the reserve
                8) The timestamp of the last update of the user stable rate
                9) True if the user is using the asset as collateral, else false

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
                    
                    def from_market_base_ccy(value):
                        return value / 10**8

                    result = {
                        "totalCollateralBase": from_market_base_ccy(totalCollateralBase),
                        "totalDebtBase": from_market_base_ccy(totalDebtBase),
                        "availableBorrowsBase": from_market_base_ccy(availableBorrowsBase),
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

    def get_wallet_balance_data(self, function_name="getReserveData", *args, **kwargs) -> dict:
        """
        Implements a logic of getting multiple tokens balance for one user address.

        Parameters:
        - function_name: defines the function we want to call from the contract. Possible function
        names are:
            - balanceOf(address user, address token): Returns the balance of the token for user (ETH included with 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE).
            - batchBalanceOf(address[] calldata users, address[] calldata tokens): Returns balances for a list of users and tokens (ETH included with MOCK_ETH_ADDRESS).
            - getUserWalletBalances(address provider, address user): Provides balances of user wallet for all reserves available on the pool
            ...

        https://docs.aave.com/developers/periphery-contracts/walletbalanceprovider
        """
        wallet_balance_provider = self.w3.to_checksum_address(self.active_network.wallet_balance_provider)
        
        wallet_balance_contract = self.w3.eth.contract(address=wallet_balance_provider, abi=ABIReference.wallet_balance_provide_abi)
        
        try:
            # Get the function dynamically
            contract_function = getattr(wallet_balance_contract.functions, function_name)
            # Call the function with provided arguments
            result = contract_function(*args, **kwargs).call()

            # Handle specific case for getReserveData
            
        except AttributeError:
            raise ValueError(f"Method {function_name} does not exist in the contract.")
        except Exception as e:
            raise Exception(f"An error occurred while calling the method {function_name}: {e}")

        return result

    def get_asset_price(self, base_address: str, quote_address: str = None) -> float:
            """
            If quote_address is None, returns the asset price in Ether
            If quote_address is not None, returns the pair price of BASE/QUOTE

            https://docs.aave.com/developers/v/2.0/the-core-protocol/price-oracle#getassetprice
            """

            # For calling Chainlink price feeds (Deprecated):
            # link_eth_address = Web3.toChecksumAddress(self.active_network.link_eth_price_feed)
            # link_eth_price_feed = self.w3.eth.contract(
            #     address=link_eth_address, abi=ABIReference.price_feed_abi)
            # latest_price = Web3.fromWei(link_eth_price_feed.functions.latestRoundData().call()[1], "ether")
            # print(f"The LINK/ETH price is {latest_price}")

            # For calling the Aave price oracle:
            price_oracle_address = self.w3.eth.contract(
                address=Web3.toChecksumAddress(self.active_network.lending_pool_addresses_provider),
                abi=ABIReference.lending_pool_addresses_provider_abi,
            ).functions.getPriceOracle().call()

            price_oracle_contract = self.w3.eth.contract(
                address=price_oracle_address, abi=ABIReference.aave_price_oracle_abi
            )

            latest_price = Web3.fromWei(int(price_oracle_contract.functions.getAssetPrice(base_address).call()),
                                        'ether')
            if quote_address is not None:
                quote_price = Web3.fromWei(int(price_oracle_contract.functions.getAssetPrice(quote_address).call()),
                                        'ether')
                latest_price = latest_price / quote_price
            return float(latest_price)

    def borrow(self, lending_pool_contract, borrow_amount: float, borrow_asset: ReserveToken,
            nonce=None, interest_rate_mode: str = "variable") -> AaveTrade:
        """
        Borrows the underlying asset (erc20_address) as long as the amount is within the confines of
        the user's buying power.

        Parameters:
            lending_pool_contract: The web3.eth.Contract class object fetched from the self.get_lending_pool function.
            borrow_amount: Amount of the underlying asset to borrow. The amount should be measured in the asset's
                        currency (e.g. for ETH, borrow_amount=0.05, as in 0.05 ETH)
            borrow_asset: The ReserveToken which you want to borrow from Aave. To get the reserve token, you can use the
                        self.get_reserve_token(symbol: str) function.
            nonce: Manually specify the transaction count/ID. Leave as None to get the current transaction count from
                the user's wallet set at self.wallet_address.
            interest_rate_mode: The type of Aave interest rate mode for borrow debt, with the options being a 'stable'
                                or 'variable' interest rate.

        Returns:
            The AaveTrade object - See line 52 for datapoints reference

        Smart Contract Docs:
        https://docs.aave.com/developers/v/2.0/the-core-protocol/lendingpool#borrow
        """
        
        print("Let's borrow...")

        rate_mode_str = interest_rate_mode
        if interest_rate_mode.lower() == "stable":
            interest_rate_mode = 1
        elif interest_rate_mode.lower() == "variable":
            interest_rate_mode = 2
        else:
            raise ValueError(f"Invalid interest rate mode passed to the borrow_erc20 function ({interest_rate_mode}) - "
                            f"Valid interest rate modes are 'stable' and 'variable'")

        # Calculate amount to borrow in decimal units:
        borrow_amount_in_decimal_units = self.convert_to_decimal_units(borrow_asset, borrow_amount)

        # Create and send transaction to borrow assets against collateral:
        print(f"\nCreating transaction to borrow {borrow_amount:.{borrow_asset.decimals}f} {borrow_asset.symbol}...")
        function_call = lending_pool_contract.functions.borrow(
            self.w3.to_checksum_address(borrow_asset.address),
            borrow_amount_in_decimal_units,
            interest_rate_mode, 0,
            # 0 must not be changed, it is deprecated
            self.w3.to_checksum_address(self.wallet_address))
        
        transaction = function_call.build_transaction(
            {
                "chainId": self.active_network.chain_id,
                "from": self.wallet_address,
                "nonce": nonce if nonce else self.w3.eth.get_transaction_count(self.wallet_address),
            }
        )
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction, private_key=self.private_key
        )
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        receipt = self.process_transaction_receipt(tx_hash, borrow_amount, borrow_asset, operation="Borrow",
                                                interest_rate_mode=rate_mode_str)

        print(f"\nBorrowed {borrow_amount:.{borrow_asset.decimals}f} of {borrow_asset.symbol}")
        print(f"Remaining Borrowing Power: {self.get_user_data(lending_pool_contract)[0]:.18f}")
        print(f"Transaction Hash: {tx_hash.hex()}")
        return receipt

    def convert_to_decimal_units(self, reserve_token: ReserveToken, token_amount: float) -> int:
        """integer units i.e amt * 10 ^ (decimal units of the token). So, 1.2 USDC will be 1.2 * 10 ^ 6"""
        return int(token_amount * (10 ** int(reserve_token.decimals)))

    def convert_from_decimal_units(self, reserve_token: ReserveToken, token_amount: float) -> int:
        """integer units i.e amt * 10 ^ (decimal units of the token). So, 1.2 USDC will be 1.2 * 10 ^ 6"""
        return float(token_amount / (10 ** int(reserve_token.decimals)))

    def borrow_percentage(self, lending_pool_contract, borrow_percentage: float,
                        borrow_asset: ReserveToken, nonce=None, interest_rate_mode: str = "variable") -> AaveTrade:
        """Same parameters as the self.borrow() function, except instead of 'borrow_amount', you will pass the
        percentage of borrowing power that you would like to borrow from in the 'borrow_percentage' parameter in the
        following format: 0.0 (0% of borrowing power) to 1.0 (100% of borrowing power)"""

        if borrow_percentage > 1.0:
            raise ValueError("Cannot borrow more than 100% of borrowing power. Please pass a value between 0.0 and 1.0")

        # Calculate borrow amount from available borrow percentage:
        total_borrowable_in_eth = self.get_user_data(lending_pool_contract)[0]
        weth_to_borrow_asset = self.get_asset_price(base_address=self.get_reserve_token("WETH").address,
                                                    quote_address=borrow_asset.address)
        borrow_amount = weth_to_borrow_asset * (total_borrowable_in_eth * borrow_percentage)
        print(f"Borrowing {borrow_percentage * 100}% of total borrowing power: "
            f"{borrow_amount:.{borrow_asset.decimals}f} {borrow_asset.symbol}")

        return self.borrow(lending_pool_contract=lending_pool_contract, borrow_amount=borrow_amount,
                        borrow_asset=borrow_asset, nonce=nonce, interest_rate_mode=interest_rate_mode)

    def repay(self, lending_pool_contract, repay_amount: float, repay_asset: ReserveToken,
            nonce=None, interest_rate_mode: str = "variable") -> AaveTrade:
        """
        Parameters:
            lending_pool_contract: The web3.eth.Contract object returned by the self.get_lending_pool() function.
            repay_amount: The amount of the target asset to repay. (e.g. 0.5 DAI)
            repay_asset: The ReserveToken object for the target asset to repay. Use self.get_reserve_token("SYMBOL") to
                        get the ReserveToken object.
            nonce: Manually specify the transaction count/ID. Leave as None to get the current transaction count from
                the user's wallet set at self.wallet_address.
            interest_rate_mode: the type of borrow debt,'stable' or 'variable'

        Returns:
            The AaveTrade object - See line 52 for datapoints reference

        https://docs.aave.com/developers/v/2.0/the-core-protocol/lendingpool#repay
        """
        print("Time to repay...")

        rate_mode_str = interest_rate_mode
        if interest_rate_mode == "stable":
            interest_rate_mode = 1
        else:
            interest_rate_mode = 2

        amount_in_decimal_units = self.convert_to_decimal_units(repay_asset, repay_amount)

        # First, attempt to approve the transaction:
        print(f"Approving transaction to repay {repay_amount} of {repay_asset.symbol} to Aave...")
        try:
            approval_hash, approval_gas = self.approve_erc20(erc20_address=self.w3.to_checksum_address(repay_asset.address),
                                                            spender_address=self.w3.to_checksum_address(lending_pool_contract.address),
                                                            amount_in_decimal_units=amount_in_decimal_units,
                                                            nonce=nonce)
            print("Transaction approved!")
        except Exception as exc:
            raise UserWarning(f"Could not approve repay transaction - Error Code {exc}")

        print(f"Repaying {repay_amount} of {repay_asset.symbol}...")
        function_call = lending_pool_contract.functions.repay(
            self.w3.to_checksum_address(repay_asset.address),
            amount_in_decimal_units,
            interest_rate_mode,  # the the interest rate mode
            self.w3.to_checksum_address(self.wallet_address),
        )
        #print("Building transaction from function call...")
        transaction = function_call.build_transaction(
            {
                "chainId": self.active_network.chain_id,
                "from": self.wallet_address,
                "nonce": nonce if nonce else self.w3.eth.get_transaction_count(self.wallet_address),
            }
        )
        #print("Repaying...")
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction, private_key=self.private_key
        )
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        receipt = self.process_transaction_receipt(tx_hash, repay_amount, repay_asset, "Repay",
                                                interest_rate_mode=rate_mode_str, approval_gas_cost=approval_gas)
        print(f"Repaid {repay_amount} {repay_asset.symbol}  |  "
            f"{self.get_user_data(lending_pool_contract)[1]:.18f} ETH worth of debt remaining.")
        return receipt

    def repay_percentage(self, lending_pool_contract, repay_percentage: float,
                        repay_asset: ReserveToken, nonce=None) -> AaveTrade:
        """
        Same parameters as the self.repay() function, except instead of 'repay_amount', you will pass the
        percentage of outstanding debt that you would like to repay from in the 'repay_percentage' parameter using the
        following format:

        0.0 (0% of borrowing power) to 1.0 (100% of borrowing power)
        """

        if repay_percentage > 1.0:
            raise ValueError("Cannot repay more than 100% of debts. Please pass a value between 0.0 and 1.0")

        # Calculate debt amount from outstanding debt percentage:
        total_debt_in_eth = self.get_user_data(lending_pool_contract)[1]
        weth_to_repay_asset = self.get_asset_price(base_address=self.get_reserve_token("WETH").address,
                                                quote_address=repay_asset.address)
        repay_amount = weth_to_repay_asset * (total_debt_in_eth * repay_percentage)

        return self.repay(lending_pool_contract, repay_amount, repay_asset, nonce)

    def get_abi(self, smart_contract_address: str):
        """
        Used to fetch the JSON ABIs for the deployed Aave smart contracts here:
        https://docs.aave.com/developers/v/2.0/deployed-contracts/deployed-contracts
        """
        print(f"Fetching ABI for smart contract: {smart_contract_address}")
        abi_endpoint = f'https://api.etherscan.io/api?module=contract&action=getabi&address={smart_contract_address}'

        retry_count = 0
        json_abi = None
        err = None
        while retry_count < 5:
            etherscan_response = requests.get(abi_endpoint).json()
            if str(etherscan_response['status']) == '0':
                err = etherscan_response['result']
                retry_count += 1
                time.sleep(1)
            else:
                try:
                    json_abi = json.loads(etherscan_response['result'])
                except json.decoder.JSONDecodeError:
                    err = "Could not load ABI into JSON format"
                except Exception as exc:
                    err = f"Response status was valid, but an unexpected error occurred '{exc}'"
                finally:
                    break
        if json_abi is not None:
            return json_abi
        else:
            raise Exception(f"could not fetch ABI for contract: {smart_contract_address} - Error: {err}")

    def get_reserve_token(self, symbol: str) -> ReserveToken:
        """Returns the ReserveToken class containing the Aave reserve token with the passed symbol"""
        try:
            return [token for token in self.active_network.aave_tokens
                    if token.symbol.lower() == symbol.lower() or token.aTokenSymbol.lower() == symbol.lower()][0]
        except IndexError:
            raise ValueError(
                f"Could not match '{symbol}' with a valid reserve token on aave for the {self.active_network.net_name} network.")

    def list_reserve_tokens(self) -> list:
        """Returns all Aave ReserveToken class objects stored on the active network"""
        return self.active_network.aave_tokens

    def get_paraswap_prices(self, src_token, dest_token, src_amount, src_decimals, dest_decimals, network='42161'):
        """Call ParaSwap API to get price data."""
        url = "https://apiv5.paraswap.io/prices"
        params = {
            "srcToken": src_token,
            "destToken": dest_token,
            "srcDecimals": src_decimals,
            "destDecimals": dest_decimals,
            "amount": src_amount,
            "side": "SELL",
            "network": network,
            "includeDEXS": "true",
            "excludeContractMethods": "simpleSwap",
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"ParaSwap prices API call failed: {response.text}")

        return response.json()

    def get_paraswap_transaction(self, prices_data, user_address):
        """Call ParaSwap API to get transaction data."""
        url = f"https://apiv5.paraswap.io/transactions/{prices_data['priceRoute']['network']}"
        body = {
            "priceRoute": prices_data['priceRoute'],
            "srcToken": prices_data['priceRoute']['srcToken'],
            "destToken": prices_data['priceRoute']['destToken'],
            "srcAmount": prices_data['priceRoute']['srcAmount'],
            "destAmount": prices_data['priceRoute']['destAmount'],
            "userAddress": user_address,
            "partnerAddress": user_address,
        }
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=body, headers=headers)
        if response.status_code != 200:
            raise Exception(f"ParaSwap transactions API call failed: {response.text}")

        return response.json()

    def swap(self, swap_from_token: ReserveToken, swap_to_token: ReserveToken, amount_to_swap: float):
        """
        Execute the swap operation using ParaSwap API and send transaction via web3.
        
        Parameters:
            swap_from_token: The ReserveToken object representing the token to swap from.
            swap_to_token: The ReserveToken object representing the token to swap to.
            amount_to_swap: The amount of tokens to swap.
            min_amount_to_receive: The minimum amount to receive from the swap.
        """
        try:
            # Convert amounts to decimal units
            amount_in_decimal_units = self.convert_to_decimal_units(swap_from_token, amount_to_swap)
            
            # Approve token transfer for ParaSwap proxy only if necessary
            erc20_address = Web3.to_checksum_address(swap_from_token.address)
            spender_address = Web3.to_checksum_address(self.active_network.token_transfer_proxy)
            #current_allowance = self.get_allowance(erc20_address, spender_address)
            
            #if current_allowance < amount_in_decimal_units:
            approval_hash, approval_gas = self.approve_erc20(
                erc20_address=erc20_address,
                spender_address=spender_address,
                amount_in_decimal_units=amount_in_decimal_units
            )

            # Fetch price data and transaction data concurrently
            #with ThreadPoolExecutor() as executor:
            prices_data = self.get_paraswap_prices(swap_from_token.address, swap_to_token.address, amount_in_decimal_units, swap_from_token.decimals, swap_to_token.decimals)
                #if current_allowance < amount_in_decimal_units:
            transaction_data = self.get_paraswap_transaction(prices_data, self.wallet_address)
                #else:
                    #transaction_data = executor.submit(fetch_transaction, prices_data).result()

            # Build and send the transaction
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            transaction = {
                'from': transaction_data['from'],
                'to': transaction_data['to'],
                'value': int(transaction_data['value']),
                'data': transaction_data['data'],
                'gasPrice': int(transaction_data['gasPrice']),
                'gas': int(transaction_data['gas']),
                'chainId': int(transaction_data['chainId']),
                'nonce': nonce
            }

            # Sign the transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key=self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            receipt = self.process_transaction_receipt(tx_hash, amount_to_swap, swap_from_token, operation="Swap", approval_gas_cost=approval_gas)
            
            return receipt

        except Exception as exc:
            raise Exception(f"Could not execute swap - Error: {exc}")

    def get_allowance(self, erc20_address: str, spender_address: str) -> int:
        """
        Get the current allowance for a given ERC20 token and spender.
        
        Parameters:
            erc20_address: The address of the ERC20 token.
            spender_address: The address of the spender.
        
        Returns:
            The current allowance as an integer.
        """
        erc20 = self.w3.eth.contract(address=erc20_address, abi=ABIReference.erc20_abi)
        return erc20.functions.allowance(self.wallet_address, spender_address).call()


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
    def __init__(self, polygon_rpc_url: str, aave_client):
        self.net_name = "Polygon"
        self.chain_id = 137
        self.pool_addresses_provider = '0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb'
        self.pool_data_provider = '0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654'
        self.wallet_balance_provider = ''
        self.liquidity_swap_adapter = ''
        self.collateral_repay_adapter = ''
        self.augustus_swapper = '0xDEF171Fe48CF0115B1d80b88dc8eAB59176FEe57'
        self.WMATIC = '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619'
        self.USDC = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        self.USDT = '0xc2132D05D31c914a87C6611C10748AEb04B58e8F'
        self.DAI = '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063'
        self.rpc_url = polygon_rpc_url
        self.aave_client = aave_client
        self.aave_tokens = self.fetch_aave_tokens()

    def fetch_aave_tokens(self) -> list:
        try:
            tokens = []
            lending_pool = self.aave_client.get_lending_pool()
            token_symbols = {
                self.WMATIC: "WMATIC",
                self.USDC: "USDC",
                self.USDT: "USDT",
                self.DAI: "DAI"
            }

            for token_address in [self.WMATIC, self.USDC, self.USDT, self.DAI]:
                pool_data = self.aave_client.get_pool_data(lending_pool, "getReserveData", token_address)
                decimals = self.aave_client.get_protocol_data("getReserveConfigurationData", token_address)[0]
                
                token_data = {
                    "aTokenAddress": pool_data["aTokenAddress"],
                    "aTokenSymbol": None,  # This data might not be directly available
                    "stableDebtTokenAddress": pool_data["stableDebtTokenAddress"],
                    "variableDebtTokenAddress": pool_data["variableDebtTokenAddress"],
                    "symbol": token_symbols[token_address],  # Correctly use the symbol from the mapping
                    "address": token_address,
                    "decimals": decimals
                }
                
                tokens.append(ReserveToken(**token_data))
                
            return tokens
        
        except Exception as e:
            raise ConnectionError(f"Could not fetch Aave tokenlist for the Polygon network - Error: {e}")

class ArbitrumConfig:
    def __init__(self, arbitrum_rpc_url: str, aave_client):
        self.net_name = "Arbitrum"
        self.chain_id = 42161
        self.pool_addresses_provider = '0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb'
        self.pool_data_provider = '0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654'
        self.wallet_balance_provider = '0xBc790382B3686abffE4be14A030A96aC6154023a'
        self.liquidity_swap_adapter = '0xF3C3F14dd7BDb7E03e6EBc3bc5Ffc6D66De12251'
        self.collateral_repay_adapter = '0x28201C152DC5B69A86FA54FCfd21bcA4C0eff3BA'
        self.augustus_swapper = '0xDEF171Fe48CF0115B1d80b88dc8eAB59176FEe57'
        self.token_transfer_proxy = '0x216b4b4ba9f3e719726886d34a177484278bfcae'
        self.WETH = '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1'
        self.USDC = '0xaf88d065e77c8cC2239327C5EDb3A432268e5831' 
        self.USDCE = '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8' 
        self.USDT = '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9'
        self.DAI = '0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1'        
        self.rpc_url = arbitrum_rpc_url
        self.aave_client = aave_client
        self.aave_tokens = []

    def fetch_aave_tokens(self) -> list:
        try:
            tokens = []
            lending_pool = self.aave_client.get_lending_pool()
            token_symbols = {
                self.WETH: "WETH",
                self.USDC: "USDC",
                self.USDCE: "USDCE",
                self.USDT: "USDT",
                self.DAI: "DAI"
            }

            for token_address in [self.WETH, self.USDC, self.USDCE, self.USDT, self.DAI]:
                pool_data = self.aave_client.get_pool_data(lending_pool, "getReserveData", token_address)
                decimals = self.aave_client.get_protocol_data("getReserveConfigurationData", token_address)[0]
                
                token_data = {
                    "aTokenAddress": pool_data["aTokenAddress"],
                    "aTokenSymbol": None,  # This data might not be directly available
                    "stableDebtTokenAddress": pool_data["stableDebtTokenAddress"],
                    "variableDebtTokenAddress": pool_data["variableDebtTokenAddress"],
                    "symbol": token_symbols[token_address],  # Correctly use the symbol from the mapping
                    "address": token_address,
                    "decimals": decimals
                }
                
                tokens.append(ReserveToken(**token_data))
                
            return tokens
        
        except Exception as e:
            raise ConnectionError(f"Could not fetch Aave tokenlist for the Polygon network - Error: {e}")


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

    liquidity_swap_adapter_abi = [{"inputs":[{"internalType":"contract IPoolAddressesProvider","name":"addressesProvider","type":"address"},{"internalType":"contract IParaSwapAugustusRegistry","name":"augustusRegistry","type":"address"},{"internalType":"address","name":"owner","type":"address"}],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"fromAsset","type":"address"},{"indexed":True,"internalType":"address","name":"toAsset","type":"address"},{"indexed":False,"internalType":"uint256","name":"amountSold","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"receivedAmount","type":"uint256"}],"name":"Bought","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"previousOwner","type":"address"},{"indexed":True,"internalType":"address","name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"fromAsset","type":"address"},{"indexed":True,"internalType":"address","name":"toAsset","type":"address"},{"indexed":False,"internalType":"uint256","name":"fromAmount","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"receivedAmount","type":"uint256"}],"name":"Swapped","type":"event"},{"inputs":[],"name":"ADDRESSES_PROVIDER","outputs":[{"internalType":"contract IPoolAddressesProvider","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"AUGUSTUS_REGISTRY","outputs":[{"internalType":"contract IParaSwapAugustusRegistry","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"MAX_SLIPPAGE_PERCENT","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"ORACLE","outputs":[{"internalType":"contract IPriceOracleGetter","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"POOL","outputs":[{"internalType":"contract IPool","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"premium","type":"uint256"},{"internalType":"address","name":"initiator","type":"address"},{"internalType":"bytes","name":"params","type":"bytes"}],"name":"executeOperation","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"renounceOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"contract IERC20","name":"token","type":"address"}],"name":"rescueTokens","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"contract IERC20Detailed","name":"assetToSwapFrom","type":"address"},{"internalType":"contract IERC20Detailed","name":"assetToSwapTo","type":"address"},{"internalType":"uint256","name":"amountToSwap","type":"uint256"},{"internalType":"uint256","name":"minAmountToReceive","type":"uint256"},{"internalType":"uint256","name":"swapAllBalanceOffset","type":"uint256"},{"internalType":"bytes","name":"swapCalldata","type":"bytes"},{"internalType":"contract IParaSwapAugustus","name":"augustus","type":"address"},{"components":[{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"internalType":"struct BaseParaSwapAdapter.PermitSignature","name":"permitParams","type":"tuple"}],"name":"swapAndDeposit","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"}]

    collateral_repay_adapter_abi = [{"inputs":[{"internalType":"contract IPoolAddressesProvider","name":"addressesProvider","type":"address"},{"internalType":"contract IParaSwapAugustusRegistry","name":"augustusRegistry","type":"address"},{"internalType":"address","name":"owner","type":"address"}],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"fromAsset","type":"address"},{"indexed":True,"internalType":"address","name":"toAsset","type":"address"},{"indexed":False,"internalType":"uint256","name":"amountSold","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"receivedAmount","type":"uint256"}],"name":"Bought","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"previousOwner","type":"address"},{"indexed":True,"internalType":"address","name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"fromAsset","type":"address"},{"indexed":True,"internalType":"address","name":"toAsset","type":"address"},{"indexed":False,"internalType":"uint256","name":"fromAmount","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"receivedAmount","type":"uint256"}],"name":"Swapped","type":"event"},{"inputs":[],"name":"ADDRESSES_PROVIDER","outputs":[{"internalType":"contract IPoolAddressesProvider","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"AUGUSTUS_REGISTRY","outputs":[{"internalType":"contract IParaSwapAugustusRegistry","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"MAX_SLIPPAGE_PERCENT","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"ORACLE","outputs":[{"internalType":"contract IPriceOracleGetter","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"POOL","outputs":[{"internalType":"contract IPool","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"premium","type":"uint256"},{"internalType":"address","name":"initiator","type":"address"},{"internalType":"bytes","name":"params","type":"bytes"}],"name":"executeOperation","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"renounceOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"contract IERC20","name":"token","type":"address"}],"name":"rescueTokens","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"contract IERC20Detailed","name":"collateralAsset","type":"address"},{"internalType":"contract IERC20Detailed","name":"debtAsset","type":"address"},{"internalType":"uint256","name":"collateralAmount","type":"uint256"},{"internalType":"uint256","name":"debtRepayAmount","type":"uint256"},{"internalType":"uint256","name":"debtRateMode","type":"uint256"},{"internalType":"uint256","name":"buyAllBalanceOffset","type":"uint256"},{"internalType":"bytes","name":"paraswapData","type":"bytes"},{"components":[{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"internalType":"struct BaseParaSwapAdapter.PermitSignature","name":"permitSignature","type":"tuple"}],"name":"swapAndRepay","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"}]

    token_transfer_proxy_abi = [{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"previousOwner","type":"address"},{"indexed":True,"internalType":"address","name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"renounceOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"}]

    wallet_balance_provide_abi = [{"inputs":[{"internalType":"address","name":"user","type":"address"},{"internalType":"address","name":"token","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address[]","name":"users","type":"address[]"},{"internalType":"address[]","name":"tokens","type":"address[]"}],"name":"batchBalanceOf","outputs":[{"internalType":"uint256[]","name":"","type":"uint256[]"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"provider","type":"address"},{"internalType":"address","name":"user","type":"address"}],"name":"getUserWalletBalances","outputs":[{"internalType":"address[]","name":"","type":"address[]"},{"internalType":"uint256[]","name":"","type":"uint256[]"}],"stateMutability":"view","type":"function"},{"stateMutability":"payable","type":"receive"}]