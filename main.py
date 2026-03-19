import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
from datetime import timedelta
import random

# --- ALAPBEÁLLÍTÁSOK ---
TOKEN = 'IDE_ÍRD_A_TOKENEDET'
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

# Spam szűrő változók
user_messages = {}     
user_spam_count = {}   
SPAM_LIMIT = 4        
SPAM_SECONDS = 5      

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Bot elindult | Nyereményjáték & Spam szűrő aktív!")

bot = MyBot()

# --- 1. NYEREMÉNYJÁTÉK (GOMBOS) ---

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.participants = []

    @discord.ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary, custom_id="join_btn")
    async def join_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.participants:
            self.participants.append(interaction.user)
            await interaction.response.send_message("🎉 Sikeresen jelentkeztél!", ephemeral=True)
            
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Jelentkezők":
                    embed.set_field_at(i, name="Jelentkezők", value=f"👤 {len(self.participants)}", inline=False)
            
            await interaction.message.edit(embed=embed)
        else:
            await interaction.response.send_message("Már jelentkeztél! 😎", ephemeral=True)

    @discord.ui.button(label="Jelentkezés törlése", style=discord.ButtonStyle.danger, custom_id="leave_btn")
    async def leave_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.participants:
            self.participants.remove(interaction.user)
            await interaction.response.send_message("Visszavontad a jelentkezést.", ephemeral=True)
            
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Jelentkezők":
                    embed.set_field_at(i, name="Jelentkezők", value=f"👤 {len(self.participants)}", inline=False)
            
            await interaction.message.edit(embed=embed)
        else:
            await interaction.response.send_message("Még nem is jelentkeztél!", ephemeral=True)

@bot.tree.command(name="nyeremenyjatek", description="Nyereményjáték indítása")
async def nyeremenyjatek(interaction: discord.Interaction, nyeremeny: str, idotartam_perc: int):
    vege_idopont = datetime.datetime.now() + datetime.timedelta(minutes=idotartam_perc)
    
    embed = discord.Embed(
        title="🎁 NYEREMÉNYJÁTÉK",
        description=f"**{nyeremeny}**",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="Leírás", value="Sok szerencsét mindenkinek! ✨", inline=False)
    embed.add_field(name="Nyertesek száma", value="1", inline=True)
    embed.add_field(name="Időtartam", value=f"{idotartam_perc} perc", inline=True)
    embed.add_field(name="Vége", value=f"🕒 {vege_idopont.strftime('%Y-%m-%d %H:%M:%S')}", inline=False)
    embed.add_field(name="Jelentkezők", value="👤 0", inline=False)
    embed.set_footer(text="Kattints a gombra a résztvételhez!")

    view = GiveawayView()
    await interaction.response.send_message(embed=embed, view=view)
    
    await asyncio.sleep(idotartam_perc * 60)
    
    if view.participants:
        nyertes = random.choice(view.participants)
        await interaction.channel.send(f"🎊 **GRATULÁLUNK!** {nyertes.mention} megnyerte a következőt: **{nyeremeny}**! 🏆")
    else:
        await interaction.channel.send("😢 A nyereményjáték véget ért, de nem volt jelentkező.")

# --- 2. SPAM SZŰRŐ (LÉPCSŐZETES NÉMÍTÁSSAL) ---

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        return

    user_id = message.author.id
    now = discord.utils.utcnow()

    # Spam figyelés
    if user_id not in user_messages:
        user_messages[user_id] = []
    
    user_messages[user_id].append(now)
    user_messages[user_id] = [t for t in user_messages[user_id] if now - t < timedelta(seconds=SPAM_SECONDS)]

    if len(user_messages[user_id]) > SPAM_LIMIT:
        # Büntetés számolása (+2 perc alkalmanként)
        user_spam_count[user_id] = user_spam_count.get(user_id, 0) + 1
        timeout_minutes = user_spam_count[user_id] * 2
        duration = timedelta(minutes=timeout_minutes)

        try:
            await message.delete()
            await message.author.timeout(duration, reason=f"Spam: {user_spam_count[user_id]}. alkalom")

            # Figyelmeztető Embed
            embed = discord.Embed(
                title="🛡️ AUTOMATA MODERÁCIÓ",
                description=f"Lassíts {message.author.mention}!",
                color=discord.Color.red()
            )
            embed.add_field(name="🚫 Indok", value="Folyamatos spammelés", inline=False)
            embed.add_field(name="🔢 Hányadik eset?", value=f"{user_spam_count[user_id]}.", inline=True)
            embed.add_field(name="⏳ Büntetés", value=f"**{timeout_minutes} perc** némítás", inline=True)
            
            # A kért lábléc:
            embed.set_footer(text="további szabály Szegés esetén a büntetésed 2 perccel növekedni fog!")

            warn_msg = await message.channel.send(embed=embed)
            await warn_msg.delete(delay=10) 

        except Exception as e:
            print(f"Hiba: {e}")

        user_messages[user_id] = []
        return

    await bot.process_commands(message)

bot.run(TOKEN)
      
