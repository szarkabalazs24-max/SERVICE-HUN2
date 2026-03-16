import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, json, datetime, asyncio, random, re

# ================== ALAP ==================

TOKEN = os.getenv("DISCORD_TOKEN")

WARN_FILE = "warns.json"
GIVEAWAY_FILE = "giveaways.json"

LINK_REGEX = r"(https?://|www\.)"
SPAM_LIMIT = 5
SPAM_TIME = 7  # másodperc

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

message_cache = {}

# ================= SEGÉD =================

def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

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

# ================= READY =================

@bot.event
async def on_ready():
    await bot.tree.sync()
    giveaway_loop.start()
    print("✅ Bot online | Slash parancsok szinkronizálva")

# ================= SPAM SZŰRŐ =================

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild:
        return

    uid = msg.author.id
    now = datetime.datetime.utcnow()

    message_cache.setdefault(uid, [])
    message_cache[uid] = [
        t for t in message_cache[uid]
        if (now - t).seconds <= SPAM_TIME
    ]
    message_cache[uid].append(now)

    if len(message_cache[uid]) >= SPAM_LIMIT:
        await msg.delete()

        data = load_json(WARN_FILE)
        data.setdefault(str(uid), []).append("Spammelés")
        save_json(WARN_FILE, data)

        mute_time = len(data[str(uid)]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))

        embed = make_embed(
            "🚫 Automatikus SPAM szűrő",
            f"👤 {msg.author.mention}\n"
            f"📄 Indok: Spammelés\n"
            f"⚠️ Figyelmeztetések: {len(data[str(uid)])}\n"
            f"🔇 Némítás: {mute_time} perc",
            discord.Color.red()
        )

        await msg.channel.send(embed=embed)
        return

    if re.search(LINK_REGEX, msg.content.lower()):
        await msg.delete()
        return

    await bot.process_commands(msg)

# ================= NYEREMÉNYJÁTÉK =================

@bot.tree.command(name="nyereményjáték")
@app_commands.check(mod_check)
async def giveaway(
    i: discord.Interaction,
    idő_perc: int,
    nyertesek: int,
    nyeremény: str
):
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=idő_perc)

    embed = discord.Embed(
        title="🎉 NYEREMÉNYJÁTÉK 🎉",
        description=(
            f"🏆 **Nyeremény:** {nyeremény}\n"
            f"👥 **Jelentkezők:** 0\n"
            f"⏳ **Vége:** <t:{int(end_time.timestamp())}:R>\n"
            f"🥇 **Nyertesek:** {nyertesek}"
        ),
        color=discord.Color.purple()
    )

    msg = await i.channel.send(embed=embed)
    await msg.add_reaction("🎉")

    data = load_json(GIVEAWAY_FILE)
    data[str(msg.id)] = {
        "channel": msg.channel.id,
        "end": end_time.timestamp(),
        "winners": nyertesek
    }
    save_json(GIVEAWAY_FILE, data)

    await i.response.send_message("✅ Nyereményjáték elindítva", ephemeral=True)

# ================= NYEREMÉNYJÁTÉK LOOP =================

@tasks.loop(seconds=10)
async def giveaway_loop():
    data = load_json(GIVEAWAY_FILE)
    now = datetime.datetime.utcnow().timestamp()
    changed = False

    for mid, g in list(data.items()):
        if now >= g["end"]:
            channel = bot.get_channel(g["channel"])
            if not channel:
                continue

            msg = await channel.fetch_message(int(mid))
            users = []

            for reaction in msg.reactions:
                async for u in reaction.users():
                    if not u.bot:
                        users.append(u)

            if users:
                winners = random.sample(users, min(g["winners"], len(users)))
                win_text = ", ".join(w.mention for w in winners)
            else:
                win_text = "❌ Nem volt jelentkező"

            end_embed = discord.Embed(
                title="🎉 NYEREMÉNYJÁTÉK VÉGE 🎉",
                description=f"🏆 **Nyertes(ek):** {win_text}",
                color=discord.Color.green()
            )

            await channel.send(embed=end_embed)
            del data[mid]
            changed = True

    if changed:
        save_json(GIVEAWAY_FILE, data)

# ================= REROLL =================

@bot.tree.command(name="reroll")
@app_commands.check(mod_check)
async def reroll(i: discord.Interaction, üzenet_id: str, nyertesek: int):
    msg = await i.channel.fetch_message(int(üzenet_id))

    users = set()
    for reaction in msg.reactions:
        async for u in reaction.users():
            if not u.bot:
                users.add(u)

    if not users:
        return await i.response.send_message("❌ Nincs jelentkező", ephemeral=True)

    winners = random.sample(list(users), min(nyertesek, len(users)))
    mentions = ", ".join(w.mention for w in winners)

    embed = discord.Embed(
        title="🔄 Újrasorsolás",
        description=f"🏆 **Új nyertes(ek):** {mentions}\n👥 Jelentkezők: {len(users)}",
        color=discord.Color.gold()
    )

    await i.response.send_message(embed=embed)

# ================= START =================

bot.run(TOKEN)
