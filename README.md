# Aave Functions for Web3.py

# Overview:

A Python repo for the main functions on the Aave protocol using web3.py. Forked from https://github.com/PathX-Projects/Aave-DeFi-Client.
- Added the Polygon Mumbai Testnet
- Added dynamic functions to easily change the amount, asset, and network

## Setup

You'll need python installed.

pip install -r requirements.txt

## Config
You'll need the following environment variables. You can set them all in your .env file (as strings):

MY_ADDRESS: Your Wallet Address

PRIVATE_KEY: Your Private Key from your Wallet # Remember to start it with "0x"

KOVAN_RPC_URL: Your Kovan connection to the blockchain. You can get a URL from a service like Infura or ]Alchemy. An example would be https://kovan.infura.io/v3/fffffffffffffffffffff

MUMBAI_RPC_URL: Your Mumbai connection to the blockchain. You can get a URL from a service like Infura or ]Alchemy. An example would be https://polygon-mumbai.infura.io/v3/fffffffffffffffffffff

MAINNET_RPC_URL: Same as above, but for mainnet.

## Thanks

(MANY THANKS TO PathX-Projects for a lot of the basis for this code !!!)
