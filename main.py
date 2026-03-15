import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, random

# ================== ALAP ==================

TOKEN = os.getenv("DISCORD_TOKEN")
WARN_FILE = "warns.json"
RAFFLE_FILE = "raffle.json"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= SEGÉD =================

def load_json(file):
    if not os.path.exists(file):
        return {}
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def make_embed(title, desc, color):
    return discord.Embed(
        title=title,
        description=desc,
        color=color,
        timestamp=datetime.datetime.utcnow()
    )

def mod_check(i: discord.Interaction):
    p = i.user.guild_permissions
    return p.administrator or p.manage_messages

# ================= READY (ITT VOLT A HIBA) =================

@bot.event
async def on_ready():
    print(f"✅ Bot online: {bot.user}")
    try:
        # Ez a sor regisztrálja a perjel (slash) parancsokat a Discordnál
        synced = await bot.tree.sync()
        print(f"♻️ Sikeresen szinkronizálva: {len(synced)} slash parancs.")
    except Exception as e:
        print(f"❌ Hiba a szinkronizálásnál: {e}")

# ================= SPAM SZŰRŐ =================

spam_cache = {}

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild:
        return

    if msg.author.guild_permissions.manage_messages or msg.author.guild_permissions.administrator:
        return

    uid = str(msg.author.id)
    now = datetime.datetime.utcnow()

    spam_cache.setdefault(uid, [])
    spam_cache[uid].append((msg.content, now))

    spam_cache[uid] = [(m, t) for m, t in spam_cache[uid] if (now - t).total_seconds() <= 5]
    same_msgs = [m for m, t in spam_cache[uid] if m == msg.content]

    if len(same_msgs) >= 3:
        await msg.delete()
        data = load_json(WARN_FILE)
        data.setdefault(uid, [])
        data[uid].append("Spam üzenetek küldése")
        save_json(WARN_FILE, data)

        mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))

        await msg.channel.send(
            embed=make_embed(
                "🚨 Automatikus SPAM figyelmeztetés",
                f"👤 {msg.author.mention}\n"
                f"📄 **Indok:** Spam üzenetek küldése\n"
                f"⚠️ Figyelmeztetések: {len(data[uid])}\n"
                f"🔇 Némítás: {mute_time} perc",
                discord.Color.red()
            )
        )

        spam_cache[uid].clear()
        return

    await bot.process_commands(msg)

# ================= NYEREMÉNYJÁTÉK =================

@bot.tree.command(name="nyereményjáték", description="Új nyereményjáték indítása")
@app_commands.check(mod_check)
async def start_raffle(i: discord.Interaction, szoveg: str):
    data = {
        "channel_id": i.channel.id,
        "message_id": 0,
        "participants": []
    }

    embed = make_embed(
        "🎉 NYEREMÉNYJÁTÉK 🎉",
        f"{szoveg}\n\n**Jelentkezéshez reagálj az 🎟️ emojira!**",
        discord.Color.green()
    )

    # Először válaszolunk az interakcióra, hogy ne járjon le az idő
    await i.response.send_message("✅ Nyereményjáték elindítva!", ephemeral=True)
    
    msg = await i.channel.send(embed=embed)
    await msg.add_reaction("🎟️")
    data["message_id"] = msg.id
    save_json(RAFFLE_FILE, data)

@bot.tree.command(name="end", description="Nyereményjáték lezárása")
@app_commands.check(mod_check)
async def end_raffle(i: discord.Interaction):
    data = load_json(RAFFLE_FILE)
    channel = i.guild.get_channel(data.get("channel_id", 0))
    if not channel:
        return await i.response.send_message("❌ Hiba: nem található csatorna", ephemeral=True)

    try:
        msg = await channel.fetch_message(data["message_id"])
    except:
        return await i.response.send_message("❌ Hiba: nem található üzenet", ephemeral=True)

    users = []
    for reaction in msg.reactions:
        if str(reaction.emoji) == "🎟️":
            async for user in reaction.users():
                if not user.bot:
                    users.append(user)

    if not users:
        return await i.response.send_message("❌ Nincs résztvevő", ephemeral=True)

    winner = random.choice(users)
    embed = make_embed(
        "🏆 NYEREMÉNYJÁTÉK VÉGE 🏆",
        f"A nyertes: {winner.mention}\nGratulálunk! 🎉",
        discord.Color.gold()
    )
    await channel.send(embed=embed)
    await i.response.send_message("✅ Sorsolás kész!", ephemeral=True)

    save_json(RAFFLE_FILE, {})

@bot.tree.command(name="reroll", description="Új nyertes választása")
@app_commands.check(mod_check)
async def reroll(i: discord.Interaction):
    data = load_json(RAFFLE_FILE)
    # Ha nincs aktív játék, megpróbáljuk megkeresni az utolsót a file-ból
    channel_id = data.get("channel_id")
    if not channel_id:
         return await i.response.send_message("❌ Nincs nyereményjáték adat a fájlban", ephemeral=True)

    channel = i.guild.get_channel(channel_id)
    try:
        msg = await channel.fetch_message(data["message_id"])
    except:
        return await i.response.send_message("❌ Hiba: nem található az üzenet", ephemeral=True)

    users = []
    for reaction in msg.reactions:
        if str(reaction.emoji) == "🎟️":
            async for user in reaction.users():
                if not user.bot:
                    users.append(user)

    if not users:
        return await i.response.send_message("❌ Nincs résztvevő", ephemeral=True)

    winner = random.choice(users)
    embed = make_embed(
        "🎲 NYEREMÉNYJÁTÉK ÚJRAHÚZÁS 🎲",
        f"Új nyertes: {winner.mention}\nGratulálunk! 🎉",
        discord.Color.purple()
    )
    await channel.send(embed=embed)
    await i.response.send_message("✅ Új nyertes kiválasztva", ephemeral=True)

# ================= START =================

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ HIÁNYZIK A DISCORD_TOKEN!")
  
