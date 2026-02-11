import discord
import requests
import os
import asyncio
from datetime import datetime

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
ALCHEMY_API_KEY = os.getenv('ALCHEMY_API_KEY')

# The Contract Address for "World Computer Netizens"
CONTRACT_ADDRESS = "0x3fd43a658915a7ce5ae0a2e48f72b9fce7ba0c44" # <--- PASTE YOUR 0x ADDRESS HERE

# ALCHEMY NETWORK SETTING
# If Alchemy supports MegaETH, you must find the exact subdomain in your dashboard.
# Common formats: 'eth-mainnet', 'polygon-mainnet', 'arb-mainnet', 'opt-mainnet'
# For MegaETH, it might be 'megaeth-mainnet' or similar. Check your Alchemy App Dashboard.
ALCHEMY_NETWORK = "megaeth-mainnet" 

# Alchemy NFT V3 Endpoint
URL = f"https://{ALCHEMY_NETWORK}.g.alchemy.com/nft/v3/{ALCHEMY_API_KEY}/getFloorPrice"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def get_floor_price():
    params = {
        "contractAddress": CONTRACT_ADDRESS
    }
    headers = {
        "accept": "application/json"
    }
    
    print(f"DEBUG: asking Alchemy ({ALCHEMY_NETWORK})...")
    
    try:
        response = requests.get(URL, params=params, headers=headers)
        
        # DEBUG: Print response if it fails
        if response.status_code != 200:
            print(f"ERROR: Alchemy returned {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
        data = response.json()
        
        # Alchemy V3 Response Structure
        # It usually returns data for OpenSea and LooksRare. We prioritize OpenSea.
        opensea_data = data.get("openSea", {})
        floor = opensea_data.get("floorPrice")
        
        # Fallback if OpenSea is empty
        if not floor:
            looksrare_data = data.get("looksRare", {})
            floor = looksrare_data.get("floorPrice")
            
        return floor

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return None

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    
    price = await get_floor_price()
    
    if price:
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="💎 Floor Price Update", color=0x00FFFF)
            embed.add_field(name="Collection", value="World Computer Netizens", inline=True)
            embed.add_field(name="Floor Price", value=f"**{price} ETH**", inline=True)
            embed.set_footer(text=f"Updated: {datetime.now().strftime('%H:%M')} via Alchemy")
            
            await channel.send(embed=embed)
            print(f"SUCCESS: Posted price: {price}")
        else:
            print(f"ERROR: Channel {CHANNEL_ID} not found.")
    else:
        print("ERROR: Alchemy returned no floor price data.")
    
    await client.close()

client.run(DISCORD_TOKEN)
