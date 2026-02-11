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

# Contract Address
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
        
        # WE WANT 2 HOURS OF DATA (~72,000 Blocks on MegaETH)
        # But Alchemy limits us to ~2,000 blocks per request.
        TOTAL_BLOCKS_TO_SCAN = 70000 
        CHUNK_SIZE = 2000
        
        start_block = latest_block - TOTAL_BLOCKS_TO_SCAN
        print(f"DEBUG: Plan: Scan from {start_block} to {latest_block} in chunks of {CHUNK_SIZE}")

        all_logs = []
        
        # --- THE CHUNKING LOOP ---
        current_from = start_block
        while current_from < latest_block:
            current_to = min(current_from + CHUNK_SIZE, latest_block)
            
            try:
                # Ask for just a small slice
                logs = w3.eth.get_logs({
                    'fromBlock': current_from,
                    'toBlock': current_to,
                    'address': CONTRACT_ADDRESS,
                    'topics': [TRANSFER_TOPIC]
                })
                all_logs.extend(logs)
                # print(f"DEBUG: Scanned {current_from}-{current_to} -> Found {len(logs)} logs")
            except Exception as e:
                print(f"WARN: Failed chunk {current_from}-{current_to}: {e}")
            
            current_from = current_to + 1
            
        print(f"DEBUG: Total transfers found: {len(all_logs)}")
        
        if not all_logs:
            print("DEBUG: No transfers found in the last 2 hours.")
            return None

        # --- ANALYZE THE LOGS ---
        raw_sales = []
        
        # Only check the last 50 transfers to save time, 
        # but now we are choosing from a much larger pool of history.
        for log in all_logs[-50:]: 
            tx_hash = log['transactionHash']
            try:
                tx = w3.eth.get_transaction(tx_hash)
                value_eth = float(w3.from_wei(tx['value'], 'ether'))
                
                # Filter: Ignore junk (< 0.0001)
                if value_eth > 0.0001: 
                    raw_sales.append(value_eth)
            except Exception as e:
                pass

        if not raw_sales:
            print("DEBUG: Transfers found, but no ETH value attached (likely WETH sales).")
            return None

        # --- SMART MATH LOGIC ---
        raw_sales.sort()
        print(f"DEBUG: Valid Sales: {raw_sales}")
        
        cleaned_sales = raw_sales.copy()
        
        # 30% Gap Filter
        while len(cleaned_sales) > 1:
            lowest = cleaned_sales[0]
            second_lowest = cleaned_sales[1]
            if lowest < (second_lowest * 0.70):
                cleaned_sales.pop(0) 
            else:
                break 
        
        # Average of Bottom 3
        final_sales_pool = cleaned_sales[:3]
        floor_estimate = mean(final_sales_pool)
        
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
            embed = discord.Embed(title="💎 Floor Price Estimate", color=0xFFAA00)
            embed.add_field(name="Collection", value="World Computer Netizens", inline=True)
            embed.add_field(name="Est. Floor Price", value=f"**{price:.4f} ETH**", inline=True)
            embed.set_footer(text=f"Based on on-chain sales (last ~2 hours)")
            await channel.send(embed=embed)
            print(f"SUCCESS: Posted price: {price}")
    else:
        print("ERROR: No valid sales found.")
    await client.close()

client.run(DISCORD_TOKEN)
