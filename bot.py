import discord
import requests
import os
import asyncio
import random
from datetime import datetime

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

# The slug from the URL: opensea.io/collection/world-computer-netizens-megaeth
COLLECTION_SLUG = "world-computer-netizens-megaeth"

# List of "Human" User-Agents to trick OpenSea
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
]

intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def get_opensea_stats():
    # Attempt 1: The V2 Stats Endpoint
    url = f"https://api.opensea.io/api/v2/collections/{COLLECTION_SLUG}/stats"
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json"
    }
    
    print(f"DEBUG: Hail Mary attempt on {url}")
    
    try:
        response = requests.get(url, headers=headers)
        
        # DEBUG: Print the status to see if we got blocked
        print(f"DEBUG: Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # OpenSea V2 structure: { total: { floor_price: 1.2, ... } }
            floor = data.get('total', {}).get('floor_price')
            if floor:
                return floor
        elif response.status_code == 403:
            print("DEBUG: GitHub IP was blocked by OpenSea (403).")
        else:
            print(f"DEBUG: Response Text: {response.text}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        
    return None

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    
    price = await get_opensea_stats()
    
    if price:
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="💎 Floor Price Update", url=f"https://opensea.io/collection/{COLLECTION_SLUG}", color=0x2081E2)
            embed.add_field(name="Collection", value="World Computer Netizens", inline=True)
            embed.add_field(name="Floor Price", value=f"**{price} ETH**", inline=True)
            embed.set_footer(text=f"Updated: {datetime.now().strftime('%H:%M')} via OpenSea")
            
            await channel.send(embed=embed)
            print(f"SUCCESS: Posted price: {price}")
        else:
            print(f"ERROR: Channel {CHANNEL_ID} not found.")
    else:
        print("ERROR: Could not fetch price. OpenSea might have blocked the GitHub server.")
    
    await client.close()

client.run(DISCORD_TOKEN)
