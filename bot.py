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
# Contract Address (World Computer Netizens)
CONTRACT_ADDRESS = "0x3fd43a658915a7ce5ae0a2e48f72b9fce7ba0c44"

# Standard Transfer Event Signature
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# --- GENTLE SCANNING SETTINGS ---
# Drastically reduced range to ensure success
TOTAL_BLOCKS_TO_SCAN = 5000 
CHUNK_SIZE = 500 # Slightly larger chunk, but we go slower

w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

def get_smart_floor():
    print(f"DEBUG: Connecting to Blockchain...")
    
    if not w3.is_connected():
        print("CRITICAL: Could not connect to RPC.")
        return None

    try:
        valid_address = Web3.to_checksum_address(CONTRACT_ADDRESS)
        latest_block = w3.eth.block_number
        start_block = latest_block - TOTAL_BLOCKS_TO_SCAN
        print(f"DEBUG: Scanning {TOTAL_BLOCKS_TO_SCAN} blocks ({start_block} to {latest_block})...")

        all_logs = []
        
        # --- ROBUST CHUNKING LOOP ---
        current_from = start_block
        while current_from < latest_block:
            current_to = min(current_from + CHUNK_SIZE, latest_block)
            
            # RETRY LOGIC
            success = False
            for attempt in range(2): # Try twice
                try:
                    logs = w3.eth.get_logs({
                        'fromBlock': current_from,
                        'toBlock': current_to,
                        'address': valid_address,
                        'topics': [TRANSFER_TOPIC]
                    })
                    if logs:
                        all_logs.extend(logs)
                    success = True
                    break # Success, exit retry loop
                except Exception as e:
                    print(f"WARN: Chunk {current_from}-{current_to} failed (Attempt {attempt+1}): {e}")
                    time.sleep(2) # Wait 2 seconds before retrying
            
            if not success:
                print(f"ERROR: Skipped chunk {current_from}-{current_to} after retries.")

            # Polite Sleep between chunks
            time.sleep(0.5) 
            current_from = current_to + 1
            
        print(f"DEBUG: Total raw transfers found: {len(all_logs)}")
        
        if not all_logs:
            return None

        # --- ANALYZE LOGS ---
        raw_sales = []
        
        # Check last 30 logs (Deep enough for a floor estimate)
        logs_to_check = all_logs[-30:]
        
        print(f"DEBUG: Checking {len(logs_to_check)} candidates for ETH value...")
        
        for log in logs_to_check:
            try:
                tx = w3.eth.get_transaction(log['transactionHash'])
                value_eth = float(w3.from_wei(tx['value'], 'ether'))
                
                # Filter: Ignore junk (< 0.0001)
                if value_eth > 0.0001: 
                    raw_sales.append(value_eth)
                # Sleep a tiny bit between transaction lookups too
                time.sleep(0.1) 
            except:
                continue

        if not raw_sales:
            print("DEBUG: Found transfers, but all were 0 ETH.")
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
price_result = None 

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

if __name__ == "__main__":
    price_result = get_smart_floor()
    if price_result:
        client.run(DISCORD_TOKEN)
    else:
        print("Done. No sales found, skipping Discord login.")
