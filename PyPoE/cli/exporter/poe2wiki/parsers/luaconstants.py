"""
Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/poe2wiki/parsers/luaconstants.py              |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Mefisto1029                                                      |
+----------+------------------------------------------------------------------+

Description
===============================================================================

Global constants the lua exporter such as lists of items to exclude from exporting.

Agreement
===============================================================================

See PyPoE/LICENSE

Documentation
===============================================================================
"""

# =============================================================================
# Imports
# =============================================================================

# Python

# 3rd-party

# self

# =============================================================================
# Globals
# =============================================================================

# Also will be used by process_keywords in PyPoE/cli/exporter/poe2wiki/parser.py
KEYWORD_LINK_MAP = {
    # Keyword:
    #   default (string): Replace the default link that is the title by default.
    #   links (list): Optional links can be either strings or tuples ("text to check", "link").
    #   A tuple is useful for linking to sections on a page.
    #   no_link (bool): Wheter keyword should not be linked to anywhere.
    # "keywordId": {
    #    "default": "",
    #    "links": [
    #    ]
    # },
    "Abyssalify": {
        "default": "Desecrated modifier",
        "links": [
            "Desecrate",
        ],
    },
    "Accuracy": {
        "links": [
            "Accurate",
        ],
    },
    "Ailments": {
        "default": "Ailment",
    },
    "AilmentSpread": {
        "default": "Spread",
    },
    "AilmentThreshold": {
        "default": "Ailment",
        "links": [
            "Ailment Threshold",
        ],
    },
    "Allies": {
        "default": "Ally",
        "links": [
            "Allied",
        ],
    },
    "AncestralBoost": {
        "links": [
            "Ancestrally Boosted",
        ],
    },
    "ArcaneSurge": {},
    "Archon": {
        "default": "Archon",
    },
    "ArmourBreak": {
        "links": [
            "Armour Break",
            "Armour Broken",
            "Break Armour",
            "Breaks Armour",
            "Breaking Armour",
            "Broken Armour",
            "Fully Armour Broken",
            "Fully Break",
            "Fully Broken Armour",
            "Fully Breaking Armour",
            "Fully Broken",
            "Break",
        ],
    },
    "ArmourOverbreak": {
        "default": "Armour Break",
    },
    "ArmouredShield": {
        "default": "Shield",
        "links": [
            "Armoured Shield",
        ],
    },
    "ArtificersOrb": {},
    "Attributes": {
        "default": "Attribute",
        "links": [
            "attribute",
            "Attributes",
            "attributes",
        ],
    },
    "AzmeriSpirit": {
        "default": "Azmerian wisp",
        "links": [
            "Azmeri Spirit",
        ],
    },
    "Bleeding": {
        "default": "Bleed",
        "links": [
            "Bleeding",
        ],
    },
    "BloodLoss": {},
    "BlueFlamesOfChayula": {
        "default": "Blue Flame of Chayula",
        "links": [
            "Blue Flames of Chayula",
        ],
    },
    "BooleanDamageRoll": {
        "default": "Damage",
    },
    "BrokenStance": {},
    "BuffEffect": {
        "default": "Buff",
    },
    "BuffMagnitude": {
        "default": "Magnitude",
    },
    "Burning": {
        "default": "Ignite",
        "links": [
            "Burn",
            "Burning",
        ],
    },
    "Channelling": {
        "links": [
            "Channelled",
        ],
    },
    "ChaosOrb": {},
    "Charges": {
        "default": "Charge",
        "links": [
            "Charges",
            "Endurance Charge",
            "Endurance Charges",
            "Frenzy Charge",
            "Frenzy Charges",
            "Power Charge",
            "Power Charges",
        ],
    },
    "ChilledGround": {},
    "Conditional": {
        "default": "Conditional",
        "links": [
            "Condition",
        ],
    },
    "ConsecratedGround": {},
    "ContainsAbyss": {},
    "ContainsBreach": {},
    "ContainsDelirium": {},
    "ContainsExpedition": {},
    "ContainsIrradiated": {},
    "ContainsRitual": {},
    "CooldownRecovery": {
        "default": "Cooldown",
        "links": [
            "Cooldown Recovery Rate",
            "Cooldowns Recover",
        ],
    },
    "CorruptedBlood": {},
    "Conversion": {
        "default": "Damage conversion",
        "links": [
            "Damage Conversion",
        ],
    },
    "Critical": {
        "default": "Critical hit",
        "links": [
            "Critical",
            "Critical Hit",
            "Critical Hit Chance",
            "Critically Hit",
            "Critically hit",
        ],
    },
    "CriticalDamageBonus": {},
    "CriticalWeakness": {},
    "CrushingBlow": {
        "links": [
            "Crushing Blow",
        ],
    },
    "CullingStrike": {
        "default": "Culling strike",
        "links": [
            "Cull",
            "Culling Strike",
        ],
    },
    "DamageTypes": {
        "default": "Damage type",
        "links": [
            "Damage Type",
            "Damage Types",
            "Damage types",
        ],
    },
    "DamagingAilments": {
        "links": [
            "Damaging Ailment",
        ],
    },
    "Defences": {
        "default": "Defence",
        "links": [
            "Defences",
        ],
    },
    "DetonationTime": {
        "links": [
            "Detonate",
            "Detonation",
        ],
    },
    "DistilledEmotion": {
        "default": "Liquid emotion",
        "links": [
            "Liquid Emotion",
            "Liquid Emotions",
        ],
    },
    "DualWield": {
        "default": "Dual wielding",
        "links": [
            "Dual Wielding",
        ],
    },
    "EasyTargetDebuff": {},
    "ElementalAilments": {
        "default": "Elemental ailment",
        "links": [
            "Ailment",
            "Elemental Ailment",
        ],
    },
    "ElementalDamage": {
        "default": "Elemental damage",
        "links": [
            "Elemental",
            "Elemental Damage",
            "Elemental Hit Damage",
        ],
    },
    "ElementalGround": {
        "default": "Ground surface",
        "links": [
            "Elemental Ground Surfaces",
        ],
    },
    "ElementalInfusion": {
        "default": "Infusion",
        "links": [
            "Elemental Infusion",
            "Infused",
        ],
    },
    "Empowered": {
        "default": "Empowered skill",
        "links": [
            "Empower",
            "Empowered",
            "Empowered Skills",
        ],
    },
    "EnergyShield": {},
    "EnergyShieldLeech": {
        "default": "Energy shield leech",
        "links": [
            "Energy Shield Leech",
            "Energy Shield leech",
            "Leech Energy Shield",
            "Leech",
        ],
    },
    "EquipArmour": {
        "default": "Armour (equipment)",
        "links": [
            "Equippable Armour",
            "Equippable Armours",
        ],
    },
    "ESRecharge": {
        "default": "Energy Shield",
        "links": [
            "Energy Shield Recharge",
        ],
    },
    "ESRechargeRate": {
        "default": "Energy Shield",
        "links": [
            "Energy Shield Recharge Rate",
        ],
    },
    "Essence": {
        "default": "Essence (encounter)",
    },
    "Evasion": {
        "links": [
            "Evasion Rating",
        ],
    },
    "ExpectedKnockback": {
        "links": [
            "Expected knockback",
        ],
    },
    "Exposure": {},
    "FasterESRechargeStart": {
        "default": "Energy Shield",
        "links": [
            "Faster Start of Energy Shield Recharge",
        ],
    },
    "FinalStrike": {},
    "Flask": {
        "default": "Flask",
        "links": [
            "flask",
            "Flasks",
            "flasks",
        ],
    },
    "FlameArchon": {
        "default": "Archon",
        "links": [
            "Flame Archon",
        ],
    },
    "FlamesOfChayula": {
        "links": [
            "Flame Of Chayula",
            "Flames Of Chayula",
            "Flames of Chayula",
        ],
    },
    "ForksCrit": {
        "default": "Tangletongue",  # unique
    },
    "Freeze": {
        "links": [
            "Freezing",
        ],
    },
    "HeavyStun": {
        "links": [
            "Heavily Stun",
            "Heavily Stuned",
        ],
    },
    "HeavyStunPlayer": {
        "default": "Heavy Stun",
        "links": [
            "Heavily Stun",
            "Heavily Stuned",
        ],
    },
    "HitDamage": {
        "default": "Hit",
        "links": [
            "Damaging Hit",
            "Damaging hit",
            "Hit Damage",
        ],
    },
    "IceArchon": {
        "default": "Archon",
        "links": [
            "Ice Archon",
        ],
    },
    "IceCrystals": {
        "default": "Ice Crystal",
        "links": [
            "Ice Crystals",
        ],
    },
    "IceFragment": {
        "links": [
            "Ice Fragment",
        ],
    },
    "Ignite": {
        "links": [
            "Ignited",
            "Igniting",
        ],
    },
    "IgnitedGround": {},
    "IgnoreResistances": {},
    "Invoke": {
        "default": "Invocation",
        "links": [
            "Invoke",
            "Invoking",
        ],
    },
    "ItemDefences": {
        "default": "Defences",
    },
    "ItemRarity": {
        "default": "Rarity",
        "links": [
            "Normal",
            "Rare",
            "Magic",
            "Unique",
        ],
    },
    "JaggedGround": {},
    "KillingBlow": {
        "default": "Kill",
        "links": [
            "Killing Blow",
            "Killing Blows",
        ],
    },
    "Knockback": {
        "links": [
            "Knock Back",
            "Knock back",
            "Knocking Back",
        ],
    },
    "LifeLeech": {
        "links": [
            "Leech",
            "Leech Life",
        ],
    },
    "LifeLoss": {},
    "LightningAilment": {
        "default": "Lightning Ailment",
        "links": [
            "Lightning ailment",
            "Lightning Ailments",
            "Lightning ailments",
        ],
    },
    "LightningArchon": {
        "default": "Archon",
        "links": [
            "Lightning Archon",
        ],
    },
    "LightStun": {},
    "LowLife": {},
    "ManaLeech": {
        "links": [
            "Leech Mana",
            "Leech",
        ],
    },
    "MarkofAbyssalLord": {},
    "MartialWeapon": {
        "links": [
            "Martial Weapon",
            "Martial weapon",
            "martial weapon",
            "Martial weapons",
            "martial weapons",
        ],
    },
    "MaximumResistances": {
        "links": [
            "Maximum Resistance",
            "Maximum Fire Resistance",
            "Maximum Cold Resistance",
            "Maximum Lightning Resistance",
            "Maximum Chaos Resistance",
        ],
    },
    "MinionDeath": {
        "default": "Minion death",
    },
    "MoltenFissure": {},
    "MonsterCategory": {
        "default": "Monster category",
        "links": [
            "Monster Category",
        ],
    },
    "MonsterModifiers": {
        "default": "Monster modifier",
        "links": [
            "Monster Modifier",
            "Monster Modifiers",
            "Monster modifiers",
        ],
    },
    "NonDamagingAilments": {
        "links": [
            "Non-Damaging Ailment",
        ],
    },
    "OilGround": {
        "default": "Oiled ground",
        "links": [
            "Oil Ground",
            "Oil ground",
        ],
    },
    "OrbOfAlchemy": {},
    "OrbOfAlteration": {},
    "OrbOfChance": {},
    "OrbOfTransmutation": {},
    "OvercapChance": {
        "default": "Overcap chance",
        "links": [
            "Overcap Chance",
        ],
    },
    "OvercappedBlock": {
        "links": [
            "Overcapped Block",
        ],
    },
    "ParriedDebuff": {
        "default": "Parry",
        "links": [
            "Parried",
            "Parried Debuff",
        ],
    },
    "Penetration": {
        "links": [
            "Resistance Penetration",
        ],
    },
    "PerfectionBuff": {},
    "PerfectTiming": {
        "links": [
            "Perfectly Timing",
        ],
    },
    "Physical": {
        "default": "Physical",
        "links": [
            "Physical Damage",
            "Physical damage",
        ],
    },
    "PlayerPossessed": {
        "default": "Azmerian wisp",
    },
    "PrecursorTablet": {
        "default": "Precursor tablet",
        "links": [
            "Precursor Tablet",
            "Precursor Tablets",
            "Precursor tablets",
        ],
    },
    "PrimedElectrocution": {},
    "PrimedFreeze": {},
    "PrimedPin": {},
    "PrimedStun": {},
    "PurpleFlamesOfChayula": {
        "links": [
            "Purple Flames of Chayul",
        ],
    },
    "Quality": {
        "links": [
            "quality",
        ],
    },
    "RageLeech": {
        "links": [
            "Leech Rage",
            "Leech",
        ],
    },
    "Rarity": {
        "links": [
            "Normal",
            "Rare",
            "Magic",
            "Unique",
        ],
    },
    "RegalOrb": {},
    "RedFlamesOfChayula": {
        "default": "Red Flame of Chayula",
        "links": [
            "Red Flames of Chayula",
        ],
    },
    "Resistances": {
        "default": "Resistance",
        "links": [
            "Resistances",
            "Elemental Resistance",
            "Elemental Resistances",
            "Fire Resistance",
            "Cold Resistance",
            "Lightning Resistance",
            "Chaos Resistance",
        ],
    },
    "ResistedBy": {
        "default": "Resistance",
    },
    "Resonance": {
        "default": "Resonance (buff)",
    },
    "Reviving": {},
    "RivenArmour": {},
    "RogueExile": {
        "links": [
            "Rogue Exiles",
        ],
    },
    "RunicInscription": {},
    "Sacrifice": {
        "default": "Sacrifice (keyword)",
    },
    "ShockedGround": {},
    "SkillSpeed": {},
    "SoulEater": {},
    "SoulEaterMonster": {
        "default": "Soul Eater",
    },
    "SpiritOfTheBearPossessedPlayer": {
        "default": "Azmerian wisp",
    },
    "SpiritOfTheBoarPossessedPlayer": {
        "default": "Azmerian wisp",
    },
    "SpiritOfTheCatPossessedPlayer": {
        "default": "Azmerian wisp",
    },
    "SpiritOfTheOwlPossessedPlayer": {
        "default": "Azmerian wisp",
    },
    "SpiritOfTheOxPossessedPlayer": {
        "default": "Azmerian wisp",
    },
    "SpiritOfTheSerpentPossessedPlayer": {
        "default": "Azmerian wisp",
    },
    "SpiritOfTheStagPossessedPlayer": {
        "default": "Azmerian wisp",
    },
    "SpiritOfTheWolfPossessedPlayer": {
        "default": "Azmerian wisp",
    },
    "StatConversion": {
        "default": "Stat conversion",
        "links": [
            "Stat Conversion",
        ],
    },
    "StatGain": {
        "default": "Gain",  # Should be different
    },
    "StunThreshold": {
        "default": "Stun Threshold",
    },
    "SunderedArmour": {
        "default": "Sundered Armour",
    },
    "ThornsRetaliation": {
        "default": "Thorns",
        "links": [
            "Retaliate with Thorns",
        ],
    },
    "Total": {
        "no_link": True,
    },
    "TotalPlus": {
        "no_link": True,
    },
    "UnboundFury": {},
    "UnholyMight": {},
    "Warcry": {
        "links": [
            "Warcries",
        ],
    },
    "WeaponSetPassiveSkillPoints": {},
    "WeaponSets": {
        "default": "Weapon set",
        "links": [
            "Weapon Set",
            "Weapon Sets",
        ],
    },
    "Wells": {
        "default": "Well",
        "links": [
            "Wells",
        ],
    },
    "Withered": {
        "links": [
            "Wither",
        ],
    },
    "WitheringGround": {},
}
