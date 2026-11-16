
import os, json, random, asyncio, time, datetime
import discord
from discord.ext import commands, tasks
from discord import app_commands

TOKEN = os.getenv("TOKEN")
DATA_FILE = "data.json"

DEFAULT_CONFIG = {
    "embed_color": 0xe66cb6,
    "server_name": "[SERVER_NAME]",
    "welcome_image": "[WELCOME_IMAGE_URL]",
    "rules_text": "[RULES_TEXT]",
    "welcome_message": "Merhba bik f [SERVER_NAME]! 9ra rules o bda l voyage dyalek.",
    "xp_min": 5, "xp_max": 15, "voice_xp": 50,
    "daily_min": 100, "daily_max": 300, "daily_amount": 200,
    "work_cooldown": 60, "rob_cooldown": 300, "gamble_min": 10, "gamble_max": 5000,
    "level_channel": None, "welcome_channel": None, "rules_channel": None,
    "log_channel": None, "suggest_channel": None, "staff_channel": None,
    "voice_channel": None, "counting_channel": None, "starboard_channel": None,
    "level_roles": {"5": "Active", "10": "VIP", "20": "Legend", "30": "Mythic"},
    "shop": {"VIP": 5000, "Legend": 15000, "Color": 2000, "XPBoost": 3000, "Shield": 2500},
    "automod": True, "anti_invite": True, "anti_spam": True, "anti_badwords": True,
    "badwords": ["badword1"],
    "voice_247": False,
}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except: pass
    return {"config": DEFAULT_CONFIG.copy(), "users": {}, "afk": {}, "reminders": [], "tickets": {}, "custom": {}, "birthdays": {}, "warnings": {}, "counting": {"last": 0, "last_user": None}, "giveaways": {}}

def save_data():
    try:
        with open(DATA_FILE, "w") as f: json.dump(DB, f, indent=2)
    except: pass

DB = load_data()
CONFIG = DB["config"]
for k, v in DEFAULT_CONFIG.items():
    if k not in CONFIG: CONFIG[k] = v

def get_user(uid):
    uid = str(uid)
    if uid not in DB["users"]:
        DB["users"][uid] = {"xp": 0, "level": 1, "wallet": 0, "bank": 0, "streak": 0, "last_daily": "", "last_work": 0, "boost_until": 0, "shield_until": 0, "bio": "", "color": None, "achievements": [], "quests_done": [], "birthday": ""}
    return DB["users"][uid]

def need_xp(level):
    return 100 + level * 40

def emb(title, desc, color=None):
    e = discord.Embed(title=title, description=desc, color=color or CONFIG.get("embed_color", 0xe66cb6), timestamp=datetime.datetime.now(datetime.timezone.utc))
    e.set_footer(text=CONFIG.get("server_name", "Server") + " | BOT MAX")
    return e

def is_owner(interaction):
    return interaction.user.id == interaction.guild.owner_id

async def safe_send(interaction, embed, ephemeral=False):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    except:
        try: await interaction.channel.send(embed=embed)
        except: pass

async def log_event(guild, text):
    try:
        cid = CONFIG.get("log_channel")
        if not cid: return
        ch = guild.get_channel(int(cid))
        if ch: await ch.send(embed=emb("Log", text))
    except: pass

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Sync error: {e}")
    if not voice_xp_loop.is_running(): voice_xp_loop.start()
    if not reminder_loop.is_running(): reminder_loop.start()

@tasks.loop(seconds=60)
async def voice_xp_loop():
    try:
        for guild in bot.guilds:
            for vc in guild.voice_channels:
                for m in vc.members:
                    if m.bot: continue
                    u = get_user(m.id)
                    mult = 2 if time.time() < u.get("boost_until", 0) else 1
                    u["xp"] += CONFIG.get("voice_xp", 50) * mult
                    await check_level(guild, m, u)
        save_data()
    except: pass

@tasks.loop(seconds=30)
async def reminder_loop():
    try:
        now = time.time()
        keep = []
        for r in DB.get("reminders", []):
            if r["at"] <= now:
                try:
                    u = await bot.fetch_user(int(r["user"]))
                    await u.send(embed=emb("Reminder", r["text"]))
                except: pass
            else: keep.append(r)
        DB["reminders"] = keep
    except: pass

async def check_level(guild, member, u):
    while u["xp"] >= need_xp(u["level"]):
        u["xp"] -= need_xp(u["level"])
        u["level"] += 1
        lvl = str(u["level"])
        if lvl in CONFIG.get("level_roles", {}):
            role_name = CONFIG["level_roles"][lvl]
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                try:
                    for old in CONFIG["level_roles"].values():
                        r2 = discord.utils.get(guild.roles, name=old)
                        if r2 and r2 in member.roles: await member.remove_roles(r2)
                    await member.add_roles(role)
                except: pass
        try:
            cid = CONFIG.get("level_channel")
            ch = guild.get_channel(int(cid)) if cid else None
            target = ch or guild.system_channel
            if target:
                e = emb("LEVEL UP!", f"Mabrouk {member.mention}! Wslti l level **{u['level']}**")
                e.set_thumbnail(url=member.display_avatar.url)
                await target.send(embed=e)
            await member.send(embed=emb("Level Up!", f"Mabrouk! Wslti l level {u['level']} f {guild.name}"))
        except: pass
        await log_event(guild, f"Level up: {member} -> {u['level']}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    u = get_user(message.author.id)
    # AFK
    if str(message.author.id) in DB["afk"]:
        del DB["afk"][str(message.author.id)]
        await message.channel.send(embed=emb("Welcome Back", f"{message.author.mention} rje3, mabrouk rjou3ek!"))
    for m in message.mentions:
        if str(m.id) in DB["afk"]:
            await message.channel.send(embed=emb("AFK", f"{m.display_name} AFK: {DB['afk'][str(m.id)]}"))
    # Counting
    if CONFIG.get("counting_channel") and message.channel.id == int(CONFIG["counting_channel"]):
        try:
            n = int(message.content.strip())
            if n == DB["counting"]["last"] + 1 and str(message.author.id) != DB["counting"]["last_user"]:
                DB["counting"]["last"] = n; DB["counting"]["last_user"] = str(message.author.id)
                await message.add_reaction("✅")
            else:
                await message.add_reaction("❌")
        except: pass
    # Automod invite
    if CONFIG.get("anti_invite") and "discord.gg" in message.content.lower() and not message.author.guild_permissions.administrator:
        try: await message.delete()
        except: pass
        await message.channel.send(embed=emb("Automod", f"{message.author.mention} links mamnou3in hna!"))
    # Anti spam simple
    # XP - NO cooldown
    mult = 2 if time.time() < u.get("boost_until", 0) else 1
    u["xp"] += random.randint(CONFIG.get("xp_min", 5), CONFIG.get("xp_max", 15)) * mult
    await check_level(message.guild, message.author, u)
    save_data()

@bot.event
async def on_member_join(member):
    try:
        role = discord.utils.get(member.guild.roles, name="Member")
        if role: await member.add_roles(role)
    except: pass
    try: await member.send(embed=emb("Merhba Bik!", CONFIG.get("welcome_message", "") + "\n\nRules: " + CONFIG.get("rules_text", "")))
    except: pass
    await log_event(member.guild, f"Join: {member.mention}")
    cid = CONFIG.get("welcome_channel")
    if cid:
        ch = member.guild.get_channel(int(cid))
        if ch:
            e = emb(f"Merhba {member.display_name}!", CONFIG.get("welcome_message", ""))
            e.set_thumbnail(url=member.display_avatar.url)
            if CONFIG.get("welcome_image") and "http" in CONFIG["welcome_image"]: e.set_image(url=CONFIG["welcome_image"])
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Rules", url="https://discord.com"))
            view.add_item(discord.ui.Button(label="Get Started", custom_id="start", style=discord.ButtonStyle.primary))
            await ch.send(embed=e, view=view)

@bot.event
async def on_member_remove(member):
    await log_event(member.guild, f"Leave: {member}")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel and CONFIG.get("voice_247") and CONFIG.get("voice_channel"):
        await asyncio.sleep(3)
        try:
            ch = member.guild.get_channel(int(CONFIG["voice_channel"]))
            if ch: await ch.connect(self_deaf=True)
        except: pass

# ---------- HELPERS FOR MOD ----------
def can_mod(interaction, target):
    if target.id == interaction.guild.owner_id: return False
    if interaction.user.top_role <= target.top_role and interaction.user.id != interaction.guild.owner_id: return False
    if interaction.guild.me.top_role <= target.top_role: return False
    return True

# ========== GENERAL ==========
@bot.tree.command(name="ping", description="chof ping dyal bot")
async def ping(interaction: discord.Interaction):
    await safe_send(interaction, emb("Ping", f"Pong! {round(bot.latency*1000)}ms"))

@bot.tree.command(name="help", description="chof ga3 les commandes li kaynin")
@app_commands.describe(category="khtar category")
@app_commands.choices(category=[app_commands.Choice(name=x, value=x) for x in ["3ama","Flous","Al3ab","Idara","Voice","Owner"]])
async def help_cmd(interaction: discord.Interaction, category: str = None):
    cats = {
        "3ama": "/profile /rank /top /avatar /banner /userinfo /serverinfo /afk /suggest /report /birthday /translate /weather /ask /lyrics /nowplaying",
        "Flous": "/daily /balance /deposit /withdraw /transfer /gamble /work /rob /shop /buy /inventory /use /dailyquest /achievement",
        "Al3ab": "/8ball /rps /coinflip /dice /slot /truth /dare /joke /meme /ship /hug /quiz /giveaway /poll /counting_setup",
        "Idara": "/kick /ban /unban /timeout /warn /warnings /clear /lock /unlock /slowmode /ticket /announce /automod /reactionrole /starboard",
        "Voice": "/voice_setup /join /leave /music_play /music_stop /music_queue",
        "Owner": "/setup /config /set_xp_rate /set_voice_xp /set_level_roles /set_welcome_message /set_rules /set_embed_color /set_daily_amount /addxp /setlevel /send /shop_add /shop_remove /custom_command",
    }
    if category: desc = f"**{category}**\n{cats.get(category,'')}"
    else: desc = "\n\n".join([f"**{k}**\n{v}" for k,v in cats.items()])
    await safe_send(interaction, emb("Help - BOT MAX", desc))

@bot.tree.command(name="profile", description="chof profile dyalek wla dyal chi wahed")
async def profile(interaction: discord.Interaction, member: discord.Member = None):
    m = member or interaction.user
    u = get_user(m.id)
    e = emb(f"Profile - {m.display_name}", f"Bio: {u.get('bio','-')}\nLevel: {u['level']} | XP: {u['xp']}/{need_xp(u['level'])}\nWallet: {u['wallet']} | Bank: {u['bank']}\nStreak: {u.get('streak',0)} | Birthday: {u.get('birthday','-')}")
    e.set_thumbnail(url=m.display_avatar.url)
    await safe_send(interaction, e)

@bot.tree.command(name="rank", description="chof rank dyalek")
async def rank_cmd(interaction: discord.Interaction):
    u = get_user(interaction.user.id)
    sorted_users = sorted(DB["users"].items(), key=lambda x: x[1].get("level",1), reverse=True)
    pos = next((i+1 for i,(k,v) in enumerate(sorted_users) if k==str(interaction.user.id)), 0)
    bar = "█" * int(u["xp"]/need_xp(u["level"])*10) + "░" * (10-int(u["xp"]/need_xp(u["level"])*10))
    await safe_send(interaction, emb("Rank", f"{interaction.user.mention} Rank #{pos}\nLevel {u['level']} | {u['xp']}/{need_xp(u['level'])} XP\n[{bar}]"))

@bot.tree.command(name="top", description="chof top members")
@app_commands.describe(type="chno bghiti", limit="chhal")
@app_commands.choices(type=[app_commands.Choice(name=x, value=x) for x in ["level","flous","xp","warnings"]], limit=[app_commands.Choice(name=str(x), value=x) for x in [5,10,20]])
async def top_cmd(interaction: discord.Interaction, type: str = "level", limit: int = 10):
    if type=="flous": data = sorted(DB["users"].items(), key=lambda x: x[1].get("wallet",0)+x[1].get("bank",0), reverse=True)
    elif type=="warnings": data = sorted(DB.get("warnings",{}).items(), key=lambda x: len(x[1]), reverse=True)
    else: data = sorted(DB["users"].items(), key=lambda x: x[1].get("level",1), reverse=True)
    lines=[]
    for i,(uid,ud) in enumerate(data[:limit],1):
        if type=="flous": lines.append(f"{i}. <@{uid}> - {ud.get('wallet',0)+ud.get('bank',0)} flous")
        elif type=="warnings": lines.append(f"{i}. <@{uid}> - {len(ud)} warns")
        else: lines.append(f"{i}. <@{uid}> - Level {ud.get('level',1)}")
    await safe_send(interaction, emb(f"Top - {type}", "\n".join(lines) or "Makayn 7ta wahed"))

@bot.tree.command(name="avatar", description="chof avatar")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    m = member or interaction.user
    e = emb(f"Avatar - {m.display_name}", ""); e.set_image(url=m.display_avatar.url)
    await safe_send(interaction, e)

@bot.tree.command(name="banner", description="chof banner")
async def banner(interaction: discord.Interaction, member: discord.Member = None):
    m = member or interaction.user
    await safe_send(interaction, emb("Banner", f"{m.mention} banner: {m.banner.url if m.banner else 'Makaynch'}"))

@bot.tree.command(name="userinfo", description="ma3loumat 3la member")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    m = member or interaction.user
    await safe_send(interaction, emb(f"Userinfo - {m.display_name}", f"ID: {m.id}\nDkhel: {m.joined_at}\nRoles: {', '.join([r.name for r in m.roles[1:]]) or 'Aucun'}"))

@bot.tree.command(name="serverinfo", description="ma3loumat 3la server")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    await safe_send(interaction, emb(f"Server - {g.name}", f"Members: {g.member_count}\nOnline: {sum(1 for m in g.members if m.status!=discord.Status.offline)}\nChannels: {len(g.channels)} | Roles: {len(g.roles)}\nOwner: {g.owner}"))

@bot.tree.command(name="dashboard", description="chof summary dyal server")
async def dashboard(interaction: discord.Interaction):
    g = interaction.guild
    top_lvl = sorted(DB["users"].items(), key=lambda x: x[1].get("level",1), reverse=True)[:3]
    voice_count = sum(len(vc.members) for vc in g.voice_channels)
    top_txt = ', '.join([f'<@{k}> L{v.get("level",1)}' for k,v in top_lvl])
    await safe_send(interaction, emb("Dashboard", f"Members: {g.member_count} | Voice: {voice_count} | Tickets: {len(DB.get('tickets',{}))}\nTop Levels: {top_txt}"))

@bot.tree.command(name="afk", description="dir rassek AFK")
async def afk_cmd(interaction: discord.Interaction, reason: str = "AFK"):
    DB["afk"][str(interaction.user.id)] = reason; save_data()
    await safe_send(interaction, emb("AFK", f"{interaction.user.mention} AFK: {reason}"))

@bot.tree.command(name="suggest", description="sifet suggestion")
async def suggest(interaction: discord.Interaction, idea: str):
    cid = CONFIG.get("suggest_channel")
    ch = interaction.guild.get_channel(int(cid)) if cid else interaction.channel
    e = emb("Suggestion Jadida", f"Men: {interaction.user.mention}\n{idea}")
    msg = await ch.send(embed=e); await msg.add_reaction("👍"); await msg.add_reaction("👎")
    await safe_send(interaction, emb("Done", "Suggestion tsiftat!"), ephemeral=True)

@bot.tree.command(name="report", description="reporti chi wahed")
async def report(interaction: discord.Interaction, member: discord.Member, reason: str):
    await log_event(interaction.guild, f"Report: {member} by {interaction.user} - {reason}")
    await safe_send(interaction, emb("Report", "Report tsift l staff, chokran!"), ephemeral=True)

@bot.tree.command(name="remind", description="dir reminder")
async def remind(interaction: discord.Interaction, minutes: int, text: str):
    DB["reminders"].append({"user": str(interaction.user.id), "at": time.time()+minutes*60, "text": text}); save_data()
    await safe_send(interaction, emb("Reminder", f"Ghadi nfakrek f {minutes} min: {text}"), ephemeral=True)

@bot.tree.command(name="birthday", description="set birthday dyalek")
async def birthday(interaction: discord.Interaction, date: str):
    u = get_user(interaction.user.id); u["birthday"]=date; save_data()
    await safe_send(interaction, emb("Birthday", f"Birthday tsajel: {date} - Ghadi n7taflo bik!"))

@bot.tree.command(name="profile_custom", description="customizi profile dyalek")
async def profile_custom(interaction: discord.Interaction, bio: str = None, color: str = None):
    u = get_user(interaction.user.id)
    if bio: u["bio"]=bio
    if color: u["color"]=color
    save_data(); await safe_send(interaction, emb("Profile", "Profile tbedel!"))

@bot.tree.command(name="weather", description="chof ta9s")
async def weather(interaction: discord.Interaction, city: str):
    await safe_send(interaction, emb(f"Weather - {city}", "Chof wttr.in wla weather.com l ta9s live. Ex: Casablanca 22C, sunny."))

@bot.tree.command(name="ask", description="swel bot")
async def ask_cmd(interaction: discord.Interaction, question: str):
    answers = ["Iyeh bzaf!", "La, ma3ndich fikra", "Momkin, 3lach la?", "100% oui!", "Jarreb o chof"]
    await safe_send(interaction, emb("Ask", f"Q: {question}\nA: {random.choice(answers)}"))

# ========== ECONOMY ==========
@bot.tree.command(name="daily", description="khod daily reward dyalek")
async def daily(interaction: discord.Interaction):
    u = get_user(interaction.user.id)
    today = datetime.date.today().isoformat()
    if u.get("last_daily")==today:
        await safe_send(interaction, emb("Daily", "Déja khditi daily dyal lyoum! Rje3 ghda."), ephemeral=True); return
    yesterday = (datetime.date.today()-datetime.timedelta(days=1)).isoformat()
    u["streak"] = u.get("streak",0)+1 if u.get("last_daily")==yesterday else 1
    reward = random.randint(CONFIG.get("daily_min",100), CONFIG.get("daily_max",300)) + u["streak"]*20
    u["wallet"] += reward; u["last_daily"]=today; save_data()
    await safe_send(interaction, emb("Daily", f"Mabrouk! Khditi {reward} flous! Streak: {u['streak']}"))

@bot.tree.command(name="balance", description="chof floussek")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    m = member or interaction.user; u = get_user(m.id)
    await safe_send(interaction, emb("Balance", f"{m.mention}\nWallet: {u['wallet']} | Bank: {u['bank']} | Total: {u['wallet']+u['bank']}"))

@bot.tree.command(name="deposit", description="7et flous f bank")
async def deposit(interaction: discord.Interaction, amount: int):
    u = get_user(interaction.user.id)
    if amount<=0 or amount>u["wallet"]:
        await safe_send(interaction, emb("Error", "Ma3ndekch had flous!"), ephemeral=True); return
    u["wallet"]-=amount; u["bank"]+=amount; save_data()
    await safe_send(interaction, emb("Deposit", f"7titi {amount} f bank!"))

@bot.tree.command(name="withdraw", description="khod flous men bank")
async def withdraw(interaction: discord.Interaction, amount: int):
    u = get_user(interaction.user.id)
    if amount<=0 or amount>u["bank"]:
        await safe_send(interaction, emb("Error", "Ma3ndekch had flous f bank!"), ephemeral=True); return
    u["bank"]-=amount; u["wallet"]+=amount; save_data()
    await safe_send(interaction, emb("Withdraw", f"Khditi {amount} men bank!"))

@bot.tree.command(name="transfer", description="sifet flous l chi wahed")
async def transfer(interaction: discord.Interaction, member: discord.Member, amount: int):
    u = get_user(interaction.user.id)
    if amount<=0 or amount>u["wallet"]:
        await safe_send(interaction, emb("Error", "Ma3ndekch had flous!"), ephemeral=True); return
    u["wallet"]-=amount; get_user(member.id)["wallet"]+=amount; save_data()
    await safe_send(interaction, emb("Transfer", f"Sifeti {amount} l {member.mention}"))

@bot.tree.command(name="gamble", description="l3eb gamble")
@app_commands.describe(game="khtar game", amount="chhal", pick="pick dyalek l roulette/coinflip")
@app_commands.choices(game=[app_commands.Choice(name=x, value=x) for x in ["coinflip","dice","slot","roulette"]])
async def gamble(interaction: discord.Interaction, game: str, amount: int, pick: str = None):
    u = get_user(interaction.user.id)
    if amount < CONFIG.get("gamble_min",10) or amount > CONFIG.get("gamble_max",5000) or amount>u["wallet"]:
        await safe_send(interaction, emb("Error", "Montant ghalet wla ma3ndekch flous!"), ephemeral=True); return
    win=False; mult=2
    if game=="coinflip":
        res = random.choice(["heads","tails"]); win = (pick==res) if pick else random.random()<0.5
    elif game=="dice":
        r=random.randint(1,6); win=r>=4
    elif game=="slot":
        s=[random.choice(["🍒","🍋","⭐","💎"]) for _ in range(3)]; win=len(set(s))==1; mult=5
    elif game=="roulette":
        r=random.randint(0,36); win=str(r)==str(pick) if pick else r%2==0; mult=3
    if win: u["wallet"]+=amount*(mult-1); msg=f"Rbe7ti {amount*(mult-1)}!"
    else: u["wallet"]-=amount; msg=f"Khsarti {amount}..."
    save_data(); await safe_send(interaction, emb("Gamble - "+game, msg))

@bot.tree.command(name="work", description="khdem o rbe7 flous")
@app_commands.choices(job=[app_commands.Choice(name=x, value=x) for x in ["police","doctor","teacher","gamer","hacker","streamer"]])
async def work(interaction: discord.Interaction, job: str):
    u = get_user(interaction.user.id)
    if time.time()-u.get("last_work",0) < CONFIG.get("work_cooldown",60):
        await safe_send(interaction, emb("Work", "Tsena chwiya 3ad khdem 3awtani!"), ephemeral=True); return
    pay = random.randint(50,250); u["wallet"]+=pay; u["last_work"]=time.time(); save_data()
    await safe_send(interaction, emb("Work", f"Khdemti b7al {job} o rbe7ti {pay} flous!"))

@bot.tree.command(name="rob", description="sre9 chi wahed")
async def rob(interaction: discord.Interaction, member: discord.Member):
    u = get_user(interaction.user.id); t = get_user(member.id)
    if time.time() < t.get("shield_until",0):
        await safe_send(interaction, emb("Rob", "Hada 3ndo Shield! Ma t9darch tsr9o."), ephemeral=True); return
    if t["wallet"]<=0:
        await safe_send(interaction, emb("Rob", "Hada ma3ndo walo!"), ephemeral=True); return
    stolen = random.randint(10, min(200, t["wallet"])); t["wallet"]-=stolen; u["wallet"]+=stolen; save_data()
    await safe_send(interaction, emb("Rob", f"Sr9ti {stolen} men {member.mention}!"))

@bot.tree.command(name="shop", description="chof shop")
async def shop(interaction: discord.Interaction):
    lines = [f"{k} - {v} flous" for k,v in CONFIG.get("shop",{}).items()]
    await safe_send(interaction, emb("Shop", "\n".join(lines)))

@bot.tree.command(name="buy", description="chri item men shop")
async def buy(interaction: discord.Interaction, item: str):
    u = get_user(interaction.user.id); shop = CONFIG.get("shop",{})
    if item not in shop:
        await safe_send(interaction, emb("Error", "Hada item makaynch!"), ephemeral=True); return
    price = shop[item]
    if u["wallet"]<price:
        await safe_send(interaction, emb("Error", "Ma3ndekch flous kafi!"), ephemeral=True); return
    u["wallet"]-=price
    if item=="XPBoost": u["boost_until"]=time.time()+3600
    elif item=="Shield": u["shield_until"]=time.time()+3600
    else:
        role = discord.utils.get(interaction.guild.roles, name=item)
        if role:
            try: await interaction.user.add_roles(role)
            except: pass
    save_data(); await safe_send(interaction, emb("Shop", f"Chriti {item} b {price}! Mabrouk!"))

@bot.tree.command(name="inventory", description="chof inventory dyalek")
async def inventory(interaction: discord.Interaction):
    u = get_user(interaction.user.id)
    boost = "ON" if time.time()<u.get("boost_until",0) else "OFF"
    shield = "ON" if time.time()<u.get("shield_until",0) else "OFF"
    await safe_send(interaction, emb("Inventory", f"XPBoost: {boost} | Shield: {shield}"))

@bot.tree.command(name="use", description="sta3mel item")
async def use_cmd(interaction: discord.Interaction, item: str):
    await safe_send(interaction, emb("Use", f"Sta3melti {item}!"))

@bot.tree.command(name="dailyquest", description="chof daily quests")
async def dailyquest(interaction: discord.Interaction):
    await safe_send(interaction, emb("Daily Quest", "1. Sifet 10 messages - 100 flous\n2. Dkhel voice 5 min - 150 flous\n3. Rbe7 gamble - 200 flous"))

@bot.tree.command(name="achievement", description="chof achievements dyalek")
async def achievement(interaction: discord.Interaction):
    u = get_user(interaction.user.id)
    await safe_send(interaction, emb("Achievements", ", ".join(u.get("achievements",[])) or "Mazal ma3ndekch achievements. Bda tl3eb!"))

@bot.tree.command(name="shop_add", description="zid item l shop - owner")
async def shop_add(interaction: discord.Interaction, item: str, price: int):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["shop"][item]=price; save_data()
    await safe_send(interaction, emb("Shop", f"Zedna {item} b {price}"))

@bot.tree.command(name="shop_remove", description="7yed item men shop - owner")
async def shop_remove(interaction: discord.Interaction, item: str):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["shop"].pop(item, None); save_data()
    await safe_send(interaction, emb("Shop", f"7yedna {item}"))

# ========== FUN / GAMES ==========
@bot.tree.command(name="8ball", description="swel 8ball")
async def eightball2(interaction: discord.Interaction, question: str):
    await safe_send(interaction, emb("8Ball", f"Q: {question}\nA: {random.choice(['Iyeh','La','Momkin','Chof mn ba3d','100%'])}"))

@bot.tree.command(name="rps", description="l3eb pierre papier ciseaux")
@app_commands.choices(choice=[app_commands.Choice(name=x, value=x) for x in ["rock","paper","scissors"]])
async def rps(interaction: discord.Interaction, choice: str):
    b = random.choice(["rock","paper","scissors"])
    win = (choice=="rock" and b=="scissors") or (choice=="paper" and b=="rock") or (choice=="scissors" and b=="paper")
    res = "Rbe7ti!" if win else ("Ta3adol!" if choice==b else "Khsarti!")
    await safe_send(interaction, emb("RPS", f"Nta: {choice} | Bot: {b}\n{res}"))

@bot.tree.command(name="coinflip", description="l3eb coinflip")
async def coinflip(interaction: discord.Interaction):
    await safe_send(interaction, emb("Coinflip", f"Tla3: {random.choice(['Heads','Tails'])}"))

@bot.tree.command(name="dice", description="l3eb dice")
@app_commands.choices(sides=[app_commands.Choice(name=str(x), value=x) for x in [6,12,20]])
async def dice(interaction: discord.Interaction, sides: int = 6):
    await safe_send(interaction, emb("Dice", f"🎲 Tla3: {random.randint(1,sides)}"))

@bot.tree.command(name="slot", description="l3eb slot machine")
async def slot(interaction: discord.Interaction):
    s=[random.choice(["🍒","🍋","⭐","💎","7️⃣"]) for _ in range(3)]
    win = len(set(s))==1
    await safe_send(interaction, emb("Slot", f"{' '.join(s)}\n{'JACKPOT! Mabrouk!' if win else '3awd jarreb!'}"))

@bot.tree.command(name="truth", description="truth question")
async def truth(interaction: discord.Interaction):
    await safe_send(interaction, emb("Truth", random.choice(["Chno akhir 7aja kdabti fiha?", "Chno katkhaf menno?", "Chkoun crush dyalek?"])))

@bot.tree.command(name="dare", description="dare challenge")
async def dare(interaction: discord.Interaction):
    await safe_send(interaction, emb("Dare", random.choice(["Sifet l akhir photo f tel dyalek", "Goul l chi wahed kanbghik", "Bedel smiytek l 1h"])))

@bot.tree.command(name="joke", description="sma3 joke")
async def joke(interaction: discord.Interaction):
    await safe_send(interaction, emb("Joke", random.choice(["3lach l computer mcha l tbib? 7it fih virus!", "Chno gal l wifi l telephone? B9a 9rib mni!"])))

@bot.tree.command(name="meme", description="chof meme")
async def meme(interaction: discord.Interaction):
    await safe_send(interaction, emb("Meme", "Meme lyoum: Ila ma dhaktich, 3awd chofha ghda 😂 (API memes f update jay)"))

@bot.tree.command(name="ship", description="chof compatibility")
async def ship(interaction: discord.Interaction, member1: discord.Member, member2: discord.Member):
    p = random.randint(0,100)
    await safe_send(interaction, emb("Ship", f"{member1.mention} + {member2.mention} = {p}% ❤️\n{'Couple parfait!' if p>80 else 'S7ab safi!'}"))

@bot.tree.command(name="hug", description="3ne9 chi wahed")
@app_commands.describe(action="khtar", member="chkoun")
@app_commands.choices(action=[app_commands.Choice(name=x, value=x) for x in ["hug","kiss","slap","pat"]])
async def hug(interaction: discord.Interaction, member: discord.Member, action: str = "hug"):
    await safe_send(interaction, emb(action.capitalize(), f"{interaction.user.mention} {action} {member.mention}!"))

@bot.tree.command(name="quiz", description="l3eb quiz")
@app_commands.choices(category=[app_commands.Choice(name=x, value=x) for x in ["general","gaming","anime","football"]])
async def quiz(interaction: discord.Interaction, category: str = "general"):
    qs = {"general": ("Chno 3assima dyal Morocco?", "Rabat"), "gaming": ("Chno l3ba fiha Steve?", "Minecraft"), "anime": ("Chkoun Naruto?", "Naruto Uzumaki"), "football": ("Fin l3eb Messi daba?", "Inter Miami")}
    q,a = qs.get(category, qs["general"])
    await safe_send(interaction, emb(f"Quiz - {category}", f"{q}\nJawb f chat! Jawab: {a}"))

@bot.tree.command(name="giveaway", description="bda giveaway")
async def giveaway(interaction: discord.Interaction, prize: str, minutes: int = 5):
    e = emb("Giveaway!", f"Prize: {prize}\nReact 🎉 bach tdkhel! Ysali f {minutes} min")
    msg = await interaction.channel.send(embed=e); await msg.add_reaction("🎉")
    await safe_send(interaction, emb("Giveaway", "Giveaway bda!"), ephemeral=True)

@bot.tree.command(name="poll", description="dir poll")
async def poll(interaction: discord.Interaction, question: str, option1: str, option2: str):
    e = emb("Poll", f"{question}\n1️⃣ {option1}\n2️⃣ {option2}")
    msg = await interaction.channel.send(embed=e); await msg.add_reaction("1️⃣"); await msg.add_reaction("2️⃣")
    await safe_send(interaction, emb("Poll", "Poll tsayeb!"), ephemeral=True)

@bot.tree.command(name="counting_setup", description="setup counting channel")
async def counting_setup(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_owner(interaction) and not interaction.user.guild_permissions.administrator:
        await safe_send(interaction, emb("Error", "Ghir owner/admin!"), ephemeral=True); return
    CONFIG["counting_channel"]=channel.id; save_data()
    await safe_send(interaction, emb("Counting", f"Counting tsayeb f {channel.mention}! Bda b 1"))

# ========== MODERATION ==========
@bot.tree.command(name="kick", description="kick member")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucun"):
    if not interaction.user.guild_permissions.kick_members:
        await safe_send(interaction, emb("Error", "Ma3ndekch permission!"), ephemeral=True); return
    if not can_mod(interaction, member):
        await safe_send(interaction, emb("Error", "Ma t9darch t kicki hada!"), ephemeral=True); return
    try: await member.kick(reason=reason)
    except Exception as e: await safe_send(interaction, emb("Error", str(e)), ephemeral=True); return
    await safe_send(interaction, emb("Kick", f"{member} tkicka. Reason: {reason}")); await log_event(interaction.guild, f"Kick: {member} by {interaction.user} - {reason}")

@bot.tree.command(name="ban", description="ban member")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucun"):
    if not interaction.user.guild_permissions.ban_members:
        await safe_send(interaction, emb("Error", "Ma3ndekch permission!"), ephemeral=True); return
    if not can_mod(interaction, member):
        await safe_send(interaction, emb("Error", "Ma t9darch t bani hada!"), ephemeral=True); return
    try: await member.ban(reason=reason)
    except Exception as e: await safe_send(interaction, emb("Error", str(e)), ephemeral=True); return
    await safe_send(interaction, emb("Ban", f"{member} tbana. Reason: {reason}")); await log_event(interaction.guild, f"Ban: {member} by {interaction.user}")

@bot.tree.command(name="unban", description="unban b ID")
async def unban(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.ban_members:
        await safe_send(interaction, emb("Error", "Ma3ndekch permission!"), ephemeral=True); return
    try: await interaction.guild.unban(discord.Object(id=int(user_id)))
    except Exception as e: await safe_send(interaction, emb("Error", str(e)), ephemeral=True); return
    await safe_send(interaction, emb("Unban", f"Unban {user_id} done!"))

@bot.tree.command(name="timeout", description="timeout member")
async def timeout_cmd(interaction: discord.Interaction, member: discord.Member, minutes: int = 5):
    if not interaction.user.guild_permissions.moderate_members:
        await safe_send(interaction, emb("Error", "Ma3ndekch permission!"), ephemeral=True); return
    try: await member.timeout(datetime.timedelta(minutes=minutes))
    except Exception as e: await safe_send(interaction, emb("Error", str(e)), ephemeral=True); return
    await safe_send(interaction, emb("Timeout", f"{member.mention} timeout {minutes} min"))

@bot.tree.command(name="untimeout", description="7yed timeout")
async def untimeout(interaction: discord.Interaction, member: discord.Member):
    try: await member.timeout(None)
    except Exception as e: await safe_send(interaction, emb("Error", str(e)), ephemeral=True); return
    await safe_send(interaction, emb("Untimeout", f"{member.mention} timeout t7yed!"))

@bot.tree.command(name="warn", description="warn member")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.moderate_members:
        await safe_send(interaction, emb("Error", "Ma3ndekch permission!"), ephemeral=True); return
    DB.setdefault("warnings", {}).setdefault(str(member.id), []).append({"by": str(interaction.user.id), "reason": reason, "at": datetime.datetime.now().isoformat()})
    save_data(); count = len(DB["warnings"][str(member.id)])
    await safe_send(interaction, emb("Warn", f"{member.mention} warn {count}/5 - {reason}"))
    await log_event(interaction.guild, f"Warn: {member} ({count}) - {reason}")
    if count>=5:
        try: await member.ban(reason="5 warns")
        except: pass
    elif count>=3:
        try: await member.kick(reason="3 warns")
        except: pass

@bot.tree.command(name="warnings", description="chof warns dyal member")
async def warnings_cmd(interaction: discord.Interaction, member: discord.Member = None):
    m = member or interaction.user
    ws = DB.get("warnings",{}).get(str(m.id), [])
    lines = [f"{i}. {w['reason']} - by <@{w['by']}>" for i,w in enumerate(ws,1)] or ["Makaynch warns"]
    await safe_send(interaction, emb(f"Warnings - {m.display_name}", "\n".join(lines)))

@bot.tree.command(name="clearwarns", description="msa7 warns")
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        await safe_send(interaction, emb("Error", "Ma3ndekch permission!"), ephemeral=True); return
    DB.get("warnings",{}).pop(str(member.id), None); save_data()
    await safe_send(interaction, emb("Clear Warns", f"Warns dyal {member.mention} tms7o!"))

@bot.tree.command(name="clear", description="msa7 messages")
@app_commands.choices(amount=[app_commands.Choice(name=str(x), value=x) for x in [5,10,20,50,100]])
async def clear(interaction: discord.Interaction, amount: int = 10):
    if not interaction.user.guild_permissions.manage_messages:
        await safe_send(interaction, emb("Error", "Ma3ndekch permission!"), ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(embed=emb("Clear", f"Tms7o {len(deleted)} messages!"), ephemeral=True)

@bot.tree.command(name="lock", description="lock channel")
async def lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    ch = channel or interaction.channel
    await ch.set_permissions(interaction.guild.default_role, send_messages=False)
    await safe_send(interaction, emb("Lock", f"{ch.mention} tlocka!"))

@bot.tree.command(name="unlock", description="unlock channel")
async def unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    ch = channel or interaction.channel
    await ch.set_permissions(interaction.guild.default_role, send_messages=True)
    await safe_send(interaction, emb("Unlock", f"{ch.mention} t7el!"))

@bot.tree.command(name="slowmode", description="dir slowmode")
async def slowmode(interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None):
    ch = channel or interaction.channel
    await ch.edit(slowmode_delay=seconds)
    await safe_send(interaction, emb("Slowmode", f"Slowmode {seconds}s f {ch.mention}"))

@bot.tree.command(name="announce", description="sifet annonce")
async def announce(interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
    if not interaction.user.guild_permissions.administrator:
        await safe_send(interaction, emb("Error", "Ghir admin!"), ephemeral=True); return
    ch = channel or interaction.channel
    await ch.send(embed=emb("Annonce", message))
    await safe_send(interaction, emb("Done", "Annonce tsiftat!"), ephemeral=True)

@bot.tree.command(name="automod", description="config automod")
async def automod(interaction: discord.Interaction, anti_invite: bool = None, anti_spam: bool = None):
    if anti_invite is not None: CONFIG["anti_invite"]=anti_invite
    if anti_spam is not None: CONFIG["anti_spam"]=anti_spam
    save_data(); await safe_send(interaction, emb("Automod", f"Anti-invite: {CONFIG['anti_invite']} | Anti-spam: {CONFIG['anti_spam']}"))

@bot.tree.command(name="reactionrole", description="creer reaction role")
async def reactionrole(interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
    await safe_send(interaction, emb("Reaction Role", f"React {emoji} 3la message {message_id} bach takhod {role.mention}"))

# ========== TICKETS ==========
@bot.tree.command(name="ticket", description="7el ticket")
async def ticket(interaction: discord.Interaction, reason: str):
    guild = interaction.guild
    existing = discord.utils.get(guild.text_channels, name=f"ticket-{interaction.user.name.lower()}")
    if existing:
        await safe_send(interaction, emb("Ticket", f"3ndek ticket déja: {existing.mention}"), ephemeral=True); return
    overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
    ch = await guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites, reason=reason)
    DB.setdefault("tickets", {})[str(ch.id)] = {"user": str(interaction.user.id), "reason": reason}
    save_data()
    e = emb("Ticket", f"Merhba {interaction.user.mention}!\nReason: {reason}\nStaff ghadi yjawbek daba.")
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Close", custom_id="close_ticket", style=discord.ButtonStyle.danger))
    view.add_item(discord.ui.Button(label="Claim", custom_id="claim_ticket", style=discord.ButtonStyle.primary))
    await ch.send(embed=e, view=view)
    await safe_send(interaction, emb("Ticket", f"Ticket t7el: {ch.mention}"), ephemeral=True)

@bot.tree.command(name="close_ticket", description="sed ticket")
async def close_ticket(interaction: discord.Interaction):
    if "ticket-" not in interaction.channel.name:
        await safe_send(interaction, emb("Error", "Hada machi ticket!"), ephemeral=True); return
    await safe_send(interaction, emb("Ticket", "Ticket ghadi ytsed f 5 sec..."))
    await asyncio.sleep(5)
    try: await interaction.channel.delete()
    except: pass

@bot.tree.command(name="add_user", description="zid user l ticket")
async def add_user(interaction: discord.Interaction, member: discord.Member):
    await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
    await safe_send(interaction, emb("Ticket", f"Zedna {member.mention} l ticket!"))

# ========== VOICE / MUSIC ==========
@bot.tree.command(name="voice_setup", description="setup voice 24/7")
async def voice_setup(interaction: discord.Interaction, channel: discord.VoiceChannel, mode: str = "on"):
    if not is_owner(interaction) and not interaction.user.guild_permissions.administrator:
        await safe_send(interaction, emb("Error", "Ghir owner/admin!"), ephemeral=True); return
    CONFIG["voice_channel"]=channel.id; CONFIG["voice_247"]=(mode=="on"); save_data()
    if mode=="on":
        try: await channel.connect(self_deaf=True)
        except: pass
    await safe_send(interaction, emb("Voice 24/7", f"Voice 24/7 {mode} f {channel.name}!"))

@bot.tree.command(name="join", description="bot ydkhel voice")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await safe_send(interaction, emb("Error", "Dkhel chi voice channel lowel!"), ephemeral=True); return
    try: await interaction.user.voice.channel.connect(self_deaf=True)
    except: pass
    await safe_send(interaction, emb("Voice", "Dkhelt voice!"))

@bot.tree.command(name="leave", description="bot ykhrej men voice")
async def leave(interaction: discord.Interaction):
    CONFIG["voice_247"]=False; save_data()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
    await safe_send(interaction, emb("Voice", "Khrjt men voice o 24/7 tfa!"))

@bot.tree.command(name="music_play", description="chaghel music")
async def music_play(interaction: discord.Interaction, song: str):
    await safe_send(interaction, emb("Music", f"Music: {song} - Khassek tinstalli yt-dlp + FFmpeg bach tkhdem kamla. Daba placeholder."))

@bot.tree.command(name="music_stop", description="wa9ef music")
async def music_stop(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
    await safe_send(interaction, emb("Music", "Music w9fat!"))

@bot.tree.command(name="music_queue", description="chof queue dyal music")
async def music_queue(interaction: discord.Interaction):
    await safe_send(interaction, emb("Music Queue", "Queue khawya daba."))

# ========== OWNER / CONFIG ==========
@bot.tree.command(name="setup", description="setup kolchi - owner")
@app_commands.describe(type="chno bghiti tsetupi", channel="khtar channel")
@app_commands.choices(type=[app_commands.Choice(name=x, value=x) for x in ["level_channel","welcome_channel","rules_channel","log","suggest","staff","voice_channel"]])
async def setup(interaction: discord.Interaction, type: str, channel: discord.abc.GuildChannel):
    if not is_owner(interaction) and not interaction.user.guild_permissions.administrator:
        await safe_send(interaction, emb("Error", "Ghir owner/admin!"), ephemeral=True); return
    key = {"level_channel":"level_channel","welcome_channel":"welcome_channel","rules_channel":"rules_channel","log":"log_channel","suggest":"suggest_channel","staff":"staff_channel","voice_channel":"voice_channel"}.get(type, type)
    CONFIG[key]=channel.id; save_data()
    await safe_send(interaction, emb("Setup", f"{type} tsayeb f {channel.mention}!"))

@bot.tree.command(name="config", description="chof ga3 settings")
async def config_cmd(interaction: discord.Interaction):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    c = CONFIG
    desc = f"**Colors & Text**\nColor: {c.get('embed_color')} | Server: {c.get('server_name')}\nWelcome: {c.get('welcome_message')[:60]}\nRules: {str(c.get('rules_text'))[:60]}\n\n**XP**\nText: {c.get('xp_min')}-{c.get('xp_max')} | Voice: {c.get('voice_xp')}/min\n\n**Economy**\nDaily: {c.get('daily_min')}-{c.get('daily_max')} | Work CD: {c.get('work_cooldown')}s | Gamble: {c.get('gamble_min')}-{c.get('gamble_max')}\n\n**Channels**\nLevel: {c.get('level_channel')} | Welcome: {c.get('welcome_channel')} | Rules: {c.get('rules_channel')} | Log: {c.get('log_channel')} | Suggest: {c.get('suggest_channel')}\n\n**Level Roles**\n{c.get('level_roles')}\n\n**Shop**\n{c.get('shop')}"
    await safe_send(interaction, emb("Config", desc), ephemeral=True)

@bot.tree.command(name="set_xp_rate", description="bedel XP per message")
async def set_xp_rate(interaction: discord.Interaction, min_xp: int, max_xp: int):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["xp_min"]=min_xp; CONFIG["xp_max"]=max_xp; save_data()
    await safe_send(interaction, emb("Config", f"XP tbedel: {min_xp}-{max_xp}"))

@bot.tree.command(name="set_voice_xp", description="bedel voice XP")
async def set_voice_xp(interaction: discord.Interaction, xp: int):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["voice_xp"]=xp; save_data(); await safe_send(interaction, emb("Config", f"Voice XP: {xp}/min"))

@bot.tree.command(name="set_level_roles", description="bedel role dyal level")
async def set_level_roles(interaction: discord.Interaction, level: int, role_name: str):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["level_roles"][str(level)]=role_name; save_data()
    await safe_send(interaction, emb("Config", f"Level {level} = {role_name}"))

@bot.tree.command(name="set_welcome_message", description="bedel welcome message")
async def set_welcome_message(interaction: discord.Interaction, message: str):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["welcome_message"]=message; save_data(); await safe_send(interaction, emb("Config", "Welcome message tbedel!"))

@bot.tree.command(name="set_rules", description="bedel rules")
async def set_rules(interaction: discord.Interaction, rules: str):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["rules_text"]=rules; save_data(); await safe_send(interaction, emb("Config", "Rules tbedlo!"))

@bot.tree.command(name="set_embed_color", description="bedel loun dyal embeds")
async def set_embed_color(interaction: discord.Interaction, hex_color: str):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    try: CONFIG["embed_color"]=int(hex_color.replace("#",""), 16)
    except: await safe_send(interaction, emb("Error", "Hex ghalet! Ex: #e66cb6"), ephemeral=True); return
    save_data(); await safe_send(interaction, emb("Config", f"Color tbedel: {hex_color}"))

@bot.tree.command(name="set_daily_amount", description="bedel daily reward")
async def set_daily_amount(interaction: discord.Interaction, min_amount: int, max_amount: int):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["daily_min"]=min_amount; CONFIG["daily_max"]=max_amount; save_data()
    await safe_send(interaction, emb("Config", f"Daily: {min_amount}-{max_amount}"))

@bot.tree.command(name="set_gamble_limits", description="bedel gamble limits")
async def set_gamble_limits(interaction: discord.Interaction, min_amount: int, max_amount: int):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["gamble_min"]=min_amount; CONFIG["gamble_max"]=max_amount; save_data()
    await safe_send(interaction, emb("Config", f"Gamble: {min_amount}-{max_amount}"))

@bot.tree.command(name="set_work_cooldown", description="bedel work cooldown")
async def set_work_cooldown(interaction: discord.Interaction, seconds: int):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    CONFIG["work_cooldown"]=seconds; save_data(); await safe_send(interaction, emb("Config", f"Work cooldown: {seconds}s"))

@bot.tree.command(name="addxp", description="zid XP l chi wahed - owner")
async def addxp(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    u = get_user(member.id); u["xp"]+=amount; await check_level(interaction.guild, member, u); save_data()
    await safe_send(interaction, emb("Add XP", f"Zedna {amount} XP l {member.mention}"))

@bot.tree.command(name="setlevel", description="bedel level - owner")
async def setlevel(interaction: discord.Interaction, member: discord.Member, level: int):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    u = get_user(member.id); u["level"]=level; u["xp"]=0; save_data()
    await safe_send(interaction, emb("Set Level", f"{member.mention} wla Level {level}"))

@bot.tree.command(name="send", description="sifet message custom - owner")
@app_commands.describe(message="message", room="fin", couleur="loun", image_link="lien image", title="titre", ping="ping", button_text="text button", button_link="lien button")
@app_commands.choices(ping=[app_commands.Choice(name=x, value=x) for x in ["none","everyone","here"]])
async def send_cmd(interaction: discord.Interaction, message: str, room: discord.TextChannel = None, couleur: str = None, image_link: str = None, title: str = None, ping: str = "none", button_text: str = None, button_link: str = None):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    ch = room or interaction.channel
    color = CONFIG.get("embed_color", 0xe66cb6)
    if couleur:
        try: color=int(couleur.replace("#",""),16)
        except: pass
    e = discord.Embed(title=title or CONFIG.get("server_name","Server"), description=message, color=color, timestamp=datetime.datetime.now(datetime.timezone.utc))
    e.set_footer(text=CONFIG.get("server_name","Server")+" | BOT MAX")
    if image_link: e.set_image(url=image_link)
    view = None
    if button_text and button_link:
        view = discord.ui.View(); view.add_item(discord.ui.Button(label=button_text, url=button_link))
    content = "@everyone" if ping=="everyone" else ("@here" if ping=="here" else None)
    await ch.send(content=content, embed=e, view=view)
    await safe_send(interaction, emb("Send", "Message tsiftat mra wa7da!"), ephemeral=True)

@bot.tree.command(name="send_welcome", description="sifet welcome embed")
async def send_welcome(interaction: discord.Interaction):
    cid = CONFIG.get("welcome_channel")
    ch = interaction.guild.get_channel(int(cid)) if cid else interaction.channel
    e = emb(f"Merhba f {CONFIG.get('server_name','Server')}!", CONFIG.get("welcome_message",""))
    if CONFIG.get("welcome_image") and "http" in CONFIG["welcome_image"]: e.set_image(url=CONFIG["welcome_image"])
    await ch.send(embed=e)
    await safe_send(interaction, emb("Done", "Welcome tsiftat!"), ephemeral=True)

@bot.tree.command(name="send_rules", description="sifet rules embed")
async def send_rules(interaction: discord.Interaction):
    cid = CONFIG.get("rules_channel")
    ch = interaction.guild.get_channel(int(cid)) if cid else interaction.channel
    await ch.send(embed=emb("Rules", CONFIG.get("rules_text","")))
    await safe_send(interaction, emb("Done", "Rules tsiftou!"), ephemeral=True)

@bot.tree.command(name="custom_command", description="creer custom command")
async def custom_command(interaction: discord.Interaction, name: str, response: str):
    if not is_owner(interaction):
        await safe_send(interaction, emb("Error", "Ghir owner!"), ephemeral=True); return
    DB.setdefault("custom", {})[name]=response; save_data()
    await safe_send(interaction, emb("Custom", f"Custom command /{name} tsayeb!"))

