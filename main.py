import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, json, datetime, asyncio, random, time

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

WARN_FILE = "warns.json"
GIVEAWAY_FILE = "giveaways.json"

# ================= SEGÉD =================

def load_json(f):
    if not os.path.exists(f):
        return {}
    with open(f, "r", encoding="utf-8") as file:
        return json.load(file)

def save_json(f, d):
    with open(f, "w", encoding="utf-8") as file:
        json.dump(d, file, indent=4, ensure_ascii=False)

def mod(i: discord.Interaction):
    p = i.user.guild_permissions
    return p.administrator or p.manage_messages

# ================= READY =================

@bot.event
async def on_ready():
    await bot.tree.sync()
    giveaway_watcher.start()
    print("✅ Bot online")

# ================= SPAMM SZŰRŐ =================

spam_tracker = {}

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild:
        return

    if msg.author.guild_permissions.manage_messages:
        return

    uid = str(msg.author.id)
    now = time.time()

    spam_tracker.setdefault(uid, [])
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < 5]
    spam_tracker[uid].append(now)

    if len(spam_tracker[uid]) >= 5:
        await msg.delete()

        warns = load_json(WARN_FILE)
        warns.setdefault(uid, [])
        warns[uid].append("Spammelés")
        save_json(WARN_FILE, warns)

        mute_minutes = len(warns[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_minutes))

        embed = discord.Embed(
            title="🚨 Automatikus figyelmeztetés",
            description=(
                f"👤 {msg.author.mention}\n"
                f"📄 Indok: Spammelés\n"
                f"⚠️ Figyelmeztetések: {len(warns[uid])}\n"
                f"🔇 Némítás: {mute_minutes} perc"
            ),
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        await msg.channel.send(embed=embed)
        return

    await bot.process_commands(msg)

# ================= NYEREMÉNYJÁTÉK VIEW =================

class GiveawayView(discord.ui.View):
    timeout = None

    @discord.ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary)
    async def join(self, i: discord.Interaction, b: discord.ui.Button):
        data = load_json(GIVEAWAY_FILE)
        gid = str(i.message.id)

        if gid not in data:
            return await i.response.send_message("❌ Lejárt.", ephemeral=True)

        if i.user.id in data[gid]["users"]:
            return await i.response.send_message("⚠️ Már jelentkeztél.", ephemeral=True)

        data[gid]["users"].append(i.user.id)
        save_json(GIVEAWAY_FILE, data)

        embed = i.message.embeds[0]
        embed.set_field_at(4, name="👥 Jelentkezők", value=str(len(data[gid]["users"])), inline=False)
        await i.message.edit(embed=embed)

        await i.response.send_message("✅ Jelentkezés sikeres!", ephemeral=True)

    @discord.ui.button(label="Jelentkezés törlése", style=discord.ButtonStyle.danger)
    async def leave(self, i: discord.Interaction, b: discord.ui.Button):
        data = load_json(GIVEAWAY_FILE)
        gid = str(i.message.id)

        if gid not in data or i.user.id not in data[gid]["users"]:
            return await i.response.send_message("❌ Nem voltál jelentkezve.", ephemeral=True)

        data[gid]["users"].remove(i.user.id)
        save_json(GIVEAWAY_FILE, data)

        embed = i.message.embeds[0]
        embed.set_field_at(4, name="👥 Jelentkezők", value=str(len(data[gid]["users"])), inline=False)
        await i.message.edit(embed=embed)

        await i.response.send_message("❌ Jelentkezés törölve.", ephemeral=True)

# ================= /NYEREMÉNYJÁTÉK =================

@bot.tree.command(name="nyereményjáték")
@app_commands.check(mod)
async def giveaway(
    i: discord.Interaction,
    nyeremény: str,
    leírás: str,
    nyertesek: int,
    idő_perc: int
):
    end = datetime.datetime.utcnow() + datetime.timedelta(minutes=idő_perc)

    embed = discord.Embed(
        title="🎊 Nyereményjáték",
        description=nyeremény,
        color=discord.Color.blue()
    )
    embed.add_field(name="📄 Leírás", value=leírás, inline=False)
    embed.add_field(name="🏆 Nyertesek száma", value=str(nyertesek), inline=True)
    embed.add_field(name="⏳ Időtartam", value=f"{idő_perc} perc", inline=True)
    embed.add_field(name="🕒 Vége", value=f"<t:{int(end.timestamp())}:F>", inline=False)
    embed.add_field(name="👥 Jelentkezők", value="0", inline=False)

    view = GiveawayView()
    await i.response.send_message(embed=embed, view=view)
    msg = await i.original_response()

    data = load_json(GIVEAWAY_FILE)
    data[str(msg.id)] = {
        "channel": msg.channel.id,
        "end": end.timestamp(),
        "winners": nyertesek,
        "user
