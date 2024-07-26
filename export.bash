#!/usr/bin/env bash

QUIET=
ARGS=()
IMG=()
export ALL_EXPORTERS=(gem-skills items passives skills mastery-effects mastery-groups mods monsters areas maps incursion-rooms modules atlas-icons)
EXPORTERS=()

# check if value is in array
# https://stackoverflow.com/a/68702551/2063518
function find() {
  local -nr values="$2"

  for value in "${values[@]}"
  do
    [[ "$value" == "$1" ]] && return 0
  done

  return 1
}

# print message and return success if exporter is enabled
function exporting() {
  if ! find $1 ALL_EXPORTERS
  then
    echo "$1 not in ALL_EXPORTERS - fix $(basename $0) script"
    exit 1
  fi

  if [[ -z ${EXPORTERS[@]} ]] && [[ $1 != atlas-icons ]] || find $1 EXPORTERS
  then
    echo exporting $1
  else
    return 1
  fi
}

function usage () {
    echo '
usage:
  '$(basename $0)' [EXPORTERS]... [OPTIONS]... [-- PYPOE_OPTIONS]

  exporters can be any or all of: '"${ALL_EXPORTERS[@]}"'
  if no exporters are listed, all exporters except atlas-icons will be run

options:
  -h, --help            show this help message and exit
  -q, --quiet           hide all non-error messages from pypoe
  -i, --image           process images and convert them to the specified format
  -t, --threads         number of threads that can read wiki pages simultaneously (equivalent to the -w-mt pypoe argument)
  -u, --username        wiki username (if not supplied pypoe will prompt several times during the export)
  -p, --password        wiki password (if not supplied pypoe will prompt several times during the export)

  -w, --write           export to the file system
                      - alias for '$(basename $0)' -- --write

  -d, --dry-run         perform a dry run, comparing changes against the wiki and saving diffs in the output directory
                      - alias for '$(basename $0)' -i md5sum .png -- --write -w -w-dr -w-d

  -e, --export          perform a full export to the wiki
                      - alias for '$(basename $0)' -i .png -- -w -w-pc

  -c, --cache           perform a null edit and cache purge of every page managed by the exporter
                      - alias for '$(basename $0)' -- -w -w-dr -w-pc all'
  exit $1
}

VALID_ARGS=$(getopt -o hqi:t:u:p:wdec --long help,quiet,image:,threads:,username:,password:,write,dry-run,export,cache -- "$@")
if [[ $? -ne 0 ]]; then
    usage $?;
fi
eval set -- "$VALID_ARGS"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i | --image)
        if [[ $2 == .png ]]
        then
          IMG=(--store-images --convert-images)
        elif [[ $2 == md5sum ]]
        then
          IMG=(--store-images --convert-images=md5sum)
        elif [[ $2 == .* ]]
        then
          IMG=(--store-images --convert-images="$2")
        else
          echo "Error: $2 is not a file extension"
          usage
        fi
        shift 2
        ;;
    -t | --threads)
        ARGS+=(-w-mt $2)
        shift 2
        ;;
    -u | --username)
        ARGS+=(-w-u $2)
        shift 2
        ;;
    -p | --password)
        ARGS+=(-w-pw $2)
        shift 2
        ;;
    -w | --write)
        ARGS+=(--write)
        shift
        ;;
    -d | --dry-run)
        ARGS+=(--write -w -w-dr -w-d)
        IMG=(--store-images --convert-images=md5sum)
        shift
        ;;
    -e | --export)
        ARGS+=(-w -w-pc)
        IMG=(--store-images --convert-images)
        shift
        ;;
    -c | --cache)
        ARGS+=(-w -w-dr -w-pc all)
        IMG=(--store-images --convert-images)
        shift
        ;;
    -q | --quiet)
        QUIET=--quiet
        shift
        ;;
    -h | --help)
        usage
        shift
        ;;
    --)
        shift
        # getopt puts all arguments not starting with '-' after the '--'
        while [[ $# -gt 0 ]] && [[ $1 != -* ]]
        do
          if ! find $1 ALL_EXPORTERS
          then
            echo "$1 not recognized - known exporters: ${ALL_EXPORTERS[@]}"
            usage 1
          fi
          EXPORTERS+=($1)
          shift
        done
        break
        ;;
  esac
done

set -e

pypoe_exporter $QUIET setup perform

exporting gem-skills &&
pypoe_exporter $QUIET wiki skill by_gem "${IMG[@]}" "${ARGS[@]}" "$@"
exporting items &&
pypoe_exporter $QUIET wiki items item rowid "${IMG[@]}" "${ARGS[@]}" "$@"
exporting passives &&
pypoe_exporter $QUIET wiki passive rowid "${IMG[@]}" "${ARGS[@]}" "$@"
exporting skills &&
pypoe_exporter $QUIET wiki skill by_name "${IMG[@]}" "${ARGS[@]}" "$@"
exporting mastery-effects &&
pypoe_exporter $QUIET wiki mastery effects rowid "${ARGS[@]}" "$@"
exporting mastery-groups &&
pypoe_exporter $QUIET wiki mastery groups rowid "${ARGS[@]}" "$@"
exporting mods &&
pypoe_exporter $QUIET wiki mods mods rowid "${ARGS[@]}" "$@"
exporting monsters &&
pypoe_exporter $QUIET wiki monster rowid "${ARGS[@]}" "$@"
exporting areas &&
pypoe_exporter $QUIET wiki area rowid "${ARGS[@]}" "$@"
exporting maps &&
pypoe_exporter $QUIET wiki items maps "${IMG[@]}" "${ARGS[@]}" "$@" --store-images --convert-images
exporting incursion-rooms &&
pypoe_exporter $QUIET wiki incursion rooms rowid "${ARGS[@]}" "$@"
exporting modules && {
  pypoe_exporter $QUIET wiki lua bestiary "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua blight "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua crafting_bench "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua delve "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua harvest "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua heist "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua monster "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua pantheon "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua synthesis "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua ot "${ARGS[@]}" "$@"
  pypoe_exporter $QUIET wiki lua minimap "${ARGS[@]}" "$@"
  # pypoe_exporter $QUIET wiki lua packs "${ARGS[@]}" "$@"
}
exporting atlas-icons &&
pypoe_exporter $QUIET wiki items atlas_icons "${ARGS[@]}" "$@" --store-images --convert-images

date -ud "@$SECONDS" "+Export completed in: %H:%M:%S"
