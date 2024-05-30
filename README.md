# Aave Functions for Web3.py

# Overview:

A Python repo for the main functions on the Aave protocol using web3.py. Latest changes include:
- Migration to Aave v3 from Aave v2
- Added Polygon, Arbitrum, and Mumbai networks
- Added dynamic functions to easily change the amount, asset, and network

## Setup

You'll need python installed.

pip install -r requirements.txt
a
## Config
You'll need the following environment variables. You can set them all in your .env file (as strings):

WALLET_ADDRESS: Your Wallet Address

PRIVATE_WALLET_KEY: Your Private Key from your Wallet # Remember to start it with "0x"

KOVAN_RPC_URL: Your Kovan connection to the blockchain. You can get a URL from a service like Infura or ]Alchemy. An example would be https://kovan.infura.io/v3/fffffffffffffffffffff

MUMBAI_RPC_URL: Your Mumbai connection to the blockchain. You can get a URL from a service like Infura or ]Alchemy. An example would be https://polygon-mumbai.infura.io/v3/fffffffffffffffffffff

MAINNET_RPC_URL: Same as above, but for mainnet.

POLYGON_RPC_URL: Same as above, but for Polygon.

ARBITRUM_RPC_URL: Same as above, but for Arbitrum.


# Use case: Stablecoins leveraged loop strategy

Deposit stablecoins in the highest-paying market and use it as collateral to borrow the cheapest stablecoin market. Do it until additional borrowing becomes negligible, with a 90% LTV thanks to e-mode.

## Definitions:
- **LTV (Loan-to-Value):** The ratio of the loan amount to the value of the collateral. In this case, LTV is 90%, meaning you can borrow up to 90% of your collateral value.
- **Loop:** Each loop involves borrowing a portion of the collateral value, then using that borrowed amount as additional collateral.

## Steps to Calculate the Number of Loops and Resulting Leverage:

1. **Initial Supply:** Start with an initial amount of collateral.
2. **Borrow:** Borrow 90% of the value of the collateral.
3. **Supply:** Use the borrowed amount as additional collateral.
4. **Repeat:** Continue the process until the borrowed amount is too small to be practically used as collateral.

## Formula for Each Loop:
- **Initial Collateral:** \( C_0 \)
- **Collateral After n Loops:** \( C_n \)
- **Borrowed Amount After n Loops:** \( B_n \)

### First Loop:
- Supply: \( C_0 \)
- Borrow: \( B_1 = 0.9 \times C_0 \)
- New Collateral: \( C_1 = C_0 + B_1 \)

### Second Loop:
- Supply: \( C_1 \)
- Borrow: \( B_2 = 0.9 \times B_1 \)
- New Collateral: \( C_2 = C_1 + B_2 \)

### General Formula:
- \( B_{n+1} = 0.9 \times B_n \)
- \( C_{n+1} = C_n + B_{n+1} \)

This creates a geometric series where the borrowed amounts decrease by 90% each loop.

## Summing the Geometric Series:
The total borrowed amount after infinite loops is the sum of a geometric series:
\[ B_{\text{total}} = B_1 + B_2 + B_3 + \ldots = B_1 \times \left(\frac{1}{1 - 0.9}\right) = 0.9 \times C_0 \times 10 = 9 \times C_0 \]

## Total Collateral After Infinite Loops:
\[ C_{\text{total}} = C_0 + B_1 + B_2 + B_3 + \ldots \]
\[ C_{\text{total}} = C_0 + (0.9 \times C_0) + (0.9^2 \times C_0) + \ldots \]
\[ C_{\text{total}} = C_0 \times \left(1 + 0.9 + 0.9^2 + \ldots\right) \]
\[ C_{\text{total}} = C_0 \times \left(\frac{1}{1 - 0.9}\right) \]
\[ C_{\text{total}} = 10 \times C_0 \]

## Leverage:
The leverage is defined as the total exposure (total collateral) divided by the initial supply:
\[ \text{Leverage} = \frac{C_{\text{total}}}{C_0} = \frac{10 \times C_0}{C_0} = 10 \]

## Number of Effective Loops:
To estimate the number of loops, we can find when the borrowed amount becomes negligible:
\[ B_n = 0.9^n \times C_0 \]
When \( 0.9^n \) becomes very small, the loops are effectively done. Practically, this is when \( 0.9^n \) is less than a small threshold (e.g., \(10^{-6}\)).

Let's calculate the number of loops \( n \) for this threshold:
\[ 0.9^n < 10^{-6} \]
Taking the natural logarithm of both sides:
\[ n \ln(0.9) < \ln(10^{-6}) \]
\[ n > \frac{\ln(10^{-6})}{\ln(0.9)} \]
\[ n > \frac{-13.8155}{-0.1054} \]
\[ n > 131.07 \]

So, it will take approximately 131 loops for the borrowed amount to become negligible.

## Conclusion:
- **Number of Loops:** Approximately 131
- **Resulting Leverage:** 10

By using the supplied assets as collateral and borrowing at 90% LTV, you can achieve a leverage of 10 after about 131 loops. This means you can increase your exposure tenfold by repeating the supply-borrow loop with a 90% LTV.


## Thanks

(MANY THANKS TO PathX-Projects for a lot of the underlying structure for this code !!!)
