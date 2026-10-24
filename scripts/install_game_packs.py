#!/usr/bin/env python3
"""
Instalador de Packs de Jogos Retrô (SNES, Arcade/NeoGeo/MAME e Sega Mega Drive)
para o HybridBox Remote PWA e Xiaomi Redmi Note 8 Pro.

Baixa em paralelo +48 ROMs de repositórios do GitHub (`retrobrews/snes-games`,
`retrobrews/md-games`, `PIBSAS/NeoGeo` com BIOS `neogeo.zip`) e do acervo oficial
`mamedev.org/roms`, salvando localmente em `roms/{snes,mame,megadrive}` e enviando
para `/sdcard/ROMs/{snes,mame,megadrive}` e `/sdcard/MAME4droid/roms` no celular.
"""

import concurrent.futures
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent.parent
ROMS_DIR = BASE_DIR / "roms"

SNES_BASE = "https://raw.githubusercontent.com/retrobrews/snes-games/master"
MD_BASE = "https://raw.githubusercontent.com/retrobrews/md-games/master"
NEOGEO_BASE = "https://raw.githubusercontent.com/PIBSAS/NeoGeo/master/neogeo"
MAME_BASE = "https://www.mamedev.org/roms"

import urllib.parse

GAME_PACKS_CATALOG: List[Dict[str, Any]] = [
    # ==================== PACK 1: SUPER NINTENDO (SNES) ====================
    {
        "system": "snes",
        "filename": "superbossgaiden.sfc",
        "title": "Super Boss Gaiden",
        "subtitle": "16-Bit Action • SNES",
        "genre": "Action / Boss Rush",
        "console_badge": "SNES",
        "icon": "🥷",
        "art_type": "samurai",
        "palette": ("#dc2626", "#7f1d1d", "#fde047"),
        "url": f"{SNES_BASE}/superbossgaiden.sfc",
    },
    {
        "system": "snes",
        "filename": "megafamilybros.smc",
        "title": "Mega Family Bros",
        "subtitle": "Arcade Platformer • SNES",
        "genre": "Platformer",
        "console_badge": "SNES",
        "icon": "🍄",
        "art_type": "platform_hero",
        "palette": ("#2563eb", "#1e3a8a", "#facc15"),
        "url": f"{SNES_BASE}/megafamilybros.smc",
    },
    {
        "system": "snes",
        "filename": "nwarpdaisakusen.smc",
        "title": "N-Warp Daisakusen",
        "subtitle": "Multiplayer Arena • SNES",
        "genre": "Battle / Party",
        "console_badge": "SNES",
        "icon": "⚡",
        "art_type": "mecha_cyber",
        "palette": ("#7c3aed", "#3b0764", "#38bdf8"),
        "url": f"{SNES_BASE}/nwarpdaisakusen.smc",
    },
    {
        "system": "snes",
        "filename": "furryrpg.sfc",
        "title": "Furry RPG",
        "subtitle": "Epic Adventure • SNES",
        "genre": "RPG / Adventure",
        "console_badge": "SNES",
        "icon": "🗡️",
        "art_type": "rpg_magic",
        "palette": ("#059669", "#064e3b", "#fde68a"),
        "url": f"{SNES_BASE}/furryrpg.sfc",
    },
    {
        "system": "snes",
        "filename": "questformoney.sfc",
        "title": "UWOL: Quest for Money",
        "subtitle": "Treasure Hunt • SNES",
        "genre": "Platformer / Arcade",
        "console_badge": "SNES",
        "icon": "💰",
        "art_type": "treasure_adventure",
        "palette": ("#d97706", "#78350f", "#fef08a"),
        "url": f"{SNES_BASE}/questformoney.sfc",
    },
    {
        "system": "snes",
        "filename": "jetpilotrising.sfc",
        "title": "Jet Pilot Rising",
        "subtitle": "Aerial Combat • SNES",
        "genre": "Shoot 'em Up",
        "console_badge": "SNES",
        "icon": "✈️",
        "art_type": "jet",
        "palette": ("#0284c7", "#0c4a6e", "#38bdf8"),
        "url": f"{SNES_BASE}/jetpilotrising.sfc",
    },
    {
        "system": "snes",
        "filename": "astrohawk.smc",
        "title": "Astrohawk",
        "subtitle": "Space Warfare • SNES",
        "genre": "Space Shooter",
        "console_badge": "SNES",
        "icon": "🚀",
        "art_type": "spaceship",
        "palette": ("#4f46e5", "#1e1b4b", "#a5b4fc"),
        "url": f"{SNES_BASE}/astrohawk.smc",
    },
    {
        "system": "snes",
        "filename": "tchouv2.smc",
        "title": "Tchou v2",
        "subtitle": "Railway Express • SNES",
        "genre": "Puzzle / Strategy",
        "console_badge": "SNES",
        "icon": "🚂",
        "art_type": "racing",
        "palette": ("#ea580c", "#7c2d12", "#fed7aa"),
        "url": f"{SNES_BASE}/tchouv2.smc",
    },
    {
        "system": "snes",
        "filename": "rockfall.smc",
        "title": "Rockfall",
        "subtitle": "Boulder Dash Edition • SNES",
        "genre": "Puzzle / Mining",
        "console_badge": "SNES",
        "icon": "💎",
        "art_type": "puzzle_bubbles",
        "palette": ("#9333ea", "#3b0764", "#f0abfc"),
        "url": f"{SNES_BASE}/rockfall.smc",
    },
    {
        "system": "snes",
        "filename": "saf.smc",
        "title": "S.A.F. Arcade",
        "subtitle": "Action Squad • SNES",
        "genre": "Action / Arcade",
        "console_badge": "SNES",
        "icon": "🛡️",
        "art_type": "platform_hero",
        "palette": ("#e11d48", "#881337", "#fda4af"),
        "url": f"{SNES_BASE}/saf.smc",
    },
    {
        "system": "snes",
        "filename": "hilda.sfc",
        "title": "Hilda Adventure",
        "subtitle": "Forest Journey • SNES",
        "genre": "Adventure / Platformer",
        "console_badge": "SNES",
        "icon": "🌲",
        "art_type": "platform_hero",
        "palette": ("#16a34a", "#14532d", "#bbf7d0"),
        "url": f"{SNES_BASE}/hilda.sfc",
    },
    {
        "system": "snes",
        "filename": "bucket.smc",
        "title": "Bucket Arcade",
        "subtitle": "Reflex & Precision • SNES",
        "genre": "Arcade Puzzle",
        "console_badge": "SNES",
        "icon": "🪣",
        "art_type": "puzzle_bubbles",
        "palette": ("#0891b2", "#164e63", "#67e8f9"),
        "url": f"{SNES_BASE}/bucket.smc",
    },
    {
        "system": "snes",
        "filename": "blt.sfc",
        "title": "B.L.T. Retro",
        "subtitle": "16-Bit Classic • SNES",
        "genre": "Retro Platformer",
        "console_badge": "SNES",
        "icon": "🥪",
        "art_type": "platform_hero",
        "palette": ("#ca8a04", "#713f12", "#fef08a"),
        "url": f"{SNES_BASE}/blt.sfc",
    },
    {
        "system": "snes",
        "filename": "horizontal-shooter.sfc",
        "title": "Horizontal Shooter",
        "subtitle": "Star Squadron • SNES",
        "genre": "Shoot 'em Up",
        "console_badge": "SNES",
        "icon": "🛸",
        "art_type": "jet",
        "palette": ("#2563eb", "#172554", "#93c5fd"),
        "url": f"{SNES_BASE}/horizontal-shooter.sfc",
    },
    # ==================== PACK 2: ARCADE / NEOGEO MVS / MAME ====================
    {
        "system": "mame",
        "filename": "neogeo.zip",
        "title": "[BIOS] NeoGeo MVS / AES System BIOS",
        "subtitle": "Official SNK BIOS",
        "genre": "System BIOS",
        "console_badge": "NeoGeo",
        "icon": "⚙️",
        "art_type": "mecha_cyber",
        "palette": ("#475569", "#0f172a", "#94a3b8"),
        "url": f"{NEOGEO_BASE}/neogeo.zip",
        "is_bios": True,
    },
    {
        "system": "mame",
        "filename": "mslug.zip",
        "title": "Metal Slug",
        "subtitle": "Super Vehicle-001 • SNK 1996",
        "genre": "Military Run & Gun",
        "console_badge": "NeoGeo",
        "icon": "🎖️",
        "art_type": "tank",
        "palette": ("#ea580c", "#7c2d12", "#fde047"),
        "url": f"{NEOGEO_BASE}/mslug.zip",
    },
    {
        "system": "mame",
        "filename": "mslug2.zip",
        "title": "Metal Slug 2",
        "subtitle": "Super Vehicle-001/II • SNK 1998",
        "genre": "Military Run & Gun",
        "console_badge": "NeoGeo",
        "icon": "💥",
        "art_type": "tank",
        "palette": ("#dc2626", "#7f1d1d", "#facc15"),
        "url": f"{NEOGEO_BASE}/mslug2.zip",
    },
    {
        "system": "mame",
        "filename": "mslugx.zip",
        "title": "Metal Slug X",
        "subtitle": "Super Vehicle-001 • SNK 1999",
        "genre": "Military Run & Gun",
        "console_badge": "NeoGeo",
        "icon": "🔥",
        "art_type": "tank",
        "palette": ("#b91c1c", "#450a0a", "#fde047"),
        "url": f"{NEOGEO_BASE}/mslugx.zip",
    },
    {
        "system": "mame",
        "filename": "kof97.zip",
        "title": "The King of Fighters '97",
        "subtitle": "Orochi Saga • SNK 1997",
        "genre": "2D Fighting / Tournament",
        "console_badge": "NeoGeo",
        "icon": "🥊",
        "art_type": "fighter_flame",
        "palette": ("#e11d48", "#4c0519", "#fde047"),
        "url": f"{NEOGEO_BASE}/kof97.zip",
    },
    {
        "system": "mame",
        "filename": "samsho2.zip",
        "title": "Samurai Shodown II",
        "subtitle": "Shin Samurai Spirits • SNK 1994",
        "genre": "Weapon Fighting",
        "console_badge": "NeoGeo",
        "icon": "⚔️",
        "art_type": "samurai",
        "palette": ("#be123c", "#4c0519", "#fef08a"),
        "url": f"{NEOGEO_BASE}/samsho2.zip",
    },
    {
        "system": "mame",
        "filename": "fatfursp.zip",
        "title": "Fatal Fury Special",
        "subtitle": "Garou Densetsu Special • SNK",
        "genre": "2D Fighting / Versus",
        "console_badge": "NeoGeo",
        "icon": "🐺",
        "art_type": "fighter_flame",
        "palette": ("#d97706", "#451a03", "#fef08a"),
        "url": f"{NEOGEO_BASE}/fatfursp.zip",
    },
    {
        "system": "mame",
        "filename": "sonicwi2.zip",
        "title": "Aero Fighters 2",
        "subtitle": "Sonic Wings 2 • Video System",
        "genre": "Arcade Shoot 'em Up",
        "console_badge": "NeoGeo",
        "icon": "✈️",
        "art_type": "jet",
        "palette": ("#0284c7", "#082f49", "#7dd3fc"),
        "url": f"{NEOGEO_BASE}/sonicwi2.zip",
    },
    {
        "system": "mame",
        "filename": "spinmast.zip",
        "title": "Spinmaster",
        "subtitle": "Miracle Adventure • Data East",
        "genre": "Action / Platformer",
        "console_badge": "NeoGeo",
        "icon": "🪀",
        "art_type": "treasure_adventure",
        "palette": ("#16a34a", "#052e16", "#fde047"),
        "url": f"{NEOGEO_BASE}/spinmast.zip",
    },
    {
        "system": "mame",
        "filename": "turfmast.zip",
        "title": "Neo Turf Masters",
        "subtitle": "Big Tournament Golf • Nazca",
        "genre": "Sports / Golf",
        "console_badge": "NeoGeo",
        "icon": "⛳",
        "art_type": "golf",
        "palette": ("#15803d", "#052e16", "#bbf7d0"),
        "url": f"{NEOGEO_BASE}/turfmast.zip",
    },
    {
        "system": "mame",
        "filename": "pbobblen.zip",
        "title": "Puzzle Bobble",
        "subtitle": "Bust-A-Move • Taito 1994",
        "genre": "Classic Puzzle",
        "console_badge": "NeoGeo",
        "icon": "🫧",
        "art_type": "puzzle_bubbles",
        "palette": ("#7c3aed", "#2e1065", "#f472b6"),
        "url": f"{NEOGEO_BASE}/pbobblen.zip",
    },
    {
        "system": "mame",
        "filename": "wjammers.zip",
        "title": "Windjammers",
        "subtitle": "Flying Power Disc • Data East",
        "genre": "Arcade Sports",
        "console_badge": "NeoGeo",
        "icon": "🥏",
        "art_type": "disc_sport",
        "palette": ("#0891b2", "#083344", "#facc15"),
        "url": f"{NEOGEO_BASE}/wjammers.zip",
    },
    {
        "system": "mame",
        "filename": "doubledr.zip",
        "title": "Double Dragon",
        "subtitle": "Technos Japan • NeoGeo MVS",
        "genre": "2D Fighting / Versus",
        "console_badge": "NeoGeo",
        "icon": "🐉",
        "art_type": "fighter_flame",
        "palette": ("#dc2626", "#450a0a", "#facc15"),
        "url": f"{NEOGEO_BASE}/doubledr.zip",
    },
    {
        "system": "mame",
        "filename": "tophuntr.zip",
        "title": "Top Hunter",
        "subtitle": "Roddy & Cathy • SNK 1994",
        "genre": "Action / Platformer",
        "console_badge": "NeoGeo",
        "icon": "🦾",
        "art_type": "treasure_adventure",
        "palette": ("#ea580c", "#431407", "#fed7aa"),
        "url": f"{NEOGEO_BASE}/tophuntr.zip",
    },
    {
        "system": "mame",
        "filename": "cyberlip.zip",
        "title": "Cyber-Lip",
        "subtitle": "Futuristic Run & Gun • SNK",
        "genre": "Sci-Fi Run & Gun",
        "console_badge": "NeoGeo",
        "icon": "🤖",
        "art_type": "mecha_cyber",
        "palette": ("#2563eb", "#172554", "#38bdf8"),
        "url": f"{NEOGEO_BASE}/cyberlip.zip",
    },
    {
        "system": "mame",
        "filename": "maglord.zip",
        "title": "Magician Lord",
        "subtitle": "Alpha Denshi • SNK 1990",
        "genre": "Action / Fantasy",
        "console_badge": "NeoGeo",
        "icon": "🧙",
        "art_type": "rpg_magic",
        "palette": ("#6d28d9", "#2e1065", "#c4b5fd"),
        "url": f"{NEOGEO_BASE}/maglord.zip",
    },
    {
        "system": "mame",
        "filename": "sengoku.zip",
        "title": "Sengoku",
        "subtitle": "Samurai Beat 'em Up • SNK",
        "genre": "Beat 'em Up",
        "console_badge": "NeoGeo",
        "icon": "👹",
        "art_type": "samurai",
        "palette": ("#991b1b", "#450a0a", "#fca5a5"),
        "url": f"{NEOGEO_BASE}/sengoku.zip",
    },
    {
        "system": "mame",
        "filename": "nam1975.zip",
        "title": "NAM-1975",
        "subtitle": "Action Caballeros • SNK 1990",
        "genre": "Shooter / Action",
        "console_badge": "NeoGeo",
        "icon": "🚁",
        "art_type": "tank",
        "palette": ("#3f6212", "#1a2e05", "#bef264"),
        "url": f"{NEOGEO_BASE}/nam1975.zip",
    },
    {
        "system": "mame",
        "filename": "roboarmy.zip",
        "title": "Robo Army",
        "subtitle": "Mecha Beat 'em Up • SNK 1991",
        "genre": "Beat 'em Up",
        "console_badge": "NeoGeo",
        "icon": "🦾",
        "art_type": "mecha_cyber",
        "palette": ("#0369a1", "#082f49", "#7dd3fc"),
        "url": f"{NEOGEO_BASE}/roboarmy.zip",
    },
    {
        "system": "mame",
        "filename": "viewpoin.zip",
        "title": "Viewpoint",
        "subtitle": "Isometric Shooter • Sammy/SNK",
        "genre": "3D Shoot 'em Up",
        "console_badge": "NeoGeo",
        "icon": "🚀",
        "art_type": "spaceship",
        "palette": ("#4338ca", "#1e1b4b", "#a5b4fc"),
        "url": f"{NEOGEO_BASE}/viewpoin.zip",
    },
    {
        "system": "mame",
        "filename": "starfire.zip",
        "title": "Star Fire",
        "subtitle": "Exidy Classic • MAME",
        "genre": "Space Combat",
        "console_badge": "Arcade",
        "icon": "🌟",
        "art_type": "spaceship",
        "palette": ("#1d4ed8", "#172554", "#93c5fd"),
        "url": f"{MAME_BASE}/starfire/starfire.zip",
    },
    {
        "system": "mame",
        "filename": "targ.zip",
        "title": "Targ",
        "subtitle": "Exidy 1980 • MAME",
        "genre": "Maze / Shooter",
        "console_badge": "Arcade",
        "icon": "🕹️",
        "art_type": "spaceship",
        "palette": ("#b45309", "#451a03", "#fde047"),
        "url": f"{MAME_BASE}/targ/targ.zip",
    },
    {
        "system": "mame",
        "filename": "spectar.zip",
        "title": "Spectar",
        "subtitle": "Exidy Arcade • MAME",
        "genre": "Classic Arcade",
        "console_badge": "Arcade",
        "icon": "👾",
        "art_type": "spaceship",
        "palette": ("#7e22ce", "#3b0764", "#d8b4fe"),
        "url": f"{MAME_BASE}/spectar/spectar.zip",
    },
    {
        "system": "mame",
        "filename": "robotbwl.zip",
        "title": "Robot Bowl",
        "subtitle": "Exidy Bowling • MAME",
        "genre": "Retro Sports",
        "console_badge": "Arcade",
        "icon": "🎳",
        "art_type": "puzzle_bubbles",
        "palette": ("#0f766e", "#042f2e", "#5eead4"),
        "url": f"{MAME_BASE}/robotbwl/robotbwl.zip",
    },
    {
        "system": "mame",
        "filename": "victory.zip",
        "title": "Victory",
        "subtitle": "Space Combat • MAME",
        "genre": "Space Shooter",
        "console_badge": "Arcade",
        "icon": "🛸",
        "art_type": "spaceship",
        "palette": ("#3730a3", "#1e1b4b", "#818cf8"),
        "url": f"{MAME_BASE}/victory/victory.zip",
    },
    # ==================== PACK 3: SEGA MEGA DRIVE / GENESIS ====================
    {
        "system": "megadrive",
        "filename": "cavestory.bin",
        "title": "Cave Story MD",
        "subtitle": "Doukutsu Monogatari • 16-Bit",
        "genre": "Action / Metroidvania",
        "console_badge": "Mega Drive",
        "icon": "🏝️",
        "art_type": "platform_hero",
        "palette": ("#2563eb", "#172554", "#38bdf8"),
        "url": f"{MD_BASE}/cavestory.bin",
    },
    {
        "system": "megadrive",
        "filename": "fixitfelixjr.bin",
        "title": "Fix-It Felix Jr.",
        "subtitle": "Wreck-It Ralph Arcade • Sega MD",
        "genre": "Arcade / Platformer",
        "console_badge": "Mega Drive",
        "icon": "🔨",
        "art_type": "building_hammer",
        "palette": ("#d97706", "#451a03", "#fde047"),
        "url": f"{MD_BASE}/fixitfelixjr.bin",
    },
    {
        "system": "megadrive",
        "filename": "rickdangerous.bin",
        "title": "Rick Dangerous",
        "subtitle": "Core Design Classic • 16-Bit",
        "genre": "Adventure / Platformer",
        "console_badge": "Mega Drive",
        "icon": "🤠",
        "art_type": "treasure_adventure",
        "palette": ("#b45309", "#451a03", "#fcd34d"),
        "url": f"{MD_BASE}/rickdangerous.bin",
    },
    {
        "system": "megadrive",
        "filename": "rickdangerous2.bin",
        "title": "Rick Dangerous II",
        "subtitle": "Laser & Sci-Fi • Sega MD",
        "genre": "Adventure / Sci-Fi",
        "console_badge": "Mega Drive",
        "icon": "🔫",
        "art_type": "treasure_adventure",
        "palette": ("#7c3aed", "#2e1065", "#c4b5fd"),
        "url": f"{MD_BASE}/rickdangerous2.bin",
    },
    {
        "system": "megadrive",
        "filename": "ikplusdeluxe.bin",
        "title": "IK+ Deluxe",
        "subtitle": "International Karate + • MD",
        "genre": "Fighting / Karate",
        "console_badge": "Mega Drive",
        "icon": "🥋",
        "art_type": "karate",
        "palette": ("#dc2626", "#450a0a", "#fde047"),
        "url": f"{MD_BASE}/ikplusdeluxe.bin",
    },
    {
        "system": "megadrive",
        "filename": "barbarian.bin",
        "title": "Barbarian 16-Bit",
        "subtitle": "Death Sword • Sega MD",
        "genre": "Sword Fighting",
        "console_badge": "Mega Drive",
        "icon": "🪓",
        "art_type": "samurai",
        "palette": ("#991b1b", "#450a0a", "#fca5a5"),
        "url": f"{MD_BASE}/barbarian.bin",
    },
    {
        "system": "megadrive",
        "filename": "papicommandoremix.bin",
        "title": "Papi Commando Remix",
        "subtitle": "Arcade Run & Gun • Sega MD",
        "genre": "Run & Gun",
        "console_badge": "Mega Drive",
        "icon": "🎖️",
        "art_type": "tank",
        "palette": ("#15803d", "#052e16", "#fde047"),
        "url": f"{MD_BASE}/papicommandoremix.bin",
    },
    {
        "system": "megadrive",
        "filename": "mega-cheril-perils.bin",
        "title": "Mega Cheril Perils",
        "subtitle": "Mojon Twins • Sega MD",
        "genre": "Platformer / Action",
        "console_badge": "Mega Drive",
        "icon": "🦇",
        "art_type": "platform_hero",
        "palette": ("#be185d", "#500724", "#f9a8d4"),
        "url": f"{MD_BASE}/mega-cheril-perils.bin",
    },
    {
        "system": "megadrive",
        "filename": "projectmd.bin",
        "title": "Project MD",
        "subtitle": "High-Speed Sonic Style",
        "genre": "Speed Platformer",
        "console_badge": "Mega Drive",
        "icon": "🦔",
        "art_type": "mecha_cyber",
        "palette": ("#1d4ed8", "#172554", "#38bdf8"),
        "url": f"{MD_BASE}/projectmd.bin",
    },
    {
        "system": "megadrive",
        "filename": "oldtowers.bin",
        "title": "Old Towers",
        "subtitle": "Retro Sokoban / Castle",
        "genre": "Puzzle / Adventure",
        "console_badge": "Mega Drive",
        "icon": "🏰",
        "art_type": "tetris",
        "palette": ("#0284c7", "#082f49", "#fde047"),
        "url": f"{MD_BASE}/oldtowers.bin",
    },
    {
        "system": "megadrive",
        "filename": "ultimatetetris.bin",
        "title": "Ultimate Tetris",
        "subtitle": "Mega Drive Arcade Edition",
        "genre": "Block Puzzle",
        "console_badge": "Mega Drive",
        "icon": "🧱",
        "art_type": "tetris",
        "palette": ("#6d28d9", "#2e1065", "#38bdf8"),
        "url": f"{MD_BASE}/ultimatetetris.bin",
    },
    {
        "system": "megadrive",
        "filename": "downforce.bin",
        "title": "Downforce Racing",
        "subtitle": "Super GP Top-Down • MD",
        "genre": "Arcade Racing",
        "console_badge": "Mega Drive",
        "icon": "🏎️",
        "art_type": "racing",
        "palette": ("#dc2626", "#450a0a", "#facc15"),
        "url": f"{MD_BASE}/downforce.bin",
    },
    {
        "system": "megadrive",
        "filename": "xump2.bin",
        "title": "Xump 2",
        "subtitle": "Retroguru Space Puzzle",
        "genre": "Retro Puzzle",
        "console_badge": "Mega Drive",
        "icon": "🧩",
        "art_type": "puzzle_bubbles",
        "palette": ("#0891b2", "#083344", "#67e8f9"),
        "url": f"{MD_BASE}/xump2.bin",
    },
    {
        "system": "megadrive",
        "filename": "ohmummy.bin",
        "title": "Oh Mummy Genesis",
        "subtitle": "Pharaoh's Tombs • Sega MD",
        "genre": "Classic Maze",
        "console_badge": "Mega Drive",
        "icon": "🏺",
        "art_type": "treasure_adventure",
        "palette": ("#ca8a04", "#422006", "#fef08a"),
        "url": f"{MD_BASE}/ohmummy.bin",
    },
    {
        "system": "megadrive",
        "filename": "returntogenesis.bin",
        "title": "Return to Genesis",
        "subtitle": "Defender Style • Sega MD",
        "genre": "Shoot 'em Up",
        "console_badge": "Mega Drive",
        "icon": "🛸",
        "art_type": "spaceship",
        "palette": ("#4f46e5", "#1e1b4b", "#a5b4fc"),
        "url": f"{MD_BASE}/returntogenesis.bin",
    },
    {
        "system": "megadrive",
        "filename": "bareknuckleprincesss.bin",
        "title": "Bare Knuckle Princess",
        "subtitle": "Streets of Rage Style • MD",
        "genre": "Beat 'em Up",
        "console_badge": "Mega Drive",
        "icon": "👊",
        "art_type": "fighter_flame",
        "palette": ("#db2777", "#500724", "#fbcfe8"),
        "url": f"{MD_BASE}/bareknuckleprincesss.bin",
    },
    {
        "system": "megadrive",
        "filename": "goplanes.bin",
        "title": "GoPlanes",
        "subtitle": "Aerobatics & Air Combat",
        "genre": "Aerial Combat",
        "console_badge": "Mega Drive",
        "icon": "🛩️",
        "art_type": "jet",
        "palette": ("#0284c7", "#082f49", "#bae6fd"),
        "url": f"{MD_BASE}/goplanes.bin",
    },
    {
        "system": "megadrive",
        "filename": "grielsquest.bin",
        "title": "Griel's Quest",
        "subtitle": "Quest for the Sangraal • MD",
        "genre": "Puzzle / RPG",
        "console_badge": "Mega Drive",
        "icon": "🏆",
        "art_type": "rpg_magic",
        "palette": ("#059669", "#064e3b", "#fde047"),
        "url": f"{MD_BASE}/grielsquest.bin",
    },
]

EXTRA_ROMS_METADATA: Dict[str, Dict[str, Any]] = {
    "monsterfarmjump.sfc": {
        "system": "snes",
        "filename": "MonsterFarmJump.sfc",
        "title": "Monster Farm Jump",
        "subtitle": "16-Bit Platformer • SNES",
        "genre": "Platformer",
        "console_badge": "SNES",
        "icon": "👾",
        "art_type": "platform_hero",
        "palette": ("#16a34a", "#14532d", "#fde047"),
    },
    "snes_controller_test.sfc": {
        "system": "snes",
        "filename": "SNES_Controller_Test.sfc",
        "title": "SNES Controller Test",
        "subtitle": "Button Diagnostics • SNES",
        "genre": "Utility / Test",
        "console_badge": "SNES",
        "icon": "🎮",
        "art_type": "controller",
        "palette": ("#475569", "#1e293b", "#38bdf8"),
    },
}

ROM_METADATA_MAP: Dict[str, Dict[str, Any]] = {
    item["filename"].lower(): item for item in GAME_PACKS_CATALOG
}
ROM_METADATA_MAP.update(EXTRA_ROMS_METADATA)

ROM_TITLES_MAP: Dict[str, str] = {
    k: v["title"] for k, v in ROM_METADATA_MAP.items()
}


def _svg_escape(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _render_art_illustration(art_type: str, accent: str) -> str:
    """Retorna ilustração vetorial SVG temática para a capa do jogo."""
    if art_type == "tank":
        return f"""
        <circle cx="160" cy="175" r="58" fill="{accent}" opacity="0.18"/>
        <circle cx="205" cy="145" r="24" fill="#fbbf24" opacity="0.45"/>
        <polygon points="195,120 212,138 236,130 218,150 235,168 208,162 195,182 188,158 166,155 186,142" fill="#fde047" opacity="0.9"/>
        <rect x="92" y="196" width="126" height="30" rx="14" fill="#334155" stroke="#cbd5e1" stroke-width="2.5"/>
        <circle cx="112" cy="211" r="9" fill="#0f172a" stroke="{accent}" stroke-width="2.5"/>
        <circle cx="140" cy="211" r="9" fill="#0f172a" stroke="{accent}" stroke-width="2.5"/>
        <circle cx="168" cy="211" r="9" fill="#0f172a" stroke="{accent}" stroke-width="2.5"/>
        <circle cx="196" cy="211" r="9" fill="#0f172a" stroke="{accent}" stroke-width="2.5"/>
        <path d="M106 196 L118 164 L184 164 L196 196 Z" fill="#64748b" stroke="#f8fafc" stroke-width="2"/>
        <rect x="174" y="170" width="58" height="10" rx="4" transform="rotate(-12 174 170)" fill="#e2e8f0" stroke="#0f172a" stroke-width="2"/>
        <rect x="132" y="150" width="32" height="14" rx="5" fill="{accent}"/>
        """
    if art_type == "fighter_flame":
        return f"""
        <circle cx="160" cy="175" r="62" fill="{accent}" opacity="0.22"/>
        <path d="M160 106 C188 134 218 158 202 198 C192 222 168 232 160 232 C152 232 128 222 118 198 C102 158 132 134 160 106 Z" fill="#f97316" opacity="0.88"/>
        <path d="M160 128 C178 148 196 166 186 196 C178 214 160 220 160 220 C160 220 142 214 134 196 C124 166 142 148 160 128 Z" fill="#fde047"/>
        <circle cx="160" cy="182" r="26" fill="#0f172a" stroke="#ffffff" stroke-width="3"/>
        <text x="160" y="191" text-anchor="middle" fill="#fde047" font-family="Arial Black, sans-serif" font-weight="900" font-size="22">VS</text>
        """
    if art_type == "samurai":
        return f"""
        <circle cx="160" cy="175" r="56" fill="#e11d48" opacity="0.85"/>
        <line x1="96" y1="226" x2="224" y2="122" stroke="#f8fafc" stroke-width="6" stroke-linecap="round"/>
        <line x1="224" y1="226" x2="96" y2="122" stroke="#f8fafc" stroke-width="6" stroke-linecap="round"/>
        <rect x="108" y="198" width="18" height="6" transform="rotate(-39 108 198)" fill="#fde047"/>
        <rect x="194" y="198" width="18" height="6" transform="rotate(39 194 198)" fill="#fde047"/>
        <circle cx="160" cy="174" r="14" fill="#0f172a" stroke="#fde047" stroke-width="3"/>
        """
    if art_type == "jet":
        return f"""
        <circle cx="160" cy="175" r="58" fill="{accent}" opacity="0.2"/>
        <polygon points="160,110 176,162 224,184 176,192 168,224 160,212 152,224 144,192 96,184 144,162" fill="#e2e8f0" stroke="#38bdf8" stroke-width="2.5"/>
        <polygon points="160,128 167,165 153,165" fill="#0284c7"/>
        <polygon points="148,224 160,245 172,224" fill="#f97316"/>
        <line x1="120" y1="145" x2="120" y2="115" stroke="#fde047" stroke-width="3" stroke-dasharray="6,4"/>
        <line x1="200" y1="145" x2="200" y2="115" stroke="#fde047" stroke-width="3" stroke-dasharray="6,4"/>
        """
    if art_type == "spaceship":
        return f"""
        <circle cx="115" cy="130" r="3" fill="#ffffff" opacity="0.8"/>
        <circle cx="215" cy="140" r="2.5" fill="#fde047" opacity="0.9"/>
        <circle cx="105" cy="205" r="2" fill="#38bdf8" opacity="0.9"/>
        <circle cx="160" cy="175" r="54" fill="none" stroke="{accent}" stroke-width="2" stroke-dasharray="6,6" opacity="0.6"/>
        <polygon points="160,116 196,204 160,188 124,204" fill="#f8fafc" stroke="{accent}" stroke-width="3"/>
        <circle cx="160" cy="166" r="10" fill="#38bdf8"/>
        <polygon points="148,196 160,232 172,196" fill="#fde047" opacity="0.9"/>
        """
    if art_type == "puzzle_bubbles":
        return f"""
        <circle cx="132" cy="152" r="24" fill="#ec4899" stroke="#fbcfe8" stroke-width="2.5"/>
        <circle cx="124" cy="144" r="6" fill="#ffffff" opacity="0.65"/>
        <circle cx="184" cy="152" r="24" fill="#38bdf8" stroke="#bae6fd" stroke-width="2.5"/>
        <circle cx="176" cy="144" r="6" fill="#ffffff" opacity="0.65"/>
        <circle cx="158" cy="194" r="24" fill="#facc15" stroke="#fef08a" stroke-width="2.5"/>
        <circle cx="150" cy="186" r="6" fill="#ffffff" opacity="0.65"/>
        <circle cx="112" cy="198" r="18" fill="#22c55e" stroke="#bbf7d0" stroke-width="2"/>
        <circle cx="204" cy="198" r="18" fill="#a855f7" stroke="#e9d5ff" stroke-width="2"/>
        """
    if art_type == "tetris":
        return f"""
        <g stroke="#0f172a" stroke-width="2.5">
          <rect x="112" y="132" width="24" height="24" rx="4" fill="#ef4444"/>
          <rect x="136" y="132" width="24" height="24" rx="4" fill="#ef4444"/>
          <rect x="136" y="156" width="24" height="24" rx="4" fill="#ef4444"/>
          <rect x="160" y="156" width="24" height="24" rx="4" fill="#ef4444"/>
          <rect x="160" y="180" width="24" height="24" rx="4" fill="#38bdf8"/>
          <rect x="184" y="180" width="24" height="24" rx="4" fill="#38bdf8"/>
          <rect x="184" y="156" width="24" height="24" rx="4" fill="#38bdf8"/>
          <rect x="184" y="132" width="24" height="24" rx="4" fill="#38bdf8"/>
          <rect x="112" y="180" width="24" height="24" rx="4" fill="#facc15"/>
          <rect x="136" y="180" width="24" height="24" rx="4" fill="#facc15"/>
          <rect x="112" y="204" width="24" height="24" rx="4" fill="#facc15"/>
          <rect x="136" y="204" width="24" height="24" rx="4" fill="#facc15"/>
        </g>
        """
    if art_type == "disc_sport":
        return f"""
        <rect x="88" y="122" width="144" height="106" rx="10" fill="none" stroke="#38bdf8" stroke-width="2.5" opacity="0.45"/>
        <line x1="160" y1="122" x2="160" y2="228" stroke="#f8fafc" stroke-width="2" stroke-dasharray="5,5" opacity="0.6"/>
        <circle cx="160" cy="175" r="42" fill="#f97316" stroke="#fde047" stroke-width="4"/>
        <circle cx="160" cy="175" r="24" fill="#0f172a" stroke="#38bdf8" stroke-width="3"/>
        <circle cx="160" cy="175" r="9" fill="#fde047"/>
        """
    if art_type == "golf":
        return f"""
        <ellipse cx="160" cy="212" rx="68" ry="20" fill="#22c55e" opacity="0.85"/>
        <ellipse cx="176" cy="212" rx="10" ry="5" fill="#052e16"/>
        <line x1="176" y1="212" x2="176" y2="122" stroke="#f8fafc" stroke-width="3.5"/>
        <polygon points="176,122 218,136 176,150" fill="#ef4444"/>
        <circle cx="132" cy="182" r="16" fill="#f8fafc" stroke="#cbd5e1" stroke-width="2"/>
        <path d="M96 205 Q115 150 132 182" fill="none" stroke="#fde047" stroke-width="3" stroke-dasharray="4,4"/>
        """
    if art_type == "building_hammer":
        return f"""
        <rect x="108" y="122" width="104" height="108" rx="6" fill="#7c2d12" stroke="#fdba74" stroke-width="2.5"/>
        <rect x="122" y="136" width="20" height="22" fill="#38bdf8"/>
        <rect x="150" y="136" width="20" height="22" fill="#38bdf8"/>
        <rect x="178" y="136" width="20" height="22" fill="#fde047"/>
        <rect x="122" y="168" width="20" height="22" fill="#38bdf8"/>
        <rect x="150" y="168" width="20" height="22" fill="#fde047"/>
        <rect x="178" y="168" width="20" height="22" fill="#38bdf8"/>
        <rect x="146" y="198" width="28" height="32" fill="#451a03" stroke="#fde047" stroke-width="2"/>
        <rect x="180" y="114" width="38" height="18" rx="4" transform="rotate(25 180 114)" fill="#facc15" stroke="#ffffff" stroke-width="2"/>
        """
    if art_type == "treasure_adventure":
        return f"""
        <polygon points="160,118 222,220 98,220" fill="#d97706" opacity="0.35" stroke="#fde047" stroke-width="2"/>
        <rect x="118" y="164" width="84" height="54" rx="8" fill="#92400e" stroke="#fde047" stroke-width="3"/>
        <path d="M118 184 L202 184" stroke="#fde047" stroke-width="3"/>
        <rect x="150" y="176" width="20" height="18" rx="4" fill="#facc15" stroke="#0f172a" stroke-width="2"/>
        <polygon points="160,126 168,144 188,146 173,159 177,178 160,168 143,178 147,159 132,146 152,144" fill="#fde047"/>
        """
    if art_type == "karate":
        return f"""
        <circle cx="160" cy="175" r="56" fill="#f97316" opacity="0.85"/>
        <rect x="104" y="212" width="112" height="12" rx="4" fill="#0f172a"/>
        <path d="M112 146 L208 146" stroke="#0f172a" stroke-width="8" stroke-linecap="round"/>
        <path d="M122 164 L198 164" stroke="#0f172a" stroke-width="6" stroke-linecap="round"/>
        <line x1="134" y1="146" x2="134" y2="212" stroke="#0f172a" stroke-width="7"/>
        <line x1="186" y1="146" x2="186" y2="212" stroke="#0f172a" stroke-width="7"/>
        """
    if art_type == "mecha_cyber":
        return f"""
        <polygon points="160,114 212,144 212,204 160,234 108,204 108,144" fill="#0f172a" stroke="{accent}" stroke-width="3"/>
        <rect x="122" y="156" width="76" height="22" rx="6" fill="{accent}"/>
        <line x1="130" y1="167" x2="190" y2="167" stroke="#ffffff" stroke-width="3"/>
        <circle cx="160" cy="202" r="10" fill="#facc15"/>
        """
    if art_type == "rpg_magic":
        return f"""
        <circle cx="160" cy="175" r="56" fill="none" stroke="{accent}" stroke-width="2.5" stroke-dasharray="8,4"/>
        <polygon points="160,116 204,140 194,198 160,228 126,198 116,140" fill="#1e293b" stroke="#fde047" stroke-width="3"/>
        <line x1="160" y1="128" x2="160" y2="214" stroke="#fde047" stroke-width="4"/>
        <line x1="136" y1="154" x2="184" y2="154" stroke="#fde047" stroke-width="4"/>
        <circle cx="160" cy="154" r="9" fill="{accent}" stroke="#ffffff" stroke-width="2"/>
        """
    if art_type == "racing":
        return f"""
        <path d="M102 224 L138 124 L182 124 L218 224 Z" fill="#1e293b" stroke="#cbd5e1" stroke-width="2.5"/>
        <line x1="160" y1="128" x2="160" y2="220" stroke="#fde047" stroke-width="4" stroke-dasharray="10,8"/>
        <rect x="136" y="160" width="48" height="42" rx="10" fill="#ef4444" stroke="#ffffff" stroke-width="2.5"/>
        <rect x="144" y="170" width="32" height="14" rx="4" fill="#38bdf8"/>
        """
    if art_type == "controller":
        return f"""
        <rect x="92" y="142" width="136" height="68" rx="34" fill="#cbd5e1" stroke="#f8fafc" stroke-width="3"/>
        <circle cx="192" cy="176" r="22" fill="#475569"/>
        <circle cx="192" cy="162" r="5" fill="#3b82f6"/>
        <circle cx="178" cy="176" r="5" fill="#22c55e"/>
        <circle cx="206" cy="176" r="5" fill="#ef4444"/>
        <circle cx="192" cy="190" r="5" fill="#facc15"/>
        <rect x="122" y="164" width="8" height="24" fill="#1e293b"/>
        <rect x="114" y="172" width="24" height="8" fill="#1e293b"/>
        """
    # Default: platform_hero
    return f"""
    <rect x="96" y="204" width="128" height="22" rx="8" fill="#22c55e" stroke="#bbf7d0" stroke-width="2"/>
    <rect x="114" y="146" width="28" height="28" rx="5" fill="#f59e0b" stroke="#fef08a" stroke-width="2.5"/>
    <text x="128" y="167" text-anchor="middle" fill="#ffffff" font-family="Arial Black, sans-serif" font-weight="900" font-size="18">?</text>
    <polygon points="178,128 186,146 206,148 191,161 195,180 178,170 161,180 165,161 150,148 170,146" fill="#fde047" stroke="#ffffff" stroke-width="1.5"/>
    """


def build_rom_cover_svg(
    title: str,
    subtitle: str,
    genre: str,
    console_badge: str,
    art_type: str,
    palette: Tuple[str, str, str],
) -> Tuple[str, str]:
    """
    Gera arte de capa estilizada em SVG (320x420) 100% offline-ready e retorna (svg_raw, data_uri).
    """
    c1, c2, accent = palette
    badge_up = (console_badge or "RETRO").upper()
    if badge_up == "SNES":
        header_lbl = "SUPER NINTENDO • 16-BIT"
        header_bg = "#dc2626"
    elif badge_up == "NEOGEO":
        header_lbl = "SNK NEOGEO • MVS ARCADE"
        header_bg = "#d97706"
    elif badge_up == "MEGA DRIVE":
        header_lbl = "SEGA MEGA DRIVE • 16-BIT"
        header_bg = "#2563eb"
    else:
        header_lbl = "MAME • CLASSIC ARCADE"
        header_bg = "#7c3aed"

    clean_title = (title or "Retro Game").strip()
    if len(clean_title) > 22:
        words = clean_title.split()
        mid = max(1, len(words) // 2)
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        if len(line2) > 22:
            line2 = line2[:20] + "…"
        title_svg = f"""
        <text x="160" y="286" text-anchor="middle" fill="#ffffff" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-weight="900" font-size="20" letter-spacing="0.4">{_svg_escape(line1)}</text>
        <text x="160" y="311" text-anchor="middle" fill="{accent}" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-weight="900" font-size="19" letter-spacing="0.4">{_svg_escape(line2)}</text>
        """
    else:
        font_sz = 23 if len(clean_title) <= 15 else 19.5
        title_svg = f"""
        <text x="160" y="298" text-anchor="middle" fill="#ffffff" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-weight="900" font-size="{font_sz}" letter-spacing="0.5">{_svg_escape(clean_title)}</text>
        """

    illustration = _render_art_illustration(art_type, accent)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 420" width="320" height="420">'
        f"<defs>"
        f'<linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{c1}"/>'
        f'<stop offset="65%" stop-color="{c2}"/>'
        f'<stop offset="100%" stop-color="#070a12"/>'
        f"</linearGradient>"
        f"</defs>"
        f'<rect width="320" height="420" rx="22" fill="url(#bg)"/>'
        f'<rect x="6" y="6" width="308" height="408" rx="18" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>'
        f'<rect x="16" y="16" width="288" height="32" rx="10" fill="{header_bg}"/>'
        f'<text x="160" y="37" text-anchor="middle" fill="#ffffff" font-family="system-ui, sans-serif" font-weight="900" font-size="12.5" letter-spacing="1.2">{_svg_escape(header_lbl)}</text>'
        f'<rect x="24" y="62" width="272" height="190" rx="16" fill="rgba(7, 10, 18, 0.52)" stroke="rgba(255,255,255,0.16)" stroke-width="1.5"/>'
        f"{illustration}"
        f"{title_svg}"
        f'<text x="160" y="338" text-anchor="middle" fill="#cbd5e1" font-family="system-ui, sans-serif" font-weight="700" font-size="12">{_svg_escape(subtitle)}</text>'
        f'<rect x="60" y="356" width="200" height="32" rx="16" fill="rgba(9, 13, 22, 0.78)" stroke="{accent}" stroke-width="1.5"/>'
        f'<text x="160" y="377" text-anchor="middle" fill="{accent}" font-family="system-ui, sans-serif" font-weight="800" font-size="12.5" letter-spacing="0.5">{_svg_escape(genre)}</text>'
        f"</svg>"
    )
    data_uri = "data:image/svg+xml;utf8," + urllib.parse.quote(svg, safe="(),/:!~*' ")
    return svg, data_uri


def get_rom_metadata(system: str, filename: str) -> Dict[str, Any]:
    """Retorna metadados enriquecidos + arte de capa SVG offline-ready para qualquer ROM."""
    fname_low = (filename or "").strip().lower()
    sys_clean = (system or "snes").strip().lower()
    entry = ROM_METADATA_MAP.get(fname_low)

    if entry:
        title = entry["title"]
        subtitle = entry.get("subtitle") or f"{entry.get('console_badge', sys_clean.upper())} Classic"
        genre = entry.get("genre") or "Retro Arcade"
        console_badge = entry.get("console_badge") or (
            "SNES" if sys_clean == "snes" else "Mega Drive" if sys_clean == "megadrive" else "NeoGeo"
        )
        icon = entry.get("icon") or "🎮"
        art_type = entry.get("art_type") or "platform_hero"
        palette = entry.get("palette") or ("#2563eb", "#0f172a", "#38bdf8")
        is_bios = bool(entry.get("is_bios"))
    else:
        stem = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").strip()
        title = stem.title() if stem else filename
        if sys_clean == "snes":
            console_badge = "SNES"
            subtitle = "Super Nintendo • 16-Bit"
            genre = "SNES Classic"
            icon = "🍄"
            art_type = "platform_hero"
            palette = ("#dc2626", "#450a0a", "#fde047")
        elif sys_clean == "megadrive":
            console_badge = "Mega Drive"
            subtitle = "Sega Mega Drive • 16-Bit"
            genre = "Mega Drive Classic"
            icon = "🦔"
            art_type = "mecha_cyber"
            palette = ("#2563eb", "#172554", "#38bdf8")
        else:
            console_badge = "Arcade"
            subtitle = "Arcade • Coin-Op"
            genre = "Classic Arcade"
            icon = "🕹️"
            art_type = "fighter_flame"
            palette = ("#d97706", "#451a03", "#fde047")
        is_bios = fname_low == "neogeo.zip"

    cover_svg, cover_url = build_rom_cover_svg(
        title=title,
        subtitle=subtitle,
        genre=genre,
        console_badge=console_badge,
        art_type=art_type,
        palette=palette,
    )
    return {
        "title": title,
        "subtitle": subtitle,
        "genre": genre,
        "console_badge": console_badge,
        "icon": icon,
        "accent_color": palette[0],
        "cover_svg": cover_svg,
        "cover_url": cover_url,
        "is_bios": is_bios,
    }


def download_single_rom(entry: Dict[str, Any], force: bool = False) -> Tuple[str, bool, str]:
    """Baixa uma ROM do catálogo para `roms/<system>/<filename>`."""
    system = entry["system"]
    filename = entry["filename"]
    url = entry["url"]
    dest_dir = ROMS_DIR / system
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    if dest_path.exists() and dest_path.stat().st_size > 1024 and not force:
        return (filename, True, "cached")

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HybridBox-GamePack/1.0"
            },
        )
        tmp_path = dest_dir / f".{filename}.part"
        with urllib.request.urlopen(req, timeout=45.0) as resp, open(tmp_path, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)
        if tmp_path.exists() and tmp_path.stat().st_size > 512:
            tmp_path.replace(dest_path)
            return (filename, True, "downloaded")
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return (filename, False, "empty file")
    except Exception as exc:
        return (filename, False, str(exc))


def find_adb_binary() -> Optional[str]:
    adb_bin = shutil.which("adb")
    if adb_bin:
        return adb_bin
    for cand in (
        r"C:\src\Android\Sdk\platform-tools\adb.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe"
        ),
    ):
        if cand and os.path.exists(cand):
            return cand
    return None


def sync_roms_to_phone(
    systems: Optional[List[str]] = None,
    ssh_host: str = "",
    ssh_port: int = 8022,
    ssh_user: str = "",
) -> Dict[str, Any]:
    """
    Sincroniza as pastas `roms/{snes,mame,megadrive}` para `/sdcard/ROMs/{snes,mame,megadrive}`
    e `/sdcard/MAME4droid/roms` no Xiaomi Redmi Note 8 Pro (via ADB ou SCP/SSH).
    """
    target_systems = systems or ["snes", "mame", "megadrive"]
    if not os.path.exists("/sdcard") and (not ssh_host or not ssh_user):
        try:
            if str(BASE_DIR) not in sys.path:
                sys.path.insert(0, str(BASE_DIR))
            from backend.android_controller import AndroidController

            ctrl = AndroidController()
            ssh_host = ssh_host or ctrl.discover_phone_ip()
            ssh_user = ssh_user or ctrl.discover_ssh_user()
        except Exception:
            pass
    ssh_host = ssh_host or os.environ.get("HYBRIDBOX_PHONE_IP", "") or os.environ.get("HYBRIDBOX_SSH_HOST", "hybridbox.local")
    ssh_user = ssh_user or os.environ.get("HYBRIDBOX_SSH_USER", "termux")

    # 1. Caso já esteja rodando diretamente dentro do próprio celular (Termux)
    if os.path.exists("/sdcard"):
        copied = 0
        for sys_name in target_systems:
            src_dir = ROMS_DIR / sys_name
            dst_dir = Path(f"/sdcard/ROMs/{sys_name}")
            dst_dir.mkdir(parents=True, exist_ok=True)
            if not src_dir.exists():
                continue
            for f in src_dir.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    shutil.copy2(f, dst_dir / f.name)
                    copied += 1
                    if sys_name == "mame":
                        mame4_dir = Path("/sdcard/MAME4droid/roms")
                        mame4_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, mame4_dir / f.name)
        return {"ok": True, "method": "local-sdcard", "files_synced": copied}

    # 2. Sincroniza via ADB (USB ou Wi-Fi TCP:5555)
    adb_bin = find_adb_binary()
    if adb_bin:
        try:
            subprocess.run(
                [adb_bin, "connect", f"{ssh_host}:5555"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2.5,
            )
            devs = subprocess.check_output([adb_bin, "devices"], text=True, timeout=3.0)
            serials = [
                line.split()[0]
                for line in devs.splitlines()[1:]
                if "\tdevice" in line
            ]
            if serials:
                serial = f"{ssh_host}:5555" if f"{ssh_host}:5555" in serials else serials[0]
                subprocess.run(
                    [
                        adb_bin,
                        "-s",
                        serial,
                        "shell",
                        "mkdir -p /sdcard/ROMs/snes /sdcard/ROMs/mame /sdcard/ROMs/megadrive /sdcard/MAME4droid/roms",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5.0,
                )
                synced_files = 0
                for sys_name in target_systems:
                    src_dir = ROMS_DIR / sys_name
                    if not src_dir.exists():
                        continue
                    files = [f for f in src_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
                    if not files:
                        continue
                    # Envia todos os arquivos da pasta para /sdcard/ROMs/<sys_name>/
                    for f in files:
                        res = subprocess.run(
                            [adb_bin, "-s", serial, "push", str(f), f"/sdcard/ROMs/{sys_name}/{f.name}"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=45.0,
                        )
                        if res.returncode == 0:
                            synced_files += 1
                    if sys_name == "mame":
                        subprocess.run(
                            [
                                adb_bin,
                                "-s",
                                serial,
                                "shell",
                                "cp -f /sdcard/ROMs/mame/*.zip /sdcard/MAME4droid/roms/ 2>/dev/null || true",
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=20.0,
                        )
                if synced_files > 0:
                    return {"ok": True, "method": f"adb ({serial})", "files_synced": synced_files}
        except Exception:
            pass

    # 3. Fallback via Wi-Fi SSH / SCP (porta 8022)
    scp_bin = shutil.which("scp")
    ssh_bin = shutil.which("ssh")
    if scp_bin and ssh_bin:
        try:
            subprocess.run(
                [
                    ssh_bin,
                    "-p",
                    str(ssh_port),
                    "-o",
                    "StrictHostKeyChecking=no",
                    f"{ssh_user}@{ssh_host}",
                    "mkdir -p /sdcard/ROMs/snes /sdcard/ROMs/mame /sdcard/ROMs/megadrive /sdcard/MAME4droid/roms ~/hybridbox-remote-pwa/roms/snes ~/hybridbox-remote-pwa/roms/mame ~/hybridbox-remote-pwa/roms/megadrive",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=6.0,
            )
            synced_files = 0
            for sys_name in target_systems:
                src_dir = ROMS_DIR / sys_name
                if not src_dir.exists():
                    continue
                files = [str(f) for f in src_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
                if not files:
                    continue
                res = subprocess.run(
                    [
                        scp_bin,
                        "-P",
                        str(ssh_port),
                        "-o",
                        "StrictHostKeyChecking=no",
                        *files,
                        f"{ssh_user}@{ssh_host}:/sdcard/ROMs/{sys_name}/",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=90.0,
                )
                if res.returncode == 0:
                    synced_files += len(files)
            subprocess.run(
                [
                    ssh_bin,
                    "-p",
                    str(ssh_port),
                    "-o",
                    "StrictHostKeyChecking=no",
                    f"{ssh_user}@{ssh_host}",
                    "cp -f /sdcard/ROMs/mame/*.zip /sdcard/MAME4droid/roms/ 2>/dev/null || true; "
                    "cp -rf /sdcard/ROMs/* ~/hybridbox-remote-pwa/roms/ 2>/dev/null || true",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=25.0,
            )
            return {"ok": True, "method": f"wifi-scp ({ssh_host}:{ssh_port})", "files_synced": synced_files}
        except Exception as exc:
            return {"ok": False, "method": "wifi-scp", "error": str(exc), "files_synced": 0}

    return {"ok": False, "method": "none", "files_synced": 0}


def install_packs(pack_id: str = "all", max_workers: int = 8) -> Dict[str, Any]:
    """Baixa os packs solicitados ('all', 'snes', 'mame', 'megadrive') e sincroniza com o celular."""
    pack_clean = (pack_id or "all").strip().lower()
    if pack_clean in ("all", "todos", ""):
        selected = GAME_PACKS_CATALOG
        systems = ["snes", "mame", "megadrive"]
    else:
        selected = [g for g in GAME_PACKS_CATALOG if g["system"] == pack_clean]
        systems = [pack_clean]

    downloaded = []
    cached = []
    failed = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(download_single_rom, entry): entry for entry in selected}
        for fut in concurrent.futures.as_completed(futures):
            fname, ok, status = fut.result()
            if ok:
                if status == "downloaded":
                    downloaded.append(fname)
                else:
                    cached.append(fname)
            else:
                failed.append({"filename": fname, "error": status})

    sync_res = sync_roms_to_phone(systems=systems)
    total_ok = len(downloaded) + len(cached)
    return {
        "ok": total_ok > 0,
        "pack_id": pack_clean,
        "total_ready": total_ok,
        "downloaded_count": len(downloaded),
        "cached_count": len(cached),
        "failed_count": len(failed),
        "failed": failed,
        "sync": sync_res,
        "message": (
            f"✅ Game pack installed! {total_ok} games ready "
            f"({len(downloaded)} newly downloaded, {len(cached)} cached) and synced "
            f"with the phone at /sdcard/ROMs ({sync_res.get('method', 'local')})!"
        ),
    }


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"[*] Baixando e instalando pack de jogos: {target} ...")
    result = install_packs(target)
    print(result["message"])
    if result["failed"]:
        print(f"[!] Falhas ({len(result['failed'])}): {result['failed']}")
