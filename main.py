import discord
from discord import app_commands
from discord.ext import commands
import random
import string
import json
import datetime
import os

# --- KONFIGURÁCIÓ ---
TOKEN = 'A_TE_BOT_TOKENED'
DATABASE = 'warn_db.json'

class ProfessionalWarnBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✨ A bot készen áll: {self.user}")

bot = ProfessionalWarnBot()

# --- ADATBÁZIS FÜGGVÉNYEK ---
def load_db():
    if not os.path.exists(DATABASE):
        return {"users": {}, "history": {}}
    with open(DATABASE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(data):
    with open(DATABASE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def generate_id():
    return "TO-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

# --- PARANCSOK ---

@bot.tree.command(name="figyelmeztetes", description="Tag figyelmeztetése és profi szankcionálása")
@app_commands.describe(tag="A szabályszegő tag", indok="Miért kapja a figyelmeztetést?")
async def warn(interaction: discord.Interaction, tag: discord.Member, indok: str):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ **Nincs jogosultságod ehhez a művelethez!**", ephemeral=True)

    db = load_db()
    uid = str(tag.id)
    warn_id = generate_id()

    # Számláló és szankció logika
    db["users"][uid] = db["users"].get(uid, 0) + 1
    count = db["users"][uid]

    if count <= 3:
        dur, szankcio = 10, "⏳ 10 perc némítás"
    elif count <= 5:
        dur, szankcio = 60, "⏰ 1 óra némítás"
    else:
        dur, szankcio = 1440, "🚫 1 napos némítás"

    # Némítás végrehajtása
    until = discord.utils.utcnow() + datetime.timedelta(minutes=dur)
    try:
        await tag.timeout(until, reason=f"ID: {warn_id} | {indok}")
    except:
        szankcio = "⚠️ Hiba (nincs jogom némítani!)"

    # Mentés az előzményekbe
    db["history"][warn_id] = {"user_id": tag.id, "reason": indok, "mod": interaction.user.name}
    save_db(db)

    # --- ESZTÉTIKUS EMBED A CSATORNÁBA ---
    embed = discord.Embed(
        title="🛑 Rendszer Figyelmeztetés",
        description=f"Sajnálatos módon szabályszegés történt a(z) **{interaction.guild.name}** szerveren.",
        color=0xff2d2d, # Élénk piros
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=tag.display_avatar.url)
    embed.add_field(name="👤 Figyelmeztetve", value=f"{tag.mention}\n`{tag.name}`", inline=True)
    embed.add_field(name="🛡️ Intézkedett", value=f"{interaction.user.mention}\n`{interaction.user.name}`", inline=True)
    embed.add_field(name="📝 Indoklás", value=f"```\n{indok}\n```", inline=False)
    embed.add_field(name="⚖️ Szankció", value=f"**{szankcio}**", inline=True)
    embed.add_field(name="🆔 Figyelmeztetés ID", value=f"`{warn_id}`", inline=True)
    embed.set_footer(text=f"Ez a felhasználó {count}. figyelmeztetése.")

    await interaction.response.send_message(embed=embed)

    # --- PRIVÁT ÜZENET ---
    try:
        dm_embed = embed
        dm_embed.title = f"⚠️ Figyelmeztetést kaptál: {interaction.guild.name}"
        await tag.send(embed=dm_embed)
    except: pass

@bot.tree.command(name="figyelmeztetestorles", description="Figyelmeztetés visszavonása ID alapján")
@app_commands.describe(tag="A tag akitől levonod", warn_id="Például: TO-A1B2C", indok="Miért törlöd?")
async def remove_warn(interaction: discord.Interaction, tag: discord.Member, warn_id: str, indok: str):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ **Nincs jogosultságod a törléshez!**", ephemeral=True)

    db = load_db()
    uid = str(tag.id)

    if warn_id not in db["history"] or db["history"][warn_id]["user_id"] != tag.id:
        return await interaction.response.send_message(f"❌ **Érvénytelen ID!** Nem találtam ilyen figyelmeztetést ennél a tagnál.", ephemeral=True)

    # Adatok frissítése
    del db["history"][warn_id]
    if uid in db["users"] and db["users"][uid] > 0:
        db["users"][uid] -= 1
    save_db(db)

    # --- ESZTÉTIKUS EMBED A TÖRLÉSHEZ ---
    embed = discord.Embed(
        title="✅ Figyelmeztetés Visszavonva",
        color=0x2ecc71, # Kedves zöld
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 Érintett tag", value=tag.mention, inline=True)
    embed.add_field(name="🛡️ Moderátor", value=interaction.user.mention, inline=True)
    embed.add_field(name="🆔 Törölt ID", value=f"`{warn_id}`", inline=True)
    embed.add_field(name="📁 Törlés indoka", value=f"*{indok}*", inline=False)
    embed.set_footer(text=f"Maradék figyelmeztetések: {db['users'].get(uid, 0)}")

    await interaction.response.send_message(embed=embed)
    try: await tag.send(f"✨ Jó hír! Egy figyelmeztetésedet törölték a(z) **{interaction.guild.name}** szerveren.", embed=embed)
    except: pass

bot.run(TOKEN)
      
