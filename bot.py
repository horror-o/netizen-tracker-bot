import discord
import requests
import os
import asyncio
from datetime import datetime

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
RESERVOIR_API_KEY = os.getenv('RESERVOIR_API_KEY', 'demo-api-key')
COLLECTION_SLUG = "world-computer-netizens-megaeth"
URL = "https://api.reservoir.tools/collections/v5"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def get_floor_price():
    params = {
        "slug": COLLECTION_SLUG,
        "includeTopBid": "false"
    }
    headers = {
        "accept": "application/json",
        "x-api-key": RESERVOIR_API_KEY
    }
    try:
        response = requests.get(URL, params=params, headers=headers)
        data = response.json()
        if 'collections' in data and len(data['collections']) > 0:
            return data['collections'][0]
    except Exception as e:
        print(f"Error fetching price: {e}")
    return None

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    
    # 1. Fetch Price
    collection = await get_floor_price()
    
    if collection:
        floor_ask = collection.get('floorAsk', {})
        price = floor_ask.get('price', {}).get('amount', {}).get('native')
        currency = floor_ask.get('price', {}).get('currency', {}).get('symbol', 'ETH')
        
        if price:
            channel = client.get_channel(CHANNEL_ID)
            if channel:
                # 2. Create Embed
                embed = discord.Embed(title="💎 Floor Price Update", url=f"https://opensea.io/collection/{COLLECTION_SLUG}", color=0x00ff00)
                embed.add_field(name="Collection", value="World Computer Netizens", inline=True)
                embed.add_field(name="Floor Price", value=f"**{price} {currency}**", inline=True)
                embed.set_footer(text=f"Updated: {datetime.now().strftime('%H:%M')} via Reservoir")
                
                # 3. Send and Quit
                await channel.send(embed=embed)
                print(f"Posted price: {price}")
            else:
                print(f"Channel {CHANNEL_ID} not found.")
        else:
            print("No price found.")
    else:
        print("Collection not found.")

    # 4. Stop the bot (Close connection)
    await client.close()

# Run the bot
client.run(DISCORD_TOKEN)
