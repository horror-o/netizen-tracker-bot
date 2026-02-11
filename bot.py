import discord
import os
import asyncio
from datetime import datetime
from web3 import Web3
from statistics import mean

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
ALCHEMY_API_KEY = os.getenv('ALCHEMY_API_KEY')

# MegaETH RPC URL
ALCHEMY_URL = f"https://megaeth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"

# Contract Address (Ensure checksum format)
CONTRACT_ADDRESS = "0x3fd43a658915a7ce5ae0a2e48f72b9fce7ba0c44" # <--- PASTE YOUR 0x ADDRESS HERE
try:
    CONTRACT_ADDRESS = Web3.to_checksum_address(CONTRACT_ADDRESS)
except:
    print("CRITICAL: Invalid Contract Address format")

# Standard Transfer Event Signature
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# Connect to Blockchain
w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

def get_smart_floor():
    print(f"DEBUG: Connecting to Blockchain via Alchemy...")
    
    if not w3.is_connected():
        print("CRITICAL: Could not connect to RPC.")
        return None

    try:
        latest_block = w3.eth.block_number
        # MegaETH is fast. 5000 blocks is roughly 1-2 hours.
        from_block = latest_block - 5000 
        
        print(f"DEBUG: Scanning blocks {from_block} to {latest_block}")

        logs = w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': latest_block,
            'address': CONTRACT_ADDRESS,
            'topics': [TRANSFER_TOPIC]
        })
        
        print(f"DEBUG: Found {len(logs)} transfers. Analyzing values...")
        
        raw_sales = []
        
        # Limit to checking the last 50 logs to save API credits/time
        recent_logs = logs[-50:] 
        
        for log in recent_logs:
            tx_hash = log['transactionHash']
            try:
                tx = w3.eth.get_transaction(tx_hash)
                value_eth = float(w3.from_wei(tx['value'], 'ether'))
                
                # Filter 1: Ignore junk (< 0.0001)
                if value_eth > 0.0001: 
                    raw_sales.append(value_eth)
            except Exception as e:
                print(f"Warn: Could not fetch tx {tx_hash.hex()}: {e}")

        if not raw_sales:
            print("DEBUG: No ETH sales found in scan range.")
            return None

        # --- SMART LOGIC START ---
        
        # 1. Sort low to high
        raw_sales.sort()
        print(f"DEBUG: Raw Sales Found: {raw_sales}")
        
        # 2. The "30% Gap" Filter (Iterative)
        # We loop and check if the first item is an outlier compared to the second
        cleaned_sales = raw_sales.copy()
        
        while len(cleaned_sales) > 1:
            lowest = cleaned_sales[0]
            second_lowest = cleaned_sales[1]
            
            # If lowest is < 70% of the second lowest (30% gap)
            if lowest < (second_lowest * 0.70):
                print(f"DEBUG: Removed Outlier {lowest} (Gap too big vs {second_lowest})")
                cleaned_sales.pop(0) # Remove the outlier
            else:
                break # Gap is normal, stop filtering
        
        # 3. Take Average of Bottom 3
        # If we have less than 3 sales, take average of what we have
        final_sales_pool = cleaned_sales[:3]
        floor_estimate = mean(final_sales_pool)
        
        print(f"DEBUG: Final Pool: {final_sales_pool} -> Avg: {floor_estimate}")
        
        return floor_estimate

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return None

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    
    price = get_smart_floor()
    
    if price:
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="💎 Floor Price Estimate (On-Chain)", color=0xFFAA00)
            embed.add_field(name="Collection", value="World Computer Netizens", inline=True)
            embed.add_field(name="Est. Floor Price", value=f"**{price:.4f} ETH**", inline=True)
            embed.set_footer(text=f"Avg of lowest 3 recent sales (outliers removed)")
            
            await channel.send(embed=embed)
            print(f"SUCCESS: Posted price: {price}")
        else:
            print(f"ERROR: Channel {CHANNEL_ID} not found.")
    else:
        print("ERROR: No valid sales found.")
    
    await client.close()

client.run(DISCORD_TOKEN)
