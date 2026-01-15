# merged_main_no_db.py
import os
import asyncio
from datetime import datetime
import functools
import json
from typing import List, Dict, Any, Optional, Union

import discord
from discord.ext import commands
from discord import app_commands, ui
from dotenv import load_dotenv

# ================== LOAD ENV ==================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable not set!")

# For instant command registration during development, set TEST_GUILD_ID in env
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")  # optional, string of guild id

# ================== CONSTANTS ==================
BOT_COLOR = discord.Color.from_str("#8fd6ff")

# Channels
AFFILIATES_CHANNEL_ID = 1454888713216852182
ACTION_LOG_CHANNEL = 1459588265769435177  # transcripts and action logs
APPEALS_CHANNEL_ID = 1457992486046793759
SESSION_LOG_CHANNEL_ID = 1454889852054278144
STRIKE_LOG_CHANNEL_ID = 1459588265769435177
WELCOME_CHANNEL_ID = 1459354203909783688
VEHICLE_LOG_CHANNEL_ID = 1456813290381643806

SUPPORT_CHANNEL_ID = 1429227915526017054
MUTE_HINT_CHANNEL_ID = 1429220984988238007

# Ticket system
TICKET_CATEGORY_ID = 1459706908075233331
ticket_counter = 0

# ================== ROLE IDS ==================
ADMIN_ROLE_ID = 1459341992525037835
HIGHCOMMAND_ROLE_ID = 1450600601238114577
OWNERSHIP_ROLE_ID = 1459333438871175200
STAFF_TEAM_ROLE_ID = 1431352511931093052

# Session-related
CIVILIAN_ROLE_ID = 1429222424393683074
PUBLIC_SERVICES_ROLE_ID = 1454875886808596571
EARLY_ACCESS_ROLE_ID = 1454877233226453178

VIP_VEHICLE_ROLE_ID = 1458934685412626454  # Server Booster / High priority

# Suspensions / infractions
INVESTIGATION_ROLE_ID = 1456770631390466239
STAFF_SUSPENSION_ROLE_ID = 1456068646731251866
CIVILIAN_SUSPENSION_ROLE = 1454877236757790802

# Staff strikes
STAFF_STRIKE_1 = 1456068422323667058
STAFF_STRIKE_2 = 1456068533028130920
STAFF_STRIKE_3 = 1459340232389562368

# Staff Blacklist
STAFF_BLACKLIST_ROLE = 1456068586551378174

# Staff roles to remove on termination/suspension
STAFF_ROLE_IDS = {
    1456979405225201695, 1456979449177178113, 1457172806239260703, 1456067970844594388,
    1459343244902269199, 1459343158050558221, 1459343196948533408, 1459342867821629654,
    1459342846644715680, 1450600601238114577, 1456064714462199808, 1459342502627770468,
    1459341992525037835, 1459354770014867619, 1459341896122892420, 1456069337809944628,
    1459331900073185321, 1456069370752012540, 1456980955716649012, 1450600658196496526,
    1431352511931093052
}

# ================== STORAGE (IN-MEMORY) ==================
sessions: Dict[int, Dict[str, Any]] = {}
staff_strikes: Dict[int, int] = {}
civilian_infractions: Dict[int, int] = {}
notes_store: Dict[int, List[Dict[str, Any]]] = {}
history_store: Dict[int, List[Dict[str, Any]]] = {}
appeals_store: Dict[int, List[Dict[str, Any]]] = {}
session_log: Dict[int, Dict[str, Any]] = {}

vehicle_store: Dict[int, List[Dict[str, Any]]] = {}
unregister_uses: Dict[int, int] = {}

PERSISTENCE_FILE = os.getenv("PERSISTENCE_FILE", "vehicle_store.json")

# ================== EMOJIS ==================
CHECKMARK = "<:checkmark:1455689105559130152>"
CHECK_EMOJI = "<:check:1459330182329663645>"
ORANGE = "<:bluearrow:1459329920949030932>"
BLUE = "<:blue_alarm:1455688665203478651>"
HEART = "<:hearts:1459330385178656909>"
WORK = "<:work:1455689142255222987>"
DOT = "<:dot:1459330276256776427>"
BLUEARROW = "<:bluearrow:1459329920949030932>"
PIN = "<:pin:1459330500824006891>"

# ================== AUTOCOMPLETE OPTIONS ==================
FRP_OPTIONS = ["60", "65", "75", "90"]
LEO_OPTIONS = ["Active", "Inactive"]
AORP_OPTIONS = ["Greenville", "Highway", "Brookmere", "Horton"]
HOUSE_OPTIONS = ["Enabled", "Disabled"]
PEACETIME_OPTIONS = ["Normal", "Strict", "Off"]

# ================== INTENTS & BOT ==================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ================== HELPERS ==================
def save_persistence():
    if not PERSISTENCE_FILE:
        return
    try:
        data = {"vehicle_store": vehicle_store, "unregister_uses": unregister_uses}
        with open(PERSISTENCE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)
    except Exception:
        pass

def load_persistence():
    if not PERSISTENCE_FILE:
        return
    try:
        if not os.path.exists(PERSISTENCE_FILE):
            return
        with open(PERSISTENCE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        vs = data.get("vehicle_store", {})
        for k, v in vs.items():
            vehicle_store[int(k)] = v
        uu = data.get("unregister_uses", {})
        for k, v in uu.items():
            unregister_uses[int(k)] = v
    except Exception:
        pass

load_persistence()

def run_blocking(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

# Permission helpers
def has_role(user: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in user.roles)

def is_staff(interaction: discord.Interaction) -> bool:
    u = interaction.user
    return has_role(u, ADMIN_ROLE_ID) or has_role(u, HIGHCOMMAND_ROLE_ID) or has_role(u, OWNERSHIP_ROLE_ID)

def is_highcommand(interaction: discord.Interaction) -> bool:
    return has_role(interaction.user, HIGHCOMMAND_ROLE_ID)

def is_staffing(interaction: discord.Interaction) -> bool:
    return has_role(interaction.user, STAFF_TEAM_ROLE_ID)

def is_ownership(interaction: discord.Interaction) -> bool:
    return has_role(interaction.user, OWNERSHIP_ROLE_ID)

# Generic helpers
def remove_all_staff_roles(member: discord.Member):
    return [r for r in member.roles if r.id in STAFF_ROLE_IDS]

async def log_action(guild: discord.Guild, embed: discord.Embed):
    channel = guild.get_channel(ACTION_LOG_CHANNEL)
    if channel:
        await channel.send(embed=embed)

def session_info(s: dict) -> str:
    return (
        f"{BLUEARROW}**FRP Speeds:** {s.get('frp', 'N/A')}\n"
        f"{BLUEARROW}**AORP (Area of Roleplay):** {s.get('aorp', 'N/A')}\n"
        f"{BLUEARROW}**Law Enforcement:** {s.get('leo', 'N/A')}\n"
        f"{BLUEARROW}**Public Services:** {s.get('house', 'N/A')}\n"
        f"{BLUEARROW}**Peacetime Status:** {s.get('peacetime', 'N/A')}"
    )

def add_history_entry(user_id: int, entry_type: str, action: str, by_id: int, extra: str = ""):
    history_store.setdefault(user_id, []).append({
        "type": entry_type,
        "action": action,
        "by": by_id,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "extra": extra
    })

async def safe_dm(user: discord.Member, embed: discord.Embed):
    try:
        await user.send(embed=embed)
    except Exception:
        pass

# ================== "DB" FUNCTIONS (IN-MEMORY) ==================
def _insert_vehicle_local(user_id: int, vehicle: dict):
    vehicle_store.setdefault(user_id, []).append({
        "year": vehicle.get("year"),
        "make": vehicle.get("make"),
        "model": vehicle.get("model"),
        "color": vehicle.get("color"),
        "plate": vehicle.get("plate"),
        "state": vehicle.get("state"),
        "usage": vehicle.get("usage"),
        "registered_at": datetime.utcnow().isoformat(timespec="seconds")
    })
    save_persistence()

def _remove_vehicle_by_plate_local(user_id: int, plate: str):
    rows = vehicle_store.get(user_id, [])
    new_rows = [r for r in rows if str(r.get("plate", "")).lower() != plate.lower()]
    vehicle_store[user_id] = new_rows
    save_persistence()

def _get_vehicles_local(user_id: int):
    return vehicle_store.get(user_id, [])

async def db_insert_vehicle(user_id: int, vehicle: dict):
    await run_blocking(_insert_vehicle_local, user_id, vehicle)

async def db_remove_vehicle_by_plate(user_id: int, plate: str):
    await run_blocking(_remove_vehicle_by_plate_local, user_id, plate)

async def db_get_vehicles(user_id: int):
    rows = await run_blocking(_get_vehicles_local, user_id)
    return rows or []

async def db_log_vehicle_action(user: discord.Member, action_type: str, vehicle: dict, guild: discord.Guild):
    embed = discord.Embed(
        title="🚗 Vehicle Registration Action",
        color=BOT_COLOR,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Action", value=action_type, inline=False)
    embed.add_field(name="Vehicle", value=f"{vehicle.get('year','N/A')} {vehicle.get('make','N/A')} {vehicle.get('model','N/A')}", inline=False)
    embed.add_field(name="Plate / State", value=f"{vehicle.get('plate','N/A')} / {vehicle.get('state','N/A')}", inline=False)
    embed.add_field(name="Usage", value=vehicle.get("usage","N/A"), inline=False)
    await log_vehicle_action(guild, embed)

async def log_vehicle_action(guild: discord.Guild, embed: discord.Embed):
    channel = guild.get_channel(VEHICLE_LOG_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

# ================== VEHICLE HELPERS ==================
def max_vehicle_slots_for(member: discord.Member) -> int:
    if any(r.id == VIP_VEHICLE_ROLE_ID for r in member.roles):
        return 5
    return 2

def remaining_unregister_uses_for(user_id: int, member: discord.Member) -> int:
    if member and any(r.id == VIP_VEHICLE_ROLE_ID for r in member.roles):
        return 9999
    return unregister_uses.get(user_id, 2)

async def refresh_vehicle_cache(user_id: int):
    return await db_get_vehicles(user_id)

# ================== AUTOCOMPLETE HANDLERS ==================
async def frp_ac(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=o, value=o) for o in FRP_OPTIONS if current.lower() in o.lower()][:25]

async def leo_ac(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=o, value=o) for o in LEO_OPTIONS if current.lower() in o.lower()][:25]

async def hc_ac(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=o, value=o) for o in HOUSE_OPTIONS if current.lower() in o.lower()][:25]

async def aorp_ac(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=o, value=o) for o in AORP_OPTIONS if current.lower() in o.lower()][:25]

async def peacetime_ac(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=o, value=o) for o in PEACETIME_OPTIONS if current.lower() in o.lower()][:25]

# ================== EMBED BUILDERS ==================
def build_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="__**HexVille | Server Support**__",
        description=(
            f"> <:announcement:1459329676173639680>  This is your central hub for submitting any type of request, including Civilian Reports, Staff Reports, or Support Tickets for questions or concerns.\n\n"
            "__**Moderation Appeal**__\n\n"
            f"{BLUEARROW} If you believe you were __**falsely moderated by our staff team**__, you may appeal within the \"**Moderation Appeal**\" option.\n\n"
            "__**Civilian Support**__\n\n"
            f"{BLUEARROW} Use the Civilian Support option to share __**any complaints, opinions, suggestions**__, or questions about HexVille operations.\n\n"
            "__**Member Report**__\n\n"
            f"{BLUEARROW} Select the Member Report option to __**report any civilian member**__ who is not complying with HexVille regulations.\n\n"
            "__**Partnership Request**__\n\n"
            f"{BLUEARROW} Select the Partnership Request option to __**make a partnership request**__."
        ),
        color=BOT_COLOR
    )
    return embed

def build_ticket_embed(user: discord.Member, ticket_type: str, priority: str = "Normal") -> discord.Embed:
    return discord.Embed(
        title=f"🎫 {ticket_type}",
        description=(
            f"{BLUEARROW} Hello **{user.display_name}**, thank you for opening a **{ticket_type}**!\n"
            f"{BLUEARROW} Our **Staff Team** will assist you shortly, please be patient.\n"
            f"{BLUEARROW} **If you fail to respond to our ticket within 24 hours, the ticket will be closed.**\n\n"
            f"{PIN} __**Please fill out this format.**__\n"
            "```Username:\nDate:\nQuestion:```"
            f"\n\n{ORANGE}**Priority:** {priority}"
        ),
        color=BOT_COLOR
    )

def build_casefile_embed(user: discord.Member) -> discord.Embed:
    strikes = staff_strikes.get(user.id, 0)
    civ = civilian_infractions.get(user.id, 0)
    notes = notes_store.get(user.id, [])
    history_entries = history_store.get(user.id, [])

    note_text = "None"
    if notes:
        note_text = "".join(f"{ORANGE}{n['timestamp']} — {n['note']}\n" for n in notes[-10:])

    hist_text = "None"
    if history_entries:
        hist_text = "".join(f"{ORANGE}{h['timestamp']} — {h['action']}\n" for h in history_entries[-10:])

    embed = discord.Embed(title=f"📁 Casefile — {user.display_name}", color=BOT_COLOR)
    embed.add_field(name="Staff Strikes", value=str(strikes), inline=False)
    embed.add_field(name="Civilian Infractions", value=str(civ), inline=False)
    embed.add_field(name="Internal Notes", value=note_text, inline=False)
    embed.add_field(name="Recent History", value=hist_text, inline=False)
    return embed

# ================== SESSION COMMANDS (startup/reinvites/release/end) ==================
IMG_STARTUP = "https://cdn.discordapp.com/attachments/1459425676305371186/1459581776736292955/HexVille_5.png"
IMG_SETUP = "https://cdn.discordapp.com/attachments/1459425676305371186/1459581335151837237/session-setup.png"
IMG_EARLY = "https://cdn.discordapp.com/attachments/1459425676305371186/1459581333167935731/earlyaccess-hexville.png"
IMG_RELEASE = "https://cdn.discordapp.com/attachments/1459425676305371186/1459581334455455844/session-release-hexville.png"
IMG_REINVITES = "https://cdn.discordapp.com/attachments/1459425676305371186/1459581334082289825/session-reinvites.png"
IMG_END = "https://cdn.discordapp.com/attachments/1459425676305371186/1459581333599686696/sessionend-hexville.png"

@bot.tree.command(name="startup", description="Begin session startup")
@app_commands.describe(goal="Reactions required to progress")
async def startup(interaction: discord.Interaction, goal: int = 6):
    if not is_staff(interaction):
        return await interaction.response.send_message("Unauthorized.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    session_log[interaction.channel.id] = {"start": datetime.utcnow(), "host": interaction.user.mention, "host_id": interaction.user.id}
    embed = discord.Embed(
        title=f"{HEART} __**HexVille, Session Startup**__",
        description=(
            f"{DOT} A session is **currently being commenced** by **{interaction.user.mention}**, in order to start, we require **{goal}+ Reactions**!\n\n"
            f"{DOT}Before participating in any official **HexVille** sessions, please ensure you've read the rules, registered your vehicle via the `/registervehicle` command, and reviewed the Blacklisted Vehicle List."
        ),
        color=BOT_COLOR
    )
    embed.set_image(url=IMG_STARTUP)
    msg = await interaction.channel.send("@everyone", embed=embed)
    try:
        await msg.add_reaction(CHECK_EMOJI)
    except Exception:
        try:
            await msg.add_reaction("✅")
        except Exception:
            pass
    sessions[interaction.channel.id] = {"goal": goal, "msg": msg.id, "setup": {}, "link": None, "host_id": interaction.user.id}
    await interaction.followup.send("Startup posted.", ephemeral=True)

@app_commands.autocomplete(frp=frp_ac, leo=leo_ac, hc=hc_ac, aorp=aorp_ac, peacetime=peacetime_ac)
@bot.tree.command(name="reinvites", description="Send session reinvites")
async def reinvites(interaction: discord.Interaction, link: str, goal: int, frp: str, leo: str, hc: str, aorp: str, peacetime: str):
    if not is_staff(interaction):
        return await interaction.response.send_message("Unauthorized.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title=f"{HEART} __**HexVille, Re-Invites**__", description=f"{ORANGE}React with {CHECK_EMOJI} to release the session link.", color=BOT_COLOR)
    embed.set_image(url=IMG_REINVITES)
    msg = await interaction.channel.send("@everyone", embed=embed)
    try:
        await msg.add_reaction(CHECK_EMOJI)
    except Exception:
        try:
            await msg.add_reaction("✅")
        except Exception:
            pass
    sessions[interaction.channel.id] = {
        "goal": goal,
        "msg": msg.id,
        "link": link,
        "setup": {"frp": frp, "leo": leo, "house": hc, "aorp": aorp, "peacetime": peacetime},
        "host_id": interaction.user.id
    }
    await interaction.followup.send("Reinvites started.", ephemeral=True)

@app_commands.autocomplete(frp=frp_ac, leo=leo_ac, hc=hc_ac, aorp=aorp_ac, peacetime=peacetime_ac)
@bot.tree.command(name="release", description="Release session to Civilians")
async def release(interaction: discord.Interaction, link: str, frp: str, leo: str, hc: str, aorp: str, peacetime: str):
    if not is_staff(interaction):
        return await interaction.response.send_message("Unauthorized.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    s = {"frp": frp, "leo": leo, "house": hc, "aorp": aorp, "peacetime": peacetime}
    embed = discord.Embed(title=f"{HEART} __**HexVille, Session Release**__", description=f"__Session Information__\n{session_info(s)}", color=BOT_COLOR)
    embed.set_image(url=IMG_RELEASE)
    await interaction.channel.send(f"<@&{CIVILIAN_ROLE_ID}>", embed=embed, view=None)
    await interaction.followup.send("Session released to Civilians.", ephemeral=True)

@bot.tree.command(name="end", description="End the session")
async def end(interaction: discord.Interaction):
    if not is_staff(interaction):
        return await interaction.response.send_message("Unauthorized.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    channel_id = interaction.channel.id
    data = session_log.get(channel_id)
    end_time = datetime.utcnow()
    if data:
        start_time = data.get("start")
        total_time = end_time - start_time if start_time else "N/A"
        log_channel = interaction.guild.get_channel(SESSION_LOG_CHANNEL_ID)
        embed_log = discord.Embed(
            title="📘 Session Log",
            description=(
                f"{DOT} **Start Time:** {start_time or 'N/A'}\n"
                f"{DOT} **End Time:** {end_time}\n"
                f"{DOT} **Total Time:** {total_time}\n"
                f"{DOT} **Session Host:** {data.get('host', 'N/A')}\n"
                f"{DOT} **Session Co-Host(s):** {data.get('cohosts', 'N/A')}\n"
                f"{DOT} **Session Supervisor(s):** {data.get('supervisors', 'N/A')}\n"
                f"{DOT} **Additional Notes:** {data.get('notes', 'N/A')}"
            ),
            color=BOT_COLOR
        )
        if log_channel:
            await log_channel.send(embed=embed_log)
        session_log.pop(channel_id, None)
    embed = discord.Embed(title=f"{HEART} __**HexVille, Session End**__", description=f"{ORANGE}{interaction.user.mention} has ended the session.\n-# HexVille Staff Team", color=BOT_COLOR)
    embed.set_image(url=IMG_END)
    await interaction.channel.send(embed=embed)
    sessions.pop(interaction.channel.id, None)
    await interaction.followup.send("Session ended.", ephemeral=True)

# ================== PANEL & TICKET SYSTEM ==================
PANEL_EMBED = build_panel_embed()

class SessionButton(ui.View):
    def __init__(self, link: str):
        super().__init__(timeout=None)
        self.link = link
        if link:
            self.add_item(ui.Button(label="Join Session", url=link))

class TicketCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        if not channel:
            return await interaction.response.send_message("Channel not found.", ephemeral=True)

        owner_id = None
        if channel.topic and "ticket_owner:" in channel.topic:
            try:
                owner_id = int(channel.topic.split("ticket_owner:")[1].split("|")[0])
            except Exception:
                owner_id = None

        is_owner = (interaction.user.id == owner_id)
        is_staff_user = has_role(interaction.user, ADMIN_ROLE_ID) or has_role(interaction.user, HIGHCOMMAND_ROLE_ID) or has_role(interaction.user, OWNERSHIP_ROLE_ID) or has_role(interaction.user, STAFF_TEAM_ROLE_ID)

        if not (is_owner or is_staff_user):
            return await interaction.response.send_message("Only the ticket owner or staff can close this ticket.", ephemeral=True)

        await interaction.response.send_message("Ticket will be closed in 5 seconds...", ephemeral=True)

        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

        try:
            await asyncio.sleep(5)

            # Send transcript to ACTION_LOG_CHANNEL
            try:
                await send_transcript(channel, interaction.guild)
            except Exception:
                pass

            # Log close action
            embed_log = discord.Embed(
                title="🎫 Ticket Closed",
                description=(f"{ORANGE}**Ticket Channel:** {channel.name}\n{ORANGE}**Closed By:** {interaction.user.mention}"),
                color=BOT_COLOR,
                timestamp=datetime.utcnow()
            )
            await log_action(interaction.guild, embed_log)
        except Exception:
            pass

        try:
            # Attempt to remove claimed_by/status before deletion (auto-unclaim)
            try:
                if channel.topic:
                    new_topic = remove_claim_and_set_closed(channel.topic)
                    await channel.edit(topic=new_topic)
            except Exception:
                pass

            await channel.delete(reason=f"Ticket closed by {interaction.user}")
        except Exception:
            await interaction.followup.send("Failed to delete the channel. Please check bot permissions.", ephemeral=True)

def remove_claim_and_set_closed(topic: str) -> str:
    parts = [p.strip() for p in topic.split("|")]
    kv = {}
    for p in parts:
        if ":" in p:
            k, v = p.split(":", 1)
            kv[k.strip()] = v.strip()
    kv["status"] = "closed"
    kv.pop("claimed_by", None)
    return "|".join(f"{k}:{v}" for k, v in kv.items())

class TicketTypeSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Moderation Appeal", description="Appeal a moderation action", emoji="🛡️"),
            discord.SelectOption(label="Civilian Support", description="General civilian support or questions", emoji="❗"),
            discord.SelectOption(label="Member Report", description="Report a member for rule violations", emoji="👤"),
            discord.SelectOption(label="Support Ticket", description="General support or technical help", emoji="🎫"),
            discord.SelectOption(label="Partnership Request", description="Request a partnership", emoji="🤝")
        ]
        super().__init__(placeholder="Select a ticket type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        global ticket_counter
        await interaction.response.defer(ephemeral=True)

        ticket_type = self.values[0]
        user = interaction.user
        guild = interaction.guild

        category = guild.get_channel(TICKET_CATEGORY_ID)
        if category is None:
            return await interaction.followup.send("Ticket category not found. Please contact an administrator.", ephemeral=True)

        # Anti-duplicate: check for existing open ticket for this user
        for ch in category.text_channels:
            if ch.topic and f"ticket_owner:{user.id}" in ch.topic and "status:open" in ch.topic:
                return await interaction.followup.send(f"You already have an open ticket: {ch.mention}. Please use that one or wait for it to be closed.", ephemeral=True)

        ticket_counter += 1
        safe_username = "".join(c for c in user.name if c.isalnum() or c in ("-", "_")).lower() or f"user{user.id}"
        channel_name = f"{safe_username}-{ticket_counter}"

        # Determine priority: VIP_VEHICLE_ROLE_ID (server booster) => High
        priority = "High" if any(r.id == VIP_VEHICLE_ROLE_ID for r in user.roles) else "Normal"

        overwrites: Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite] = {}
        overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False, send_messages=False, read_message_history=False)
        overwrites[user] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # Staff roles allowed to view initially: Admin, HighCommand, Ownership, StaffTeam
        for rid in (ADMIN_ROLE_ID, HIGHCOMMAND_ROLE_ID, OWNERSHIP_ROLE_ID, STAFF_TEAM_ROLE_ID):
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        bot_member = guild.me
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        topic = f"ticket_owner:{user.id}|type:{ticket_type}|status:open|priority:{priority}|claimed_by:None"

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=topic,
                reason=f"Ticket created by {user} via panel"
            )
        except Exception as e:
            return await interaction.followup.send(f"Failed to create ticket channel: {e}", ephemeral=True)

        # Ping staff (force role mentions)
        staff_ping = f"<@&{STAFF_TEAM_ROLE_ID}> <@&{OWNERSHIP_ROLE_ID}>"
        allowed = discord.AllowedMentions(roles=True, users=True, everyone=False, replied_user=False)

        try:
            await channel.send(content=staff_ping, embed=build_ticket_embed(user, ticket_type, priority), view=TicketCloseView(), allowed_mentions=allowed)
        except Exception:
            await channel.send(content=staff_ping, embed=build_ticket_embed(user, ticket_type, priority), allowed_mentions=allowed)

        # Ensure topic is set (some environments may require an explicit edit)
        try:
            await channel.edit(topic=topic)
        except Exception:
            pass

        try:
            embed_log = discord.Embed(
                title="🎫 New Ticket Created (Panel)",
                description=(f"{ORANGE}**Owner:** {user.mention}\n{ORANGE}**Channel:** {channel.mention}\n{ORANGE}**Type:** {ticket_type}\n{ORANGE}**Priority:** {priority}"),
                color=BOT_COLOR,
                timestamp=datetime.utcnow()
            )
            await log_action(guild, embed_log)
            add_history_entry(user.id, "ticket_open", f"Opened ticket {channel.name} ({ticket_type})", user.id, extra="via panel")
        except Exception:
            pass

        await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)

class PanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())

@bot.tree.command(name="panel", description="Send the HexVille support panel")
async def panel(interaction: discord.Interaction):
    if not is_staff(interaction):
        return await interaction.response.send_message("Unauthorized.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    try:
        await interaction.channel.send(embed=PANEL_EMBED, view=PanelView())
        await interaction.followup.send("Support panel posted.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to post panel: {e}", ephemeral=True)

@bot.tree.command(name="close", description="Close the current ticket")
async def close(interaction: discord.Interaction):
    channel = interaction.channel
    if not channel or not channel.topic or "ticket_owner:" not in channel.topic:
        return await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)

    await interaction.response.send_message("Ticket will be closed in 5 seconds...", ephemeral=True)

    try:
        await asyncio.sleep(5)

        # Send transcript to ACTION_LOG_CHANNEL
        try:
            await send_transcript(channel, interaction.guild)
        except Exception:
            pass

        embed_log = discord.Embed(
            title="🎫 Ticket Closed",
            description=(f"{ORANGE}**Ticket Channel:** {channel.name}\n{ORANGE}**Closed By:** {interaction.user.mention}"),
            color=BOT_COLOR,
            timestamp=datetime.utcnow()
        )
        await log_action(interaction.guild, embed_log)
    except Exception:
        pass

    try:
        # Auto-unclaim: set status closed and remove claimed_by
        try:
            if channel.topic:
                new_topic = remove_claim_and_set_closed(channel.topic)
                await channel.edit(topic=new_topic)
        except Exception:
            pass

        await channel.delete(reason=f"Ticket closed by {interaction.user}")
    except Exception:
        await interaction.followup.send("Failed to delete the ticket channel. Check bot permissions.", ephemeral=True)

# ================== HELP COMMAND (Grouped + Dynamic Permission Detection) ==================
@bot.tree.command(name="help", description="Show all available commands and their permissions")
async def help_command(interaction: discord.Interaction):
    user = interaction.user
    can_register = True  # example: civilians can register
    can_low = has_role(user, STAFF_TEAM_ROLE_ID) or has_role(user, ADMIN_ROLE_ID) or has_role(user, HIGHCOMMAND_ROLE_ID) or has_role(user, OWNERSHIP_ROLE_ID)
    can_high = has_role(user, HIGHCOMMAND_ROLE_ID) or has_role(user, OWNERSHIP_ROLE_ID) or has_role(user, ADMIN_ROLE_ID)
    can_ownership = has_role(user, OWNERSHIP_ROLE_ID) or has_role(user, ADMIN_ROLE_ID)
    can_dev = has_role(user, ADMIN_ROLE_ID)  # treat ADMIN_ROLE_ID as bot developer for this example

    def yn(v: bool) -> str:
        return "Yes" if v else "No"

    embed = discord.Embed(title="__**All Command Information**__", color=BOT_COLOR)
    desc_lines = []

    # Civilian Commands
    desc_lines.append(f"{BLUEARROW} **/register** — Register as a civilian\n> Can Use: {yn(can_register)}")
    desc_lines.append("")

    # Public Commands
    desc_lines.append(f"{BLUEARROW} **/help** — Shows all available commands\n> Can Use: Yes")
    desc_lines.append("")

    # Staff Team (Low Command)
    desc_lines.append(f"{BLUEARROW} **/warn** — Issue a warning to a user\n> Can Use: {yn(can_low)}")
    desc_lines.append(f"{BLUEARROW} **/panel** — Open support panel (staff only)\n> Can Use: {yn(is_staff(interaction))}")
    desc_lines.append("")

    # High Command
    desc_lines.append(f"{BLUEARROW} **/strike** — Issue a strike to a user\n> Can Use: {yn(can_high)}")
    desc_lines.append(f"{BLUEARROW} **/claim** — Claim a support ticket\n> Can Use: {yn(can_high)}")
    desc_lines.append(f"{BLUEARROW} **/close** — Close a ticket\n> Can Use: {yn(can_high)}")
    desc_lines.append("")

    # Ownership Team
    desc_lines.append(f"{BLUEARROW} **/admin** — Administrative controls\n> Can Use: {yn(can_ownership)}")
    desc_lines.append("")

    # Developer
    desc_lines.append(f"{BLUEARROW} **/devonly** — Developer-only commands\n> Can Use: {yn(can_dev)}")
    desc_lines.append("")

    # Ticket & Utility
    desc_lines.append(f"{BLUEARROW} **/whois** — Show full information about a user\n> Can Use: Yes")

    embed.description = "\n".join(desc_lines)
    await interaction.response.send_message(embed=embed)

# ================== CLAIM COMMAND ==================
@bot.tree.command(name="claim", description="Claim the current ticket (High Command+)")
async def claim(interaction: discord.Interaction):
    if not (has_role(interaction.user, HIGHCOMMAND_ROLE_ID) or has_role(interaction.user, OWNERSHIP_ROLE_ID) or has_role(interaction.user, ADMIN_ROLE_ID)):
        return await interaction.response.send_message("Unauthorized.", ephemeral=True)

    channel = interaction.channel
    if not channel or not channel.topic or "ticket_owner:" not in channel.topic:
        return await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)

    topic = channel.topic
    kv = {}
    for part in [p.strip() for p in topic.split("|")]:
        if ":" in part:
            k, v = part.split(":", 1)
            kv[k.strip()] = v.strip()

    ticket_type = kv.get("type", "Support Ticket")
    status = kv.get("status", "open")
    if status != "open":
        return await interaction.response.send_message("This ticket is not open.", ephemeral=True)

    # Update topic: set claimed_by to user id
    kv["claimed_by"] = str(interaction.user.id)
    new_topic = "|".join(f"{k}:{v}" for k, v in kv.items())
    try:
        await channel.edit(topic=new_topic)
    except Exception:
        pass

    guild = interaction.guild
    allowed_role_ids = {HIGHCOMMAND_ROLE_ID, OWNERSHIP_ROLE_ID, ADMIN_ROLE_ID}

    # Build new overwrites dict from scratch
    overwrites: Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite] = {}
    overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False, send_messages=False, read_message_history=False)

    # Ticket owner id
    owner_id = None
    try:
        owner_id = int(kv.get("ticket_owner", kv.get("ticket_owner", "") or 0))
    except Exception:
        owner_id = None

    # Allow HighCommand/Ownership/Admin roles to view+send
    for rid in (HIGHCOMMAND_ROLE_ID, OWNERSHIP_ROLE_ID, ADMIN_ROLE_ID):
        role = guild.get_role(rid)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    # Staff Team: view but not send
    staff_role = guild.get_role(STAFF_TEAM_ROLE_ID)
    if staff_role and staff_role.id not in allowed_role_ids:
        overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)

    # Ticket owner member overwrite (deny send)
    if owner_id:
        owner_member = guild.get_member(owner_id)
        if owner_member:
            overwrites[owner_member] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)

    # Bot must be able to send
    bot_member = guild.me
    if bot_member:
        overwrites[bot_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    try:
        await channel.edit(overwrites=overwrites)
    except Exception:
        pass

    embed = discord.Embed(
        title="🎫 Ticket Claimed",
        description=(
            f"{BLUEARROW} This ticket has been claimed by **{interaction.user.mention}**.\n"
            f"{BLUEARROW} Your **{ticket_type}** will be handled by them."
        ),
        color=BOT_COLOR
    )

    allowed = discord.AllowedMentions(roles=True, users=True)
    await interaction.response.send_message(embed=embed, allowed_mentions=allowed)

    try:
        embed_log = discord.Embed(
            title="🎫 Ticket Claimed",
            description=(f"{ORANGE}**Ticket:** {channel.name}\n{ORANGE}**Claimed By:** {interaction.user.mention}"),
            color=BOT_COLOR,
            timestamp=datetime.utcnow()
        )
        await log_action(guild, embed_log)
    except:
        pass

# ================== TRANSCRIPT FUNCTION ==================
async def send_transcript(channel: discord.TextChannel, guild: discord.Guild):
    msgs = []
    try:
        async for m in channel.history(limit=500, oldest_first=True):
            timestamp = m.created_at.isoformat(timespec="seconds")
            author = f"{m.author} ({m.author.id})"
            content = m.content or ""
            if m.attachments:
                att_texts = " ".join(a.url for a in m.attachments)
                content = f"{content}\n[Attachments: {att_texts}]"
            msgs.append(f"[{timestamp}] {author}: {content}")
    except Exception:
        pass

    transcript_text = "\n".join(msgs) or "No messages found."

    log_channel = guild.get_channel(ACTION_LOG_CHANNEL)
    if not log_channel:
        return

    header = discord.Embed(title=f"Transcript — {channel.name}", description=f"Ticket closed at {datetime.utcnow().isoformat(timespec='seconds')}", color=BOT_COLOR, timestamp=datetime.utcnow())
    await log_channel.send(embed=header)

    max_len = 1900
    current = ""
    for line in transcript_text.splitlines():
        if len(current) + len(line) + 1 > max_len:
            await log_channel.send(f"```{current}```")
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        await log_channel.send(f"```{current}```")

# ================== WHOIS COMMAND ==================
@bot.tree.command(name="whois", description="Show full information about a user")
@app_commands.describe(member="Member to inspect")
async def whois(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    if member is None:
        member = interaction.user  # type: ignore

    strikes = staff_strikes.get(member.id, 0)
    civ_infractions = civilian_infractions.get(member.id, 0)
    notes = notes_store.get(member.id, [])
    history_entries = history_store.get(member.id, [])
    vehicles = vehicle_store.get(member.id, [])
    unregisters = unregister_uses.get(member.id, 0)

    roles = ", ".join(r.name for r in member.roles if r.name != "@everyone") or "None"
    is_staff_flag = any(r.id in STAFF_ROLE_IDS for r in member.roles)
    is_highcommand_flag = any(r.id == HIGHCOMMAND_ROLE_ID for r in member.roles)
    is_ownership_flag = any(r.id == OWNERSHIP_ROLE_ID for r in member.roles)
    is_admin_flag = any(r.id == ADMIN_ROLE_ID for r in member.roles)
    is_booster = any(r.id == VIP_VEHICLE_ROLE_ID for r in member.roles)

    note_text = "None"
    if notes:
        note_text = "\n".join(f"{n['timestamp']} — {n['note']}" for n in notes[-10:])

    hist_text = "None"
    if history_entries:
        hist_text = "\n".join(f"{h['timestamp']} — {h['action']}" for h in history_entries[-10:])

    vehicle_text = "None"
    if vehicles:
        vehicle_text = "\n".join(f"{v.get('year','N/A')} {v.get('make','N/A')} {v.get('model','N/A')} — {v.get('plate','N/A')} ({v.get('state','N/A')})" for v in vehicles)

    embed = discord.Embed(title=f"🔎 Whois — {member.display_name}", color=BOT_COLOR, timestamp=datetime.utcnow())
    embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
    embed.add_field(name="Roles", value=roles, inline=False)
    embed.add_field(name="Staff?", value=str(is_staff_flag), inline=True)
    embed.add_field(name="High Command?", value=str(is_highcommand_flag), inline=True)
    embed.add_field(name="Ownership?", value=str(is_ownership_flag), inline=True)
    embed.add_field(name="Admin/Dev?", value=str(is_admin_flag), inline=True)
    embed.add_field(name="Server Booster (High Priority)?", value=str(is_booster), inline=True)
    embed.add_field(name="Staff Strikes", value=str(strikes), inline=False)
    embed.add_field(name="Civilian Infractions", value=str(civ_infractions), inline=False)
    embed.add_field(name="Registered Vehicles", value=vehicle_text, inline=False)
    embed.add_field(name="Unregister Uses Remaining", value=str(unregisters), inline=False)
    embed.add_field(name="Internal Notes (last 10)", value=note_text, inline=False)
    embed.add_field(name="Recent History (last 10)", value=hist_text, inline=False)

    await interaction.response.send_message(embed=embed)

# ================== SERVER AD & COMING SOON ==================
@bot.tree.command(name="serverad", description="Post the official server advertisement (Staff only)")
async def serverad(interaction: discord.Interaction):
    if not is_staff(interaction):
        return await interaction.response.send_message("Unauthorized.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title="**__HexVille Official Server Advertisement__** 🫂",
        description=(
            "Greetings everyone! **HexVille** is currently accepting free civilians, and are currently in need of __**members**__, join now to be apart of our server!\n\n"
            "**HexVille exclusively offers:**\n"
            "→ Exclusive Events!\n"
            "→ Regular Sessions!\n"
            "→ Robux Giveaways!\n"
            "→ Special Roleplays!\n"
            "→ And So Much More!\n\n"
            "[Join now!](https://discord.gg/MJsvGa6QNy)"
        ),
        color=BOT_COLOR
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1431352916286902285/1458956254310437096/HexVille_1.png")
    await interaction.channel.send(embed=embed)
    await interaction.followup.send("Server advertisement posted.", ephemeral=True)

@bot.tree.command(name="comingsoon", description="Show coming soon embed")
async def comingsoon(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title="__**Coming Soon**__",
        description=f"<:crane:1459330223131721769>  This section is currently **__under-construction__**, please come back again later! <:crane:1459330223131721769>",
        color=BOT_COLOR
    )
    embed.set_image(url="https://media.discordapp.net/attachments/1459323143989497918/1459423962298847388/HexVille_3.png")
    await interaction.channel.send(embed=embed)
    await interaction.followup.send("Shown coming soon.", ephemeral=True)

# ================== START BOT ==================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel and message.channel.id == MUTE_HINT_CHANNEL_ID:
        embed = discord.Embed(
            description="<:bell:1459329848161075200> Tired of __pings__? **Mute this channel**.",
            color=BOT_COLOR
        )
        embed.set_image(url="https://media1.tenor.com/m/j0RsjzrynisAAAAd/discord.gif")
        await message.channel.send(embed=embed)
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        if TEST_GUILD_ID:
            guild_obj = discord.Object(id=int(TEST_GUILD_ID))
            await bot.tree.sync(guild=guild_obj)
        else:
            await bot.tree.sync()
    except Exception:
        pass

if __name__ == "__main__":
    bot.run(TOKEN)
