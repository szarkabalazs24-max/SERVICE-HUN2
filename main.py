import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import datetime
import random
import os
import sqlite3
import re

# --- ADATBÁZIS KEZELÉS (Railway-en is maradandó) ---
db = sqlite3.connect('giveaway.db')
cursor = db.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS participants (msg_id TEXT, user_id TEXT)''')
db.commit()

TOKEN = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Spam szűrő adatok
user_spam_count = {}
user_messages = {}

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Bot online: {self.user}")

bot = MyBot()

# --- 1. NYEREMÉNYJÁTÉK MODAL (AZ ŰRLAP) ---

class GiveawayModal(ui.Modal, title='Nyereményjáték Beállítása'):
    duration = ui.TextInput(label='Mennyi ideig tartson? (pl. 10m, 2h, 1d)', placeholder='Add meg az időtartamot', required=True)
    winner_count = ui.TextInput(label='Hány nyertes legyen?', placeholder='Pl. 1, 2, 3', default='1', required=True)
    prize = ui.TextInput(label='Mi a nyeremény?', placeholder='Írd ide a nyereményt!', required=True)
    description = ui.TextInput(label='Leírás', style=discord.TextStyle.paragraph, placeholder='Adj meg egy leírást (opcionális)', required=False, max_length=4000)

    async def on_submit(self, interaction: discord.Interaction):
        # Időtartam kiszámítása
        raw_time = self.duration.value.lower()
        seconds = 0
        if 'm' in raw_time: seconds = int(raw_time.replace('m', '')) * 60
        elif 'h' in raw_time: seconds = int(raw_time.replace('h', '')) * 3600
        elif 'd' in raw_time: seconds = int(raw_time.replace('d', '')) * 86400
        else: 
            await interaction.response.send_message("❌ Hibás időformátum! Használj m, h vagy d betűket.", ephemeral=True)
            return

        end_time = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)
        
        embed = discord.Embed(title="🎁 NYEREMÉNYJÁTÉK", description=f"**{self.prize.value}**", color=discord.Color.blue())
        if self.description.value: embed.add_field(name="Leírás", value=self.description.value, inline=False)
        embed.add_field(name="Nyertesek száma", value=self.winner_count.value, inline=True)
        embed.add_field(name="Vége", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
        embed.add_field(name="Jelentkezők", value="👤 0", inline=False)
        embed.set_footer(text="Kattints a gombra a jelentkezéshez!")

        view = GiveawayButtons()
        await interaction.response.send_message(embed=embed, view=view)
        
        msg = await interaction.original_response()
        await asyncio.sleep(seconds)
        await self.end_giveaway(msg.id, interaction.channel, self.prize.value, int(self.winner_count.value))

    async def end_giveaway(self, msg_id, channel, prize, winners_num):
        cursor.execute("SELECT user_id FROM participants WHERE msg_id = ?", (str(msg_id),))
        users = [int(row[0]) for row in cursor.fetchall()]
        
        if users:
            winners = random.sample(users, min(len(users), winners_num))
            winner_mentions = ", ".join([f"<@{w}>" for w in winners])
            await channel.send(f"🎊 **GRATULÁLUNK!** {winner_mentions} megnyerte: **{prize}**! 🏆")
        else:
            await channel.send(f"😢 A nyereményjáték (**{prize}**) véget ért, de nem volt jelentkező.")

# --- GOMBOK ÉS REROLL ---

class GiveawayButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary, custom_id="join_btn")
    async def join(self, interaction: discord.Interaction, button: ui.Button):
        cursor.execute("SELECT * FROM participants WHERE msg_id = ? AND user_id = ?", (str(interaction.message.id), str(interaction.user.id)))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO participants VALUES (?, ?)", (str(interaction.message.id), str(interaction.user.id)))
            db.commit()
            
            cursor.execute("SELECT COUNT(*) FROM participants WHERE msg_id = ?", (str(interaction.message.id),))
            count = cursor.fetchone()[0]
            
            embed = interaction.message.embeds[0]
            embed.set_field_at(2, name="Jelentkezők", value=f"👤 {count}", inline=False)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message("✅ Sikeresen jelentkeztél!", ephemeral=True)
        else:
            await interaction.response.send_message("Már jelentkeztél! 😎", ephemeral=True)

@bot.tree.command(name="nyeremenyjatek", description="Nyereményjáték indítása űrlappal")
async def start_giveaway(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayModal())

@bot.tree.command(name="reroll", description="Új nyertes sorsolása")
async def reroll(interaction: discord.Interaction, uzenet_id: str):
    cursor.execute("SELECT user_id FROM participants WHERE msg_id = ?", (uzenet_id,))
    users = [int(row[0]) for row in cursor.fetchall()]
    if users:
        nyertes = random.choice(users)
        await interaction.response.send_message(f"🎲 **Újrasorsolva!** Az új nyertes: <@{nyertes}>! 🎉")
    else:
        await interaction.response.send_message("❌ Nem találok jelentkezőket ehhez az ID-hoz.", ephemeral=True)

# --- 2. SPAM SZŰRŐ (VÁLTOZATLAN) ---

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    uid = str(message.author.id)
    now = discord.utils.utcnow()
    user_messages[uid] = [t for t in user_messages.get(uid, []) if now - t < datetime.timedelta(seconds=5)]
    user_messages[uid].append(now)

    if len(user_messages[uid]) > 4:
        user_spam_count[uid] = user_spam_count.get(uid, 0) + 1
        mins = user_spam_count[uid] * 2
        try:
            await message.delete()
            await message.author.timeout(datetime.timedelta(minutes=mins), reason="Spammelés")
            embed = discord.Embed(title="🛡️ AUTOMATIKUS FIGYELMEZTETÉS", color=discord.Color.red(), timestamp=now)
            embed.add_field(name="👤 Szabályszegő", value=f"{message.author.mention}", inline=False)
            embed.add_field(name="🚫 Indok", value="**Spammelés**", inline=False)
            embed.add_field(name="⏳ Némítás", value=f"{mins} perc", inline=True)
            embed.set_footer(text="további szabály Szegés esetén a büntetésed 2 perccel növekedni fog!")
            await message.channel.send(embed=embed, delete_after=10)
        except: pass
        user_messages[uid] = []
        return
    await bot.process_commands(message)

bot.run(TOKEN)
