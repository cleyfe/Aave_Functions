AAVE_ERRORS = {
    "CALLER_NOT_POOL_ADMIN": {"Code": '1', "Description": "The caller of the function is not a pool admin"},
    "CALLER_NOT_EMERGENCY_ADMIN": {"Code": '2', "Description": "The caller of the function is not an emergency admin"},
    "CALLER_NOT_POOL_OR_EMERGENCY_ADMIN": {"Code": '3', "Description": "The caller of the function is not a pool or emergency admin"},
    "CALLER_NOT_RISK_OR_POOL_ADMIN": {"Code": '4', "Description": "The caller of the function is not a risk or pool admin"},
    "CALLER_NOT_ASSET_LISTING_OR_POOL_ADMIN": {"Code": '5', "Description": "The caller of the function is not an asset listing or pool admin"},
    "CALLER_NOT_BRIDGE": {"Code": '6', "Description": "The caller of the function is not a bridge"},
    "ADDRESSES_PROVIDER_NOT_REGISTERED": {"Code": '7', "Description": "Pool addresses provider is not registered"},
    "INVALID_ADDRESSES_PROVIDER_ID": {"Code": '8', "Description": "Invalid id for the pool addresses provider"},
    "NOT_CONTRACT": {"Code": '9', "Description": "Address is not a contract"},
    "CALLER_NOT_POOL_CONFIGURATOR": {"Code": '10', "Description": "The caller of the function is not the pool configurator"},
    "CALLER_NOT_ATOKEN": {"Code": '11', "Description": "The caller of the function is not an AToken"},
    "INVALID_ADDRESSES_PROVIDER": {"Code": '12', "Description": "The address of the pool addresses provider is invalid"},
    "INVALID_FLASHLOAN_EXECUTOR_RETURN": {"Code": '13', "Description": "Invalid return value of the flashloan executor function"},
    "RESERVE_ALREADY_ADDED": {"Code": '14', "Description": "Reserve has already been added to reserve list"},
    "NO_MORE_RESERVES_ALLOWED": {"Code": '15', "Description": "Maximum amount of reserves in the pool reached"},
    "EMODE_CATEGORY_RESERVED": {"Code": '16', "Description": "Zero eMode category is reserved for volatile heterogeneous assets"},
    "INVALID_EMODE_CATEGORY_ASSIGNMENT": {"Code": '17', "Description": "Invalid eMode category assignment to asset"},
    "RESERVE_LIQUIDITY_NOT_ZERO": {"Code": '18', "Description": "The liquidity of the reserve needs to be 0"},
    "FLASHLOAN_PREMIUM_INVALID": {"Code": '19', "Description": "Invalid flashloan premium"},
    "INVALID_RESERVE_PARAMS": {"Code": '20', "Description": "Invalid risk parameters for the reserve"},
    "INVALID_EMODE_CATEGORY_PARAMS": {"Code": '21', "Description": "Invalid risk parameters for the eMode category"},
    "BRIDGE_PROTOCOL_FEE_INVALID": {"Code": '22', "Description": "Invalid bridge protocol fee"},
    "CALLER_MUST_BE_POOL": {"Code": '23', "Description": "The caller of this function must be a pool"},
    "INVALID_MINT_AMOUNT": {"Code": '24', "Description": "Invalid amount to mint"},
    "INVALID_BURN_AMOUNT": {"Code": '25', "Description": "Invalid amount to burn"},
    "INVALID_AMOUNT": {"Code": '26', "Description": "Amount must be greater than 0"},
    "RESERVE_INACTIVE": {"Code": '27', "Description": "Action requires an active reserve"},
    "RESERVE_FROZEN": {"Code": '28', "Description": "Action cannot be performed because the reserve is frozen"},
    "RESERVE_PAUSED": {"Code": '29', "Description": "Action cannot be performed because the reserve is paused"},
    "BORROWING_NOT_ENABLED": {"Code": '30', "Description": "Borrowing is not enabled"},
    "STABLE_BORROWING_NOT_ENABLED": {"Code": '31', "Description": "Stable borrowing is not enabled"},
    "NOT_ENOUGH_AVAILABLE_USER_BALANCE": {"Code": '32', "Description": "User cannot withdraw more than the available balance"},
    "INVALID_INTEREST_RATE_MODE_SELECTED": {"Code": '33', "Description": "Invalid interest rate mode selected"},
    "COLLATERAL_BALANCE_IS_ZERO": {"Code": '34', "Description": "The collateral balance is 0"},
    "HEALTH_FACTOR_LOWER_THAN_LIQUIDATION_THRESHOLD": {"Code": '35', "Description": "Health factor is lesser than the liquidation threshold"},
    "COLLATERAL_CANNOT_COVER_NEW_BORROW": {"Code": '36', "Description": "There is not enough collateral to cover a new borrow"},
    "COLLATERAL_SAME_AS_BORROWING_CURRENCY": {"Code": '37', "Description": "Collateral is (mostly) the same currency that is being borrowed"},
    "AMOUNT_BIGGER_THAN_MAX_LOAN_SIZE_STABLE": {"Code": '38', "Description": "The requested amount is greater than the max loan size in stable rate mode"},
    "NO_DEBT_OF_SELECTED_TYPE": {"Code": '39', "Description": "For repayment of a specific type of debt, the user needs to have debt that type"},
    "NO_EXPLICIT_AMOUNT_TO_REPAY_ON_BEHALF": {"Code": '40', "Description": "To repay on behalf of a user an explicit amount to repay is needed"},
    "NO_OUTSTANDING_STABLE_DEBT": {"Code": '41', "Description": "User does not have outstanding stable rate debt on this reserve"},
    "NO_OUTSTANDING_VARIABLE_DEBT": {"Code": '42', "Description": "User does not have outstanding variable rate debt on this reserve"},
    "UNDERLYING_BALANCE_ZERO": {"Code": '43', "Description": "The underlying balance needs to be greater than 0"},
    "INTEREST_RATE_REBALANCE_CONDITIONS_NOT_MET": {"Code": '44', "Description": "Interest rate rebalance conditions were not met"},
    "HEALTH_FACTOR_NOT_BELOW_THRESHOLD": {"Code": '45', "Description": "Health factor is not below the threshold"},
    "COLLATERAL_CANNOT_BE_LIQUIDATED": {"Code": '46', "Description": "The collateral chosen cannot be liquidated"},
    "SPECIFIED_CURRENCY_NOT_BORROWED_BY_USER": {"Code": '47', "Description": "User did not borrow the specified currency"},
    "INCONSISTENT_FLASHLOAN_PARAMS": {"Code": '49', "Description": "Inconsistent flashloan parameters"},
    "BORROW_CAP_EXCEEDED": {"Code": '50', "Description": "Borrow cap is exceeded"},
    "SUPPLY_CAP_EXCEEDED": {"Code": '51', "Description": "Supply cap is exceeded"},
    "UNBACKED_MINT_CAP_EXCEEDED": {"Code": '52', "Description": "Unbacked mint cap is exceeded"},
    "DEBT_CEILING_EXCEEDED": {"Code": '53', "Description": "Debt ceiling is exceeded"},
    "UNDERLYING_CLAIMABLE_RIGHTS_NOT_ZERO": {"Code": '54', "Description": "Claimable rights over underlying not zero (aToken supply or accruedToTreasury)"},
    "STABLE_DEBT_NOT_ZERO": {"Code": '55', "Description": "Stable debt supply is not zero"},
    "VARIABLE_DEBT_SUPPLY_NOT_ZERO": {"Code": '56', "Description": "Variable debt supply is not zero"},
    "LTV_VALIDATION_FAILED": {"Code": '57', "Description": "Ltv validation failed"},
    "INCONSISTENT_EMODE_CATEGORY": {"Code": '58', "Description": "Inconsistent eMode category"},
    "PRICE_ORACLE_SENTINEL_CHECK_FAILED": {"Code": '59', "Description": "Price oracle sentinel validation failed"},
    "ASSET_NOT_BORROWABLE_IN_ISOLATION": {"Code": '60', "Description": "Asset is not borrowable in isolation mode"},
    "RESERVE_ALREADY_INITIALIZED": {"Code": '61', "Description": "Reserve has already been initialized"},
    "USER_IN_ISOLATION_MODE_OR_LTV_ZERO": {"Code": '62', "Description": "User is in isolation mode or ltv is zero"},
    "INVALID_LTV": {"Code": '63', "Description": "Invalid ltv parameter for the reserve"},
    "INVALID_LIQ_THRESHOLD": {"Code": '64', "Description": "Invalid liquidity threshold parameter for the reserve"},
    "INVALID_LIQ_BONUS": {"Code": '65', "Description": "Invalid liquidity bonus parameter for the reserve"},
    "INVALID_DECIMALS": {"Code": '66', "Description": "Invalid decimals parameter of the underlying asset of the reserve"},
    "INVALID_RESERVE_FACTOR": {"Code": '67', "Description": "Invalid reserve factor parameter for the reserve"},
    "INVALID_BORROW_CAP": {"Code": '68', "Description": "Invalid borrow cap for the reserve"},
    "INVALID_SUPPLY_CAP": {"Code": '69', "Description": "Invalid supply cap for the reserve"},
    "INVALID_LIQUIDATION_PROTOCOL_FEE": {"Code": '70', "Description": "Invalid liquidation protocol fee for the reserve"},
    "INVALID_EMODE_CATEGORY": {"Code": '71', "Description": "Invalid eMode category for the reserve"},
    "INVALID_UNBACKED_MINT_CAP": {"Code": '72', "Description": "Invalid unbacked mint cap for the reserve"},
    "INVALID_DEBT_CEILING": {"Code": '73', "Description": "Invalid debt ceiling for the reserve"},
    "INVALID_RESERVE_INDEX": {"Code": '74', "Description": "Invalid reserve index"},
    "ACL_ADMIN_CANNOT_BE_ZERO": {"Code": '75', "Description": "ACL admin cannot be set to the zero address"},
    "INCONSISTENT_PARAMS_LENGTH": {"Code": '76', "Description": "Array parameters that should be equal length are not"},
    "ZERO_ADDRESS_NOT_VALID": {"Code": '77', "Description": "Zero address not valid"},
    "INVALID_EXPIRATION": {"Code": '78', "Description": "Invalid expiration"},
    "INVALID_SIGNATURE": {"Code": '79', "Description": "Invalid signature"},
    "OPERATION_NOT_SUPPORTED": {"Code": '80', "Description": "Operation not supported"},
    "DEBT_CEILING_NOT_ZERO": {"Code": '81', "Description": "Debt ceiling is not zero"},
    "ASSET_NOT_LISTED": {"Code": '82', "Description": "Asset is not listed"},
    "INVALID_OPTIMAL_USAGE_RATIO": {"Code": '83', "Description": "Invalid optimal usage ratio"},
    "INVALID_OPTIMAL_STABLE_TO_TOTAL_DEBT_RATIO": {"Code": '84', "Description": "Invalid optimal stable to total debt ratio"},
    "UNDERLYING_CANNOT_BE_RESCUED": {"Code": '85', "Description": "The underlying asset cannot be rescued"},
    "ADDRESSES_PROVIDER_ALREADY_ADDED": {"Code": '86', "Description": "Reserve has already been added to reserve list"},
    "POOL_ADDRESSES_DO_NOT_MATCH": {"Code": '87', "Description": "The token implementation pool address and the pool address provided by the initializing pool do not match"},
    "STABLE_BORROWING_ENABLED": {"Code": '88', "Description": "Stable borrowing is enabled"},
    "SILOED_BORROWING_VIOLATION": {"Code": '89', "Description": "User is trying to borrow multiple assets including a siloed one"},
    "RESERVE_DEBT_NOT_ZERO": {"Code": '90', "Description": "The total debt of the reserve needs to be 0"},
    "FLASHLOAN_DISABLED": {"Code": '91', "Description": "FlashLoaning for this asset is disabled"}
}

