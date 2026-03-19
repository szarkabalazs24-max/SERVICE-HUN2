import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import datetime
import random
import os
import sqlite3

# --- ADATBÁZIS INICIALIZÁLÁSA (Mentéshez) ---
def init_db():
    conn = sqlite3.connect('giveaway.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS participants 
                      (msg_id TEXT, user_id TEXT, UNIQUE(msg_id, user_id))''')
    conn.commit()
    conn.close()

init_db()

TOKEN = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Fontos: A gombok regisztrálása, hogy újraindítás után is működjenek
        self.add_view(GiveawayButtons())
        await self.tree.sync()
        print(f"Bot bejelentkezve: {self.user}")

bot = MyBot()

# --- GOMBOK ÉS JELENTKEZÉS SZÁMLÁLÓ ---
class GiveawayButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Sosem jár le a gomb

    @ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary, custom_id="join_giveaway_btn")
    async def join(self, interaction: discord.Interaction, button: ui.Button):
        msg_id = str(interaction.message.id)
        user_id = str(interaction.user.id)
        
        conn = sqlite3.connect('giveaway.db')
        c = conn.cursor()
        try:
            # Megpróbáljuk betenni az adatbázisba
            c.execute("INSERT INTO participants VALUES (?, ?)", (msg_id, user_id))
            conn.commit()
            
            # Megszámoljuk az összes jelentkezőt ehhez az üzenethez
            c.execute("SELECT COUNT(*) FROM participants WHERE msg_id = ?", (msg_id,))
            count = c.fetchone()[0]
            conn.close()

            # Frissítjük az Embedet a pontos számmal
            embed = interaction.message.embeds[0]
            # Megkeressük a "Jelentkezők" mezőt (általában az utolsó előtti mező)
            for i, field in enumerate(embed.fields):
                if "Jelentkezők" in field.name:
                    embed.set_field_at(i, name="👤 Jelentkezők", value=f"**{count}** fő", inline=False)
                    break
            
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message("✅ Sikeresen jelentkeztél a játékra!", ephemeral=True)
            
        except sqlite3.IntegrityError:
            conn.close()
            await interaction.response.send_message("❌ Már korábban jelentkeztél erre a játékra!", ephemeral=True)

# --- NYEREMÉNYJÁTÉK MODAL (ŰRLAP) ---
class GiveawayModal(ui.Modal, title='Nyereményjáték Beállítása'):
    duration = ui.TextInput(label='Mennyi ideig tartson? (pl. 10m, 2h, 1d)', placeholder='Pl. 30m', required=True)
    winner_count = ui.TextInput(label='Hány nyertes legyen?', default='1', required=True)
    prize = ui.TextInput(label='Mi a nyeremény?', placeholder='Írd ide a nyereményt!', required=True)
    description = ui.TextInput(label='Leírás', style=discord.TextStyle.paragraph, required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        # Idő kiszámítása
        raw_time = self.duration.value.lower()
        seconds = 0
        if 'm' in raw_time: seconds = int(raw_time.replace('m', '')) * 60
        elif 'h' in raw_time: seconds = int(raw_time.replace('h', '')) * 3600
        elif 'd' in raw_time: seconds = int(raw_time.replace('d', '')) * 86400
        else: seconds = int(raw_time) * 60

        end_time = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)
        
        embed = discord.Embed(title="🎁 NYEREMÉNYJÁTÉK ELINDULT", description=f"Nyeremény: **{self.prize.value}**", color=0x5865F2)
        if self.description.value: 
            embed.add_field(name="📝 Leírás", value=self.description.value, inline=False)
        embed.add_field(name="🏆 Nyertesek", value=f"{self.winner_count.value} fő", inline=True)
        embed.add_field(name="⏳ Hátralévő idő", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
        embed.add_field(name="👤 Jelentkezők", value="**0** fő", inline=False)
        
        # A kért lábléc szöveg
        embed.set_footer(text="Kattints az alábbi gombra a sorsoláson való részvételhez! 🎉")

        await interaction.response.send_message(embed=embed, view=GiveawayButtons())
        
        # Sorsolás várása
        await asyncio.sleep(seconds)
        await self.process_winners(interaction, self.prize.value, self.winner_count.value)

    async def process_winners(self, interaction, prize, count):
        msg = await interaction.original_response()
        conn = sqlite3.connect('giveaway.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (str(msg.id),))
        users = [row[0] for row in c.fetchall()]
        conn.close()

        if users:
            winners = random.sample(users, min(len(users), int(count)))
            mentions = ", ".join([f"<@{w}>" for w in winners])
            await interaction.channel.send(f"🎊 **GRATULÁLUNK!** {mentions} megnyerte a következőt: **{prize}**! 🏆")
        else:
            await interaction.channel.send(f"😢 A(z) **{prize}** nyereményjátéka lezárult, de nem érkezett érvényes jelentkezés.")

# --- PARANCSOK ---
@bot.tree.command(name="nyeremenyjatek", description="Nyereményjáték indítása űrlappal")
async def start_giveaway(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayModal())

@bot.tree.command(name="reroll", description="Új nyertes sorsolása")
async def reroll(interaction: discord.Interaction, uzenet_id: str):
    conn = sqlite3.connect('giveaway.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (uzenet_id,))
    users = [row[0] for row in c.fetchall()]
    conn.close()
    if users:
        await interaction.response.send_message(f"🎲 **Újrasorsolás!** Az új szerencsés nyertes: <@{random.choice(users)}>! 🎉")
    else:
        await interaction.response.send_message("❌ Nem találok jelentkezőket ehhez a játékhoz.", ephemeral=True)

# --- SPAM SZŰRŐ (Admin mentességel) ---
user_violation_count = {}
user_msgs = {}

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or message.author.guild_permissions.manage_messages:
        return

    uid = str(message.author.id)
    now = discord.utils.utcnow()
    user_msgs[uid] = [t for t in user_msgs.get(uid, []) if now - t < datetime.timedelta(seconds=5)]
    user_msgs[uid].append(now)

    if len(user_msgs[uid]) > 4:
        user_violation_count[uid] = user_violation_count.get(uid, 0) + 1
        mins = user_violation_count[uid] * 2
        try:
            await message.delete()
            await message.author.timeout(datetime.timedelta(minutes=mins), reason="Spammelés")
            embed = discord.Embed(title="🛡️ AUTOMATIKUS FIGYELMEZTETÉS", color=discord.Color.red())
            embed.add_field(name="👤 Szabályszegő", value=f"{message.author.mention}", inline=False)
            embed.add_field(name="🚫 Indok", value="**Spammelés**", inline=False)
            embed.add_field(name="⏳ Némítás", value=f"{mins} perc", inline=True)
            embed.set_footer(text="további szabály Szegés esetén a büntetésed 2 perccel növekedni fog!")
            await message.channel.send(embed=embed, delete_after=10)
        except: pass
        user_msgs[uid] = []
        return
    await bot.process_commands(message)

bot.run(TOKEN)
               
