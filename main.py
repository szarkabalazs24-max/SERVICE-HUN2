import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, asyncio, datetime, random

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

giveaways = {}
spam_data = {}

# ================= READY =================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online: {bot.user}")

# ================= SPAM SZŰRŐ =================

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild:
        return

    now = datetime.datetime.utcnow().timestamp()
    uid = msg.author.id

    spam_data.setdefault(uid, [])
    spam_data[uid] = [t for t in spam_data[uid] if now - t < 5]
    spam_data[uid].append(now)

    if len(spam_data[uid]) >= 5:
        await msg.delete()

        warns = len(spam_data[uid])
        mute_time = warns * 2

        await msg.author.timeout(
            datetime.timedelta(minutes=mute_time),
            reason="Spammelés"
        )

        embed = discord.Embed(
            title="🚫 Spamm szűrő",
            description=(
                f"👤 {msg.author.mention}\n"
                f"📄 Indok: Spammelés\n"
                f"🔇 Némítás: {mute_time} perc"
            ),
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        await msg.channel.send(embed=embed)

    await bot.process_commands(msg)

# ================= NYEREMÉNYJÁTÉK =================

class GiveawayView(discord.ui.View):
    def __init__(self, gid):
        super().__init__(timeout=None)
        self.gid = gid

    @discord.ui.button(label="Jelentkezem!", style=discord.ButtonStyle.blurple)
    async def join(self, interaction: discord.Interaction, _):
        g = giveaways[self.gid]
        if interaction.user.id in g["users"]:
            return await interaction.response.send_message(
                "❌ Már jelentkeztél!", ephemeral=True
            )
        g["users"].add(interaction.user.id)
        await interaction.response.send_message("✅ Jelentkeztél!", ephemeral=True)
        await update_embed(self.gid)

    @discord.ui.button(label="Jelentkezés törlése", style=discord.ButtonStyle.danger)
    async def leave(self, interaction: discord.Interaction, _):
        g = giveaways[self.gid]
        g["users"].discard(interaction.user.id)
        await interaction.response.send_message("❌ Jelentkezés törölve", ephemeral=True)
        await update_embed(self.gid)

async def update_embed(gid):
    g = giveaways[gid]
    embed = build_embed(g)
    await g["msg"].edit(embed=embed)

def build_embed(g):
    embed = discord.Embed(
        title="🎉 Nyereményjáték",
        description=g["prize"],
        color=discord.Color.blue()
    )
    embed.add_field(name="📄 Leírás", value="Sok szerencsét mindenkinek", inline=False)
    embed.add_field(name="🏆 Nyertesek száma", value=str(g["winners"]), inline=True)
    embed.add_field(name="⏳ Hátralévő idő", value=f"<t:{g['end']}:R>", inline=True)
    embed.add_field(name="👥 Jelentkezők", value=str(len(g["users"])), inline=True)
    embed.set_footer(text=f"Giveaway ID: {g['msg'].id}")
    return embed

@bot.tree.command(name="nyereményjáték")
@app_commands.checks.has_permissions(administrator=True)
async def giveaway(
    i: discord.Interaction,
    nyeremeny: str,
    nap: int,
    ora: int,
    perc: int,
    nyertesek: int
):
    seconds = nap*86400 + ora*3600 + perc*60
    end = int((datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)).timestamp())

    msg = await i.channel.send("⏳ Nyereményjáték indítása...")
    gid = msg.id

    giveaways[gid] = {
        "prize": nyeremeny,
        "winners": nyertesek,
        "end": end,
        "users": set(),
        "msg": msg,
        "channel": i.channel
    }

    await msg.edit(embed=build_embed(giveaways[gid]), view=GiveawayView(gid))
    await i.response.send_message("✅ Nyereményjáték elindítva!", ephemeral=True)

    await asyncio.sleep(seconds)
    await end_giveaway(gid)

async def end_giveaway(gid):
    g = giveaways.get(gid)
    if not g:
        return

    users = list(g["users"])
    if not users:
        winners = ["Nincs jelentkező"]
    else:
        winners = random.sample(users, min(len(users), g["winners"]))
        winners = [f"<@{u}>" for u in winners]

    embed = discord.Embed(
        title="🎊 Nyereményjáték véget ért!",
        color=discord.Color.green()
    )
    embed.add_field(name="🎁 Nyeremény", value=g["prize"], inline=False)
    embed.add_field(name="👥 Résztvevők", value=str(len(g["users"])), inline=True)
    embed.add_field(name="🏆 Nyertes(ek)", value="\n".join(winners), inline=False)

    await g["msg"].edit(embed=embed, view=None)

@bot.tree.command(name="reroll")
@app_commands.checks.has_permissions(administrator=True)
async def reroll(i: discord.Interaction, giveaway_id: str):
    gid = int(giveaway_id)
    g = giveaways.get(gid)
    if not g:
        return await i.response.send_message("❌ Hibás ID", ephemeral=True)

    users = list(g["users"])
    winners = random.sample(users, min(len(users), g["winners"]))
    winners = [f"<@{u}>" for u in winners]

    embed = discord.Embed(
        title="🔄 Reroll",
        description="\n".join(winners),
        color=discord.Color.orange()
    )

    await i.channel.send(embed=embed)
    await i.response.send_message("✅ Reroll kész", ephemeral=True)

# ================= START =================

bot.run(TOKEN)
