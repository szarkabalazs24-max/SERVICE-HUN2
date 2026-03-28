import discord
from discord import app_commands
from discord.ext import commands
import random
import string
import json
import datetime
import os
from threading import Thread
from flask import Flask

# --- RAILWAY STABILITÁS (Webszerver) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is online!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- BEÁLLÍTÁSOK ---
TOKEN = os.environ.get('DISCORD_TOKEN')
DATABASE = 'warn_db.json'

class SecureWarnBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = SecureWarnBot()

# --- ADATKEZELÉS ---
def load_db():
    if not os.path.exists(DATABASE): return {"users": {}, "history": {}}
    with open(DATABASE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {"users": {}, "history": {}}

def save_db(data):
    with open(DATABASE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- PARANCSOK (CSAK MODERÁTOROKNAK) ---

@bot.tree.command(name="figyelmeztetes", description="⚠️ Tag figyelmeztetése (Csak Moderátorok!)")
@app_commands.checks.has_permissions(moderate_members=True) # JOGOSULTSÁG ELLENŐRZÉS
async def warn(interaction: discord.Interaction, tag: discord.Member, indok: str):
    # Hierarchia ellenőrzése
    if tag.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("❌ **Hiba:** Nem figyelmeztethetsz veled egyenrangú vagy feletted álló tagot!", ephemeral=True)

    db = load_db()
    uid = str(tag.id)
    warn_id = "TO-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

    db["users"][uid] = db["users"].get(uid, 0) + 1
    count = db["users"][uid]

    # Időzítés logika
    if count <= 3: dur, szankcio = 10, "⏳ 10 perc némítás"
    elif count <= 5: dur, szankcio = 60, "⏰ 1 óra némítás"
    else: dur, szankcio = 1440, "🚫 1 napos némítás"

    until = discord.utils.utcnow() + datetime.timedelta(minutes=dur)
    try:
        await tag.timeout(until, reason=f"ID: {warn_id} | {indok}")
    except:
        szankcio = "⚠️ Nincs jogom némítani ezt a tagot!"

    db["history"][warn_id] = {"user_id": tag.id, "reason": indok, "mod": interaction.user.name}
    save_db(db)

    embed = discord.Embed(title="🛑 Rendszer Figyelmeztetés", color=0xff2d2d, timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=tag.display_avatar.url)
    embed.add_field(name="👤 Megbüntetett", value=tag.mention, inline=True)
    embed.add_field(name="🛡️ Moderátor", value=interaction.user.mention, inline=True)
    embed.add_field(name="📝 Indok", value=f"```\n{indok}\n```", inline=False)
    embed.add_field(name="⚖️ Szankció", value=f"**{szankcio}**", inline=True)
    embed.add_field(name="🆔 ID", value=f"`{warn_id}`", inline=True)
    embed.set_footer(text=f"Figyelmeztetések száma: {count}")

    await interaction.response.send_message(embed=embed)
    try: await tag.send(f"⚠️ Figyelmeztetve lettél a(z) **{interaction.guild.name}** szerveren!", embed=embed)
    except: pass

@bot.tree.command(name="figyelmeztetestorles", description="✅ Figyelmeztetés visszavonása (Csak Moderátorok!)")
@app_commands.checks.has_permissions(moderate_members=True) # JOGOSULTSÁG ELLENŐRZÉS
async def remove_warn(interaction: discord.Interaction, tag: discord.Member, warn_id: str, indok: str):
    db = load_db()
    if warn_id not in db["history"] or db["history"][warn_id]["user_id"] != tag.id:
        return await interaction.response.send_message("❌ **Hiba:** Érvénytelen ID vagy nem ehhez a taghoz tartozik!", ephemeral=True)

    del db["history"][warn_id]
    if str(tag.id) in db["users"] and db["users"][str(tag.id)] > 0:
        db["users"][str(tag.id)] -= 1
    save_db(db)

    embed = discord.Embed(title="✨ Figyelmeztetés Törölve", color=0x2ecc71, timestamp=discord.utils.utcnow())
    embed.add_field(name="👤 Érintett", value=tag.mention, inline=True)
    embed.add_field(name="🆔 Törölt ID", value=f"`{warn_id}`", inline=True)
    embed.add_field(name="📂 Törlés oka", value=f"*{indok}*", inline=False)
    
    await interaction.response.send_message(embed=embed)
    try: await tag.timeout(None); await tag.send(embed=embed)
    except: pass

# --- HIBAKEZELÉS (Ha nem moderátor próbálja) ---
@warn.error
@remove_warn.error
async def error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⛔ **Nincs jogosultságod!** Ezt csak moderátorok tehetik meg.", ephemeral=True)

if __name__ == "__main__":
    Thread(target=run_web).start()
    if TOKEN: bot.run(TOKEN)
    else: print("❌ HIBA: Nincs DISCORD_TOKEN környezeti változó!")
          
