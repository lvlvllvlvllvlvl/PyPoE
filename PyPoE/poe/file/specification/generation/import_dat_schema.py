"""
Generates :py:mod:`PyPoE.poe.file.specification.data.stable` from
https://github.com/poe-tool-dev/dat-schema.
"""

import json
import os
import sys
import urllib.request
from types import SimpleNamespace

from PyPoE import DIR
from PyPoE.poe.file.specification.fields import VirtualField
from PyPoE.poe.file.specification.generation.column_naming import UnknownColumnNameGenerator
from PyPoE.poe.file.specification.generation.custom_attributes import custom_attributes, CustomizedField
from PyPoE.poe.file.specification.generation.virtual_fields import virtual_fields


def main():
    if len(sys.argv) > 1:
        schema_json = _read_dat_schema_local(sys.argv[1])
    else:
        schema_json = _read_latest_dat_schema_release()
    input_spec = _load_dat_schema_tables(schema_json)
    output_spec = _convert_tables(input_spec)
    _write_spec(output_spec)


def _read_latest_dat_schema_release() -> str:
    url = 'https://github.com/poe-tool-dev/dat-schema/releases/download/latest/schema.min.json'
    response = urllib.request.urlopen(url)
    return response.read().decode()


def _read_dat_schema_local(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _load_dat_schema_tables(schema_json: str):
    data = json.loads(schema_json, object_hook=lambda d: SimpleNamespace(**d))
    return sorted(data.tables, key=lambda table: table.name)


def _convert_tables(tables: list) -> str:
    spec = ''
    converted_tables = [_convert_table(table) for table in tables]
    with open('template.py', 'r') as f:
        f.readline()
        for line in f:
            if line == '    # <specification>\n':
                spec += ''.join(converted_tables)
            else:
                spec += line
    return spec


def _convert_table(table) -> str:
    table_name = f'{table.name}.dat'
    spec = f"    '{table_name}': File(\n"

    spec += _convert_columns(table_name, table.columns)

    if table_name in virtual_fields:
        spec += _convert_virtual_fields(virtual_fields[table_name])

    spec += "    ),\n"
    return spec


def _convert_columns(table_name: str, columns: list) -> str:
    spec = "        fields=(\n"
    column_name_generator = UnknownColumnNameGenerator()
    for column in columns:
        spec += _convert_column(table_name, column, column_name_generator)
    spec += "        ),\n"
    return spec


def _convert_column(table_name: str, column, name_generator: UnknownColumnNameGenerator) -> str:
    column_name = column.name if column.name else name_generator.next_name(column)
    column_type = _convert_column_type(column)
    if table_name in custom_attributes and column_name in custom_attributes[table_name]:
        custom_attribute = custom_attributes[table_name][column_name]
    else:
        custom_attribute = CustomizedField()

    spec = "            Field(\n"
    spec += f"                name='{column_name}',\n"
    spec += f"                type='{column_type}',\n"
    if column.references and not column.type == 'enumrow':
        spec += f"                key='{column.references.table}.dat',\n"
        if hasattr(column.references, 'column'):
            spec += f"                key_id='{column.references.column}',\n"
    if column.unique:
        spec += f"                unique=True,\n"
    if custom_attribute.enum:
        spec += f"                enum='{custom_attribute.enum}',\n"
    if column.file:
        spec += f"                file_path=True,\n"
        spec += f"                file_ext='{column.file}',\n"
    elif column.files:
        spec += f"                file_path=True,\n"
        spec += f"                file_ext='{', '.join(column.files)}',\n"
    if column.description:
        description = column.description.replace("'", '"')
        spec += f"                description='{description}',\n"
    spec += "            ),\n"
    return spec


def _convert_column_type(column) -> str:
    if column.type == 'array':
        return 'ref|list|byte'
    elif column.array:
        return 'ref|list|' + _TYPE_MAP[column.type]
    else:
        return _TYPE_MAP[column.type]


_TYPE_MAP = {
    'bool': 'bool',
    'string': 'ref|string',
    'i32': 'int',
    'f32': 'float',
    'foreignrow': 'ref|out',
    'row': 'ref|generic',
    'enumrow': 'int',
}


def _convert_virtual_fields(fields: list[VirtualField]) -> str:
    spec = '        virtual_fields=(\n'
    for field in fields:
        spec += '            VirtualField(\n'
        spec += f"                name='{field.name}',\n"
        field_names = "'" + "', '".join(field.fields) + "'"
        spec += f"                fields=({field_names}),\n"
        if field.zip:
            spec += "                zip=True,\n"
        spec += '            ),\n'
    spec += '        ),\n'
    return spec


def _write_spec(spec: str):
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'stable.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(spec)


if __name__ == "__main__":
    main()
