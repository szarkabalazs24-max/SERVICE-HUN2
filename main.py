import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import datetime
import random
import os
import sqlite3

# --- ADATBÁZIS INICIALIZÁLÁSA ---
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
        self.add_view(GiveawayButtons())
        await self.tree.sync()
        print(f"Bot bejelentkezve: {self.user}")

bot = MyBot()

# --- INTELLIGENS JELENTKEZÉS GOMB (Toggle) ---
class GiveawayButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary, custom_id="toggle_join_btn")
    async def toggle_join(self, interaction: discord.Interaction, button: ui.Button):
        msg_id = str(interaction.message.id)
        user_id = str(interaction.user.id)
        
        conn = sqlite3.connect('giveaway.db')
        c = conn.cursor()
        c.execute("SELECT * FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
        user_exists = c.fetchone()

        if user_exists:
            c.execute("DELETE FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
            status_text = "❌ Eltávolítottalak a nyereményjátékból."
        else:
            c.execute("INSERT INTO participants VALUES (?, ?)", (msg_id, user_id))
            status_text = "✅ Sikeresen jelentkeztél a játékra!"
        
        conn.commit()
        c.execute("SELECT COUNT(*) FROM participants WHERE msg_id = ?", (msg_id,))
        count = c.fetchone()[0]
        conn.close()

        embed = interaction.message.embeds[0]
        for i, field in enumerate(embed.fields):
            if "Jelentkezők" in field.name:
                embed.set_field_at(i, name="👤 Jelentkezők", value=f"**{count}** fő", inline=False)
                break
        
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(status_text, ephemeral=True)

# --- NYEREMÉNYJÁTÉK MODAL (ŰRLAP) ---
class GiveawayModal(ui.Modal, title='Nyereményjáték Beállítása'):
    duration = ui.TextInput(label='Mennyi ideig tartson? (pl. 10m, 2h, 1d)', placeholder='Pl. 30m', required=True)
    winner_count = ui.TextInput(label='Hány nyertes legyen?', default='1', required=True)
    prize = ui.TextInput(label='Mi a nyeremény?', placeholder='Írd ide a nyereményt!', required=True)
    description = ui.TextInput(label='Leírás', style=discord.TextStyle.paragraph, required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        raw_time = self.duration.value.lower()
        seconds = 0
        try:
            if 'm' in raw_time: seconds = int(raw_time.replace('m', '')) * 60
            elif 'h' in raw_time: seconds = int(raw_time.replace('h', '')) * 3600
            elif 'd' in raw_time: seconds = int(raw_time.replace('d', '')) * 86400
            else: seconds = int(raw_time) * 60
        except ValueError:
            return await interaction.response.send_message("❌ Hibás időformátum!", ephemeral=True)

        end_timestamp = int((discord.utils.utcnow() + datetime.timedelta(seconds=seconds)).timestamp())
        
        embed = discord.Embed(title="🎁 NYEREMÉNYJÁTÉK ELINDULT", description=f"Nyeremény: **{self.prize.value}**", color=0x5865F2)
        if self.description.value: 
            embed.add_field(name="📝 Leírás", value=self.description.value, inline=False)
        embed.add_field(name="🏆 Nyertesek", value=f"{self.winner_count.value} fő", inline=True)
        embed.add_field(name="⏳ Hátralévő idő", value=f"<t:{end_timestamp}:R> múlva ér véget", inline=True)
        embed.add_field(name="👤 Jelentkezők", value="**0** fő", inline=False)
        embed.set_footer(text="Kattints a gombra a jelentkezéshez vagy leiratkozáshoz! 🎉")

        view = GiveawayButtons()
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        
        # ID elküldése DM-ben
        try:
            dm_embed = discord.Embed(title="🎫 Nyereményjáték Létrehozva", color=discord.Color.green())
            dm_embed.add_field(name="🆔 Nyereményjáték ID", value=f"`{msg.id}`", inline=False)
            dm_embed.set_footer(text="Ezt az ID-t használd a /reroll parancshoz!")
            await interaction.user.send(embed=dm_embed)
        except:
            await interaction.followup.send(f"⚠️ ID: `{msg.id}` (DM-et nem tudtam küldeni)", ephemeral=True)

        await asyncio.sleep(seconds)
        await self.process_winners(interaction, self.prize.value, self.winner_count.value, msg.id, view)

    async def process_winners(self, interaction, prize, count, msg_id, view):
        conn = sqlite3.connect('giveaway.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (str(msg_id),))
        users = [row[0] for row in c.fetchall()]
        conn.close()

        # Üzenet frissítése: gomb letiltása (szürke lesz)
        for item in view.children:
            item.disabled = True
        
        try:
            msg = await interaction.channel.fetch_message(msg_id)
            old_embed = msg.embeds[0]
            old_embed.title = "🔒 NYEREMÉNYJÁTÉK LEZÁRULT"
            old_embed.color = discord.Color.dark_grey()
            # Idő mező frissítése
            for i, field in enumerate(old_embed.fields):
                if "Hátralévő idő" in field.name:
                    old_embed.set_field_at(i, name="⏳ Állapot", value="Véget ért", inline=True)
            
            await msg.edit(embed=old_embed, view=view)
        except:
            pass

        if users:
            winners = random.sample(users, min(len(users), int(count)))
            mentions = ", ".join([f"<@{w}>" for w in winners])
            await interaction.channel.send(f"🎊 **GRATULÁLUNK!** {mentions} megnyerte a következőt: **{prize}**! 🏆")
        else:
            await interaction.channel.send(f"😢 A(z) **{prize}** sorsolása sikertelen (nem maradt jelentkező).")

# --- PARANCSOK ---
@bot.tree.command(name="nyeremenyjatek")
async def start_giveaway(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayModal())

@bot.tree.command(name="reroll")
async def reroll(interaction: discord.Interaction, uzenet_id: str):
    conn = sqlite3.connect('giveaway.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (uzenet_id,))
    users = [row[0] for row in c.fetchall()]
    conn.close()
    if users:
        await interaction.response.send_message(f"🎲 **Újrasorsolás!** Az új nyertes: <@{random.choice(users)}>! 🎉")
    else:
        await interaction.response.send_message("❌ Nincs jelentkező ehhez az ID-hoz.", ephemeral=True)

# --- SPAM SZŰRŐ ---
user_msgs = {}
user_violation_count = {}

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
