import discord
import os
import time
import asyncio
from web3 import Web3
from statistics import mean

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
ALCHEMY_API_KEY = os.getenv('ALCHEMY_API_KEY')

# MegaETH RPC URL
ALCHEMY_URL = f"https://megaeth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
# Contract Address
CONTRACT_ADDRESS = "0x3fd43a658915a7ce5ae0a2e48f72b9fce7ba0c44" # <--- PASTE YOUR 0x ADDRESS HERE (Make sure it's the right one!)

# Standard Transfer Event Signature
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# --- SCANNING SETTINGS ---
# MegaETH blocks are fast. 20,000 blocks is approx 30-45 minutes of history.
TOTAL_BLOCKS_TO_SCAN = 20000 
CHUNK_SIZE = 250  # drastic reduction to fix 400 errors

w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

def get_smart_floor():
    print(f"DEBUG: Connecting to Blockchain...")
    
    if not w3.is_connected():
        print("CRITICAL: Could not connect to RPC.")
        return None

    try:
        # Check address validity
        valid_address = Web3.to_checksum_address(CONTRACT_ADDRESS)
        
        latest_block = w3.eth.block_number
        start_block = latest_block - TOTAL_BLOCKS_TO_SCAN
        print(f"DEBUG: Scanning {TOTAL_BLOCKS_TO_SCAN} blocks ({start_block} to {latest_block})...")

        all_logs = []
        
        # --- SAFE CHUNKING LOOP ---
        current_from = start_block
        while current_from < latest_block:
            current_to = min(current_from + CHUNK_SIZE, latest_block)
            
            try:
                logs = w3.eth.get_logs({
                    'fromBlock': current_from,
                    'toBlock': current_to,
                    'address': valid_address,
                    'topics': [TRANSFER_TOPIC]
                })
                if logs:
                    all_logs.extend(logs)
                    print(f"DEBUG: Found {len(logs)} txs in blocks {current_from}-{current_to}")
            except Exception as e:
                # If 250 fails, we just skip that chunk and keep going
                print(f"WARN: Chunk failed {current_from}-{current_to} (Likely RPC limit)")
            
            # Tiny sleep to be polite to the API
            time.sleep(0.05)
            current_from = current_to + 1
            
        print(f"DEBUG: Total raw transfers found: {len(all_logs)}")
        
        if not all_logs:
            return None

        # --- ANALYZE LOGS ---
        raw_sales = []
        
        for log in all_logs:
            try:
                # We need the transaction value.
                # Optimization: get_transaction is expensive. 
                # We only check if we have < 50 logs. If we have 1000s, this will be slow.
                if len(all_logs) > 100:
                    # If tons of logs, skip checking all of them, just check the last 50
                    if log not in all_logs[-50:]: continue

                tx = w3.eth.get_transaction(log['transactionHash'])
                value_eth = float(w3.from_wei(tx['value'], 'ether'))
                
                if value_eth > 0.001: 
                    raw_sales.append(value_eth)
            except:
                continue

        if not raw_sales:
            print("DEBUG: Found transfers, but all were 0 ETH (likely Mints or WETH sales).")
            return None

        # --- SMART MATH ---
        raw_sales.sort()
        print(f"DEBUG: Valid Sales: {raw_sales}")
        
        cleaned_sales = raw_sales.copy()
        
        # 30% Gap Filter
        while len(cleaned_sales) > 1:
            lowest = cleaned_sales[0]
            second = cleaned_sales[1]
            if lowest < (second * 0.70):
                cleaned_sales.pop(0) 
            else:
                break 
        
        # Average of Bottom 3
        final_pool = cleaned_sales[:3]
        return mean(final_pool)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return None

# --- DISCORD BOT ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)
price_result = None # Global variable to store the result

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    
    if price_result:
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="💎 Floor Price Estimate", color=0xFFAA00)
            embed.add_field(name="Collection", value="World Computer Netizens", inline=True)
            embed.add_field(name="Est. Floor Price", value=f"**{price_result:.4f} ETH**", inline=True)
            embed.set_footer(text="Based on recent on-chain sales")
            await channel.send(embed=embed)
            print("SUCCESS: Posted to Discord.")
    else:
        print("ERROR: No price to post.")
    
    await client.close()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # 1. Run the heavy scan FIRST (No Discord connection yet)
    price_result = get_smart_floor()
    
    # 2. Only run Discord if we found something
    if price_result:
        client.run(DISCORD_TOKEN)
    else:
        print("Done. No sales found, skipping Discord login.")
