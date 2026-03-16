import discord
from discord.ext import commands
from discord import app_commands
import os, json, asyncio, datetime, random, time

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

WARN_FILE = "warns.json"

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

def is_mod(i: discord.Interaction):
    p = i.user.guild_permissions
    return p.administrator or p.manage_messages

# ================= READY =================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("✅ Bot online – Railway stabil")

# ================= SPAMM SZŰRŐ =================

spam_cache = {}

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild:
        return

    if msg.author.guild_permissions.manage_messages:
        return

    uid = str(msg.author.id)
    now = time.time()

    spam_cache.setdefault(uid, [])
    spam_cache[uid] = [t for t in spam_cache[uid] if now - t < 5]
    spam_cache[uid].append(now)

    if len(spam_cache[uid]) >= 5:
        try:
            await msg.delete()
        except:
            pass

        warns = load_json(WARN_FILE)
        warns.setdefault(uid, [])
        warns[uid].append("Spammelés")
        save_json(WARN_FILE, warns)

        mute_time = len(warns[uid]) * 2

        try:
            await msg.author.timeout(datetime.timedelta(minutes=mute_time))
        except:
            pass

        embed = discord.Embed(
            title="🚨 Automatikus figyelmeztetés",
            description=(
                f"👤 {msg.author.mention}\n"
                f"📄 Indok: Spammelés\n"
                f"⚠️ Figyelmeztetések: {len(warns[uid])}\n"
                f"🔇 Némítás: {mute_time} perc"
            ),
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        try:
            await msg.channel.send(embed=embed)
        except:
            pass

    await bot.process_commands(msg)

# ================= NYEREMÉNYJÁTÉK =================

class GiveawayButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.users = set()

    @discord.ui.button(label="🎉 Jelentkezem", style=discord.ButtonStyle.primary)
    async def join(self, i: discord.Interaction, _):
        if i.user.id in self.users:
            return await i.response.send_message("⚠️ Már jelentkeztél.", ephemeral=True)

        self.users.add(i.user.id)
        await i.response.send_message("✅ Jelentkezés sikeres!", ephemeral=True)

    @discord.ui.button(label="❌ Jelentkezés törlése", style=discord.ButtonStyle.danger)
    async def leave(self, i: discord.Interaction, _):
        self.users.discard(i.user.id)
        await i.response.send_message("❌ Jelentkezés törölve.", ephemeral=True)

# ================= /NYEREMÉNYJÁTÉK =================

@bot.tree.command(name="nyereményjáték")
@app_commands.check(is_mod)
async def giveaway(
    i: discord.Interaction,
    nyeremény: str,
    leírás: str,
    nyertesek: int,
    idő_perc: int
):
    view = GiveawayButtons()

    embed = discord.Embed(
        title="🎊 Nyereményjáték",
        description=nyeremény,
        color=discord.Color.blue()
    )
    embed.add_field(name="📄 Leírás", value=leírás, inline=False)
    embed.add_field(name="🏆 Nyertesek száma", value=str(nyertesek), inline=True)
    embed.add_field(name="⏳ Időtartam", value=f"{idő_perc} perc", inline=True)

    await i.response.send_message(embed=embed, view=view)

    async def end():
        await asyncio.sleep(idő_perc * 60)

        if not view.users:
            await i.channel.send("❌ A nyereményjátéknak nincs nyertese.")
            return

        winners = random.sample(list(view.users), min(nyertesek, len(view.users)))
        mentions = ", ".join(f"<@{u}>" for u in winners)

        end_embed = discord.Embed(
            title="🎉 Nyereményjáték véget ért!",
            description=(
                f"🎁 Nyertesek száma: {nyertesek}\n"
                f"👥 Résztvevők: {len(view.users)}\n\n"
                f"🏆 Nyertes(ek): {mentions}"
            ),
            color=discord.Color.green()
        )

        await i.channel.send(embed=end_embed)

    bot.loop.create_task(end())

# ================= START =================

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN hiányzik")
