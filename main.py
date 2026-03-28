import discord
from discord import app_commands
from discord.ext import commands, tasks
import random, string, json, datetime, os
from threading import Thread
from flask import Flask

# --- RAILWAY STABILITÁS ---
app = Flask('')
@app.route('/')
def home(): return "Bot is online!"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- KONFIGURÁCIÓ ---
TOKEN = os.environ.get('DISCORD_TOKEN')
DATABASE = 'staff_system.json'

class StaffBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.msg_cooldown = {} # Üzenet számláló

    async def setup_hook(self):
        self.voice_tracker.start()
        await self.tree.sync()

bot = StaffBot()

# --- ADATKEZELÉS ---
def load_db():
    if not os.path.exists(DATABASE): return {"users": {}, "history": {}, "stats": {}}
    with open(DATABASE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {"users": {}, "history": {}, "stats": {}}

def save_db(data):
    with open(DATABASE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- AKTIVITÁS FIGYELŐ ---
@bot.event
async def on_message(message):
    if message.author.bot: return
    db = load_db()
    uid = str(message.author.id)
    
    if uid not in db["stats"]: db["stats"][uid] = {"points": 0.0, "msg_count": 0}
    
    db["stats"][uid]["msg_count"] += 1
    if db["stats"][uid]["msg_count"] >= 15:
        db["stats"][uid]["points"] += 1
        db["stats"][uid]["msg_count"] = 0
        save_db(db)
    
    await bot.process_commands(message)

@tasks.loop(minutes=1)
async def voice_tracker():
    db = load_db()
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot and not member.voice.self_deaf:
                    uid = str(member.id)
                    if uid not in db["stats"]: db["stats"][uid] = {"points": 0.0, "msg_count": 0}
                    # 1 perc voice = 0.4 pont
                    db["stats"][uid]["points"] += 0.4
    save_db(db)

# --- MODERÁTOR PARANCSOK ---

@bot.tree.command(name="munkaido", description="Moderátori aktivitás lekérése")
@app_commands.checks.has_permissions(moderate_members=True)
async def munkaido(interaction: discord.Interaction, tag: discord.Member):
    db = load_db()
    uid = str(tag.id)
    points = db["stats"].get(uid, {}).get("points", 0)

    # Szint kalkuláció
    if points < 500:
        level = "Junior Moderator (Cél: 500)"
        percent = (points / 500) * 100
    elif points < 10000:
        level = "Moderator (Cél: 10000)"
        percent = (points / 10000) * 100
    else:
        level = "Max Szint Elérve"
        percent = 100

    embed = discord.Embed(title="📊 Munkaidő Statisztika", color=0x3498db, timestamp=discord.utils.utcnow())
    embed.set_author(name=tag.name, icon_url=tag.display_avatar.url)
    embed.add_field(name="✨ Összes pont", value=f"`{points:.1f}` pont", inline=True)
    embed.add_field(name="📈 Haladás", value=f"`{percent:.1f}%`", inline=True)
    embed.add_field(name="🎖️ Aktuális szint", value=level, inline=False)
    
    # Progress bar készítése
    filled = int(percent / 10)
    bar = "🟦" * filled + "⬜" * (10 - filled)
    embed.add_field(name="Progress Bar", value=bar, inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="figyelmeztetes", description="⚠️ Tag figyelmeztetése")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, tag: discord.Member, indok: str):
    if tag.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("❌ Magasabb rangút nem büntethetsz!", ephemeral=True)
    
    db = load_db()
    uid = str(tag.id)
    warn_id = "TO-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    db["users"][uid] = db["users"].get(uid, 0) + 1
    count = db["users"][uid]

    dur = 10 if count <= 3 else (60 if count <= 5 else 1440)
    szankcio = f"{dur // 60 if dur >= 60 else dur} {'óra' if dur >= 60 else 'perc'} némítás"
    
    until = discord.utils.utcnow() + datetime.timedelta(minutes=dur)
    try: await tag.timeout(until, reason=f"{warn_id} | {indok}")
    except: szankcio = "Hiba a némításnál"

    db["history"][warn_id] = {"user_id": tag.id, "reason": indok, "mod": interaction.user.name}
    save_db(db)

    embed = discord.Embed(title="🛑 Figyelmeztetés", color=0xff2d2d)
    embed.add_field(name="👤 Tag", value=tag.mention, inline=True)
    embed.add_field(name="🆔 ID", value=f"`{warn_id}`", inline=True)
    embed.add_field(name="📝 Indok", value=indok, inline=False)
    embed.add_field(name="⚖️ Szankció", value=f"**{szankcio}** ({count}. alkalom)")
    
    await interaction.response.send_message(embed=embed)
    try: await tag.send(embed=embed)
    except: pass

# --- HIBAKEZELÉS ---
@munkaido.error
async def error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⛔ Ezt csak moderátorok használhatják!", ephemeral=True)

if __name__ == "__main__":
    Thread(target=run_web).start()
    if TOKEN: bot.run(TOKEN)
    else: print("Nincs DISCORD_TOKEN!")
