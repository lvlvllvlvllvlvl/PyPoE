from PyPoE.poe.file.specification.fields import VirtualField

virtual_fields = {
    'CraftingBenchOptions.dat': [
        VirtualField(
            name='Cost',
            fields=('Cost_BaseItemTypes', 'Cost_Values'),
            zip=True,
        ),
    ],
    'DelveUpgrades.dat': [
        VirtualField(
            name='Stats',
            fields=('StatsKeys', 'StatValues'),
            zip=True,
        ),
    ],
    'GrantedEffectsPerLevel.dat': [
        VirtualField(
            name='Costs',
            fields=('CostTypes', 'CostAmounts'),
            zip=True,
        ),
    ],
    'Mods.dat': [
        VirtualField(
            name='SpawnWeight',
            fields=('SpawnWeight_TagsKeys', 'SpawnWeight_Values'),
            zip=True,
        ),
        VirtualField(
            name='Stat1',
            fields=('StatsKey1', 'Stat1Min', 'Stat1Max'),
        ),
        VirtualField(
            name='Stat2',
            fields=('StatsKey2', 'Stat2Min', 'Stat2Max'),
        ),
        VirtualField(
            name='Stat3',
            fields=('StatsKey3', 'Stat3Min', 'Stat3Max'),
        ),
        VirtualField(
            name='Stat4',
            fields=('StatsKey4', 'Stat4Min', 'Stat4Max'),
        ),
        VirtualField(
            name='Stat5',
            fields=('StatsKey5', 'Stat5Min', 'Stat5Max'),
        ),
        VirtualField(
            name='Stat6',
            fields=('StatsKey6', 'Stat6Min', 'Stat6Max'),
        ),
        VirtualField(
            name='StatsKeys',
            fields=('StatsKey1', 'StatsKey2', 'StatsKey3', 'StatsKey4',
                    'StatsKey5', 'StatsKey6'),
        ),
        VirtualField(
            name='Stats',
            fields=('Stat1', 'Stat2', 'Stat3', 'Stat4', 'Stat5', 'Stat6'),
        ),
        VirtualField(
            name='GenerationWeight',
            fields=('GenerationWeight_TagsKeys', 'GenerationWeight_Values'),
            zip=True,
        ),
    ],
    'MonsterMapBossDifficulty.dat': [
        VirtualField(
            name='Stat1',
            fields=('StatsKey1', 'Stat1Value'),
        ),
        VirtualField(
            name='Stat2',
            fields=('StatsKey2', 'Stat2Value'),
        ),
        VirtualField(
            name='Stat3',
            fields=('StatsKey3', 'Stat3Value'),
        ),
        VirtualField(
            name='Stat4',
            fields=('StatsKey4', 'Stat4Value'),
        ),
        VirtualField(
            name='Stat5',
            fields=('StatsKey5', 'Stat5Value'),
        ),
        VirtualField(
            name='Stats',
            fields=('Stat1', 'Stat2', 'Stat3', 'Stat4', 'Stat5'),
        ),
    ],
    'MonsterMapDifficulty.dat': [
        VirtualField(
            name='Stat1',
            fields=('StatsKey1', 'Stat1Value'),
        ),
        VirtualField(
            name='Stat2',
            fields=('StatsKey2', 'Stat2Value'),
        ),
        VirtualField(
            name='Stat3',
            fields=('StatsKey3', 'Stat3Value'),
        ),
        VirtualField(
            name='Stat4',
            fields=('StatsKey4', 'Stat4Value'),
        ),
        VirtualField(
            name='Stats',
            fields=('Stat1', 'Stat2', 'Stat3', 'Stat4'),
        ),
    ],
    'PassiveSkills.dat': [
        VirtualField(
            name='StatValues',
            fields=('Stat1Value', 'Stat2Value', 'Stat3Value', 'Stat4Value', 'Stat5Value'),
        ),
        VirtualField(
            name='StatsZip',
            fields=('Stats', 'StatValues'),
            zip=True,
        ),
    ],
}
