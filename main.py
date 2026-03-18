import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import datetime
import random
import os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

giveaways = {}
spam_tracker = {}
mute_times = {}

# -------------------- SPAM SZŰRŐ --------------------

SPAM_LIMIT = 5
SPAM_TIME = 6  # mp

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.datetime.utcnow()
    user_id = message.author.id

    spam_tracker.setdefault(user_id, [])
    spam_tracker[user_id] = [
        t for t in spam_tracker[user_id]
        if (now - t).seconds < SPAM_TIME
    ]
    spam_tracker[user_id].append(now)

    if len(spam_tracker[user_id]) >= SPAM_LIMIT:
        await message.delete()

        mute_times[user_id] = mute_times.get(user_id, 0) + 2
        minutes = mute_times[user_id]

        until = datetime.timedelta(minutes=minutes)
        await message.author.timeout(until, reason="Automatikus spam szűrő")

        embed = discord.Embed(
            title="🚫 Spam figyelmeztetés",
            description=f"**Indok:** túl sok üzenet rövid időn belül\n🔇 Némítás: **{minutes} perc**",
            color=discord.Color.red()
        )
        await message.channel.send(embed=embed)

    await bot.process_commands(message)

# -------------------- GIVEAWAY VIEW --------------------

class GiveawayView(discord.ui.View):
    def __init__(self, msg_id):
        super().__init__(timeout=None)
        self.msg_id = msg_id

    @discord.ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = giveaways[self.msg_id]
        if interaction.user.id not in g["participants"]:
            g["participants"].append(interaction.user.id)
            await interaction.response.send_message("✅ Jelentkeztél!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Már jelentkeztél!", ephemeral=True)

    @discord.ui.button(label="Jelentkezés törlése", style=discord.ButtonStyle.danger)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = giveaways[self.msg_id]
        if interaction.user.id in g["participants"]:
            g["participants"].remove(interaction.user.id)
            await interaction.response.send_message("❌ Jelentkezés törölve!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Nem voltál jelentkezve!", ephemeral=True)

# -------------------- GIVEAWAY PARANCS --------------------

@bot.tree.command(name="nyeremenyjatek")
@app_commands.describe(
    nyeremeny="Mi a nyeremény?",
    ido="Időtartam (pl: 10m, 2h, 1d)",
    nyertesek="Nyertesek száma"
)
async def nyeremenyjatek(interaction: discord.Interaction, nyeremeny: str, ido: str, nyertesek: int):
    now = datetime.datetime.utcnow()

    if ido.endswith("m"):
        end = now + datetime.timedelta(minutes=int(ido[:-1]))
    elif ido.endswith("h"):
        end = now + datetime.timedelta(hours=int(ido[:-1]))
    elif ido.endswith("d"):
        end = now + datetime.timedelta(days=int(ido[:-1]))
    else:
        await interaction.response.send_message("❌ Rossz időformátum!", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎉 Nyereményjáték",
        description=nyeremeny,
        color=discord.Color.blue()
    )
    embed.add_field(name="🏆 Nyertesek száma", value=nyertesek)
    embed.add_field(name="⏳ Vége", value=end.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="👥 Jelentkezők", value="0")

    msg = await interaction.channel.send(embed=embed, view=GiveawayView(None))
    giveaways[msg.id] = {
        "prize": nyeremeny,
        "end": end,
        "winners": nyertesek,
        "participants": [],
        "channel": interaction.channel.id
    }
    msg.view.msg_id = msg.id
    await interaction.response.send_message("✅ Nyereményjáték elindítva!", ephemeral=True)

# -------------------- GIVEAWAY LOOP --------------------

@tasks.loop(seconds=30)
async def check_giveaways():
    now = datetime.datetime.utcnow()
    for gid, g in list(giveaways.items()):
        if now >= g["end"]:
            channel = bot.get_channel(g["channel"])
            if not g["participants"]:
                await channel.send("❌ Nem volt jelentkező.")
            else:
                winners = random.sample(
                    g["participants"],
                    min(g["winners"], len(g["participants"]))
                )
                mentions = ", ".join(f"<@{w}>" for w in winners)

                embed = discord.Embed(
                    title="🎊 Nyereményjáték véget ért!",
                    description=f"🎁 **{g['prize']}**\n👑 Nyertes(ek): {mentions}",
                    color=discord.Color.green()
                )
                await channel.send(embed=embed)

            giveaways.pop(gid)

# -------------------- REROLL --------------------

@bot.tree.command(name="reroll")
@app_commands.describe(uzenet_id="Giveaway üzenet ID")
async def reroll(interaction: discord.Interaction, uzenet_id: str):
    mid = int(uzenet_id)
    if mid not in giveaways:
        await interaction.response.send_message("❌ Nincs ilyen nyereményjáték.", ephemeral=True)
        return

    g = giveaways[mid]
    if not g["participants"]:
        await interaction.response.send_message("❌ Nincs jelentkező.", ephemeral=True)
        return

    winner = random.choice(g["participants"])
    await interaction.channel.send(f"🔁 Új nyertes: <@{winner}>")
    await interaction.response.send_message("✅ Reroll kész!", ephemeral=True)

# -------------------- READY --------------------

@bot.event
async def on_ready():
    await bot.tree.sync()
    check_giveaways.start()
    print("✅ Bot elindult")

bot.run(TOKEN)
