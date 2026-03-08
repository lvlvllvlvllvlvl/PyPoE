class CustomizedField:
    def __init__(self, enum: str = None):
        self.enum = enum


custom_attributes = {
    "AlternatePassiveSkills.dat": {
        "PassiveType": CustomizedField(
            enum="PASSIVE_SKILL_SIZES",
        ),
    },
    "BaseItemTypes.dat": {
        "ModDomainsKey": CustomizedField(
            enum="MOD_DOMAIN",
        ),
    },
    "BestiaryRecipes.dat": {
        "GameMode": CustomizedField(
            enum="GAME_MODES",
        ),
    },
    "BestiaryRecipeComponent.dat": {
        "RarityKey": CustomizedField(
            enum="RARITY",
        ),
    },
    "BetrayalUpgrades.dat": {
        "BetrayalUpgradeSlotsKey": CustomizedField(
            enum="BETRAYAL_UPGRADE_SLOTS",
        ),
    },
    "DelveUpgrades.dat": {
        "DelveUpgradeTypeKey": CustomizedField(
            enum="DELVE_UPGRADE_TYPE",
        ),
    },
    "Maps.dat": {
        "MapGeneration": CustomizedField(
            enum="MAP_GENERATION",
        ),
    },
    "Mods.dat": {
        "Domain": CustomizedField(
            enum="MOD_DOMAIN",
        ),
        "GenerationType": CustomizedField(
            enum="MOD_GENERATION_TYPE",
        ),
        "GameMode": CustomizedField(
            enum="GAME_MODES",
        ),
    },
    "PassiveSkills.dat": {
        "SkillType": CustomizedField(
            enum="PASSIVE_SKILL_TYPES",
        ),
    },
    "Words.dat": {
        "Wordlist": CustomizedField(
            enum="WORDLISTS",
        ),
    },
}
