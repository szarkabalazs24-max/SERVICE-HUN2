import discord
from discord.ext import commands
import asyncio
import datetime
from datetime import timedelta
import os
import random

# --- BEÁLLÍTÁSOK ---
TOKEN = os.getenv('DISCORD_TOKEN') 
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

user_messages = {}     
user_spam_count = {}   
SPAM_LIMIT = 4        
SPAM_SECONDS = 5      

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Bot online: {self.user} | Spam szűrő & Nyereményjáték kész!")

bot = MyBot()

# --- 1. NYEREMÉNYJÁTÉK RÉSZ ---

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.participants = []

    @discord.ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary, custom_id="join_btn")
    async def join_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.participants:
            self.participants.append(interaction.user)
            await interaction.response.send_message("🎉 Sikeresen jelentkeztél!", ephemeral=True)
            
            embed = interaction.message.embeds
            for i, field in enumerate(embed.fields):
                if "Jelentkezők" in field.name:
                    embed.set_field_at(i, name="Jelentkezők", value=f"👤 {len(self.participants)}", inline=False)
            await interaction.message.edit(embed=embed)
        else:
            await interaction.response.send_message("Már jelentkeztél! ✨", ephemeral=True)

    @discord.ui.button(label="Jelentkezés törlése", style=discord.ButtonStyle.danger, custom_id="leave_btn")
    async def leave_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.participants:
            self.participants.remove(interaction.user)
            await interaction.response.send_message("Visszavontad a jelentkezést.", ephemeral=True)
            
            embed = interaction.message.embeds
            for i, field in enumerate(embed.fields):
                if "Jelentkezők" in field.name:
                    embed.set_field_at(i, name="Jelentkezők", value=f"👤 {len(self.participants)}", inline=False)
            await interaction.message.edit(embed=embed)
        else:
            await interaction.response.send_message("Még nem jelentkeztél!", ephemeral=True)

@bot.tree.command(name="nyeremenyjatek", description="Nyereményjáték indítása")
async def nyeremenyjatek(interaction: discord.Interaction, nyeremeny: str, idotartam_perc: int):
    vege = datetime.datetime.now() + datetime.timedelta(minutes=idotartam_perc)
    embed = discord.Embed(title="🎁 NYEREMÉNYJÁTÉK", description=f"**{nyeremeny}**", color=discord.Color.blue())
    embed.add_field(name="Leírás", value="Sok szerencsét mindenkinek! ✨", inline=False)
    embed.add_field(name="Nyertesek száma", value="1", inline=True)
    embed.add_field(name="Időtartam", value=f"{idotartam_perc} perc", inline=True)
    embed.add_field(name="Vége", value=f"🕒 {vege.strftime('%Y-%m-%d %H:%M:%S')}", inline=False)
    embed.add_field(name="Jelentkezők", value="👤 0", inline=False)
    embed.set_footer(text="Kattints a gombra a résztvételhez!")

    view = GiveawayView()
    await interaction.response.send_message(embed=embed, view=view)
    await asyncio.sleep(idotartam_perc * 60)
    
    if view.participants:
        nyertes = random.choice(view.participants)
        await interaction.channel.send(f"🎊 **GRATULÁLUNK!** {nyertes.mention} megnyerte: **{nyeremeny}**! 🏆")
    else:
        await interaction.channel.send("😢 Nem érkezett jelentkezés.")

# --- 2. AUTOMATIKUS FIGYELMEZTETÉS (SPAM SZŰRŐ) ---

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        return

    uid = str(message.author.id)
    now = discord.utils.utcnow()

    # Spam figyelés
    user_messages[uid] = [t for t in user_messages.get(uid, []) if now - t < timedelta(seconds=SPAM_SECONDS)]
    user_messages[uid].append(now)

    if len(user_messages[uid]) > SPAM_LIMIT:
        user_spam_count[uid] = user_spam_count.get(uid, 0) + 1
        timeout_mins = user_spam_count[uid] * 2
        
        try:
            await message.delete()
            await message.author.timeout(timedelta(minutes=timeout_mins), reason="Spammelés")

            # Figyelmeztető Embed
            embed = discord.Embed(
                title="🛡️ AUTOMATIKUS FIGYELMEZTETÉS",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="👤 Szabályszegő", value=f"{message.author.mention} ({message.author})", inline=False)
            embed.add_field(name="🚫 Indok", value="**Spammelés**", inline=False) 
            embed.add_field(name="🔢 Eset", value=f"{user_spam_count[uid]}. alkalom", inline=True)
            embed.add_field(name="⏳ Némítás", value=f"{timeout_mins} perc", inline=True)
            
            # Lábléc
            embed.set_footer(text="további szabály Szegés esetén a büntetésed 2 perccel növekedni fog!")

            warn_msg = await message.channel.send(embed=embed)
            await warn_msg.delete(delay=10)

        except Exception as e:
            print(f"Hiba: {e}")
        
        user_messages[uid] = []
        return

    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(TOKEN)
              
