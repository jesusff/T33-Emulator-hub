#!/bin/bash

target="ALPX-3i-Barcelona"
variable="tasmin"

target="NSEA-3i-Bergen"
variable=${1:-orog}
institution="UIB"
domain="NSEA-3"

emulator=true
cprcm=false

echo "** Retrieving variable: ${variable}"

# Test for cdo and parallel
if ! command -v cdo &> /dev/null; then
  echo "cdo could not be found. Please install cdo to run this script."
  exit 1
fi

if ! command -v parallel &> /dev/null; then
  echo "parallel could not be found. Please install parallel to run this script."
  exit 1
fi

test -f "${target}.grid" || wget https://raw.githubusercontent.com/impetus4change/T32-CPRCM/refs/heads/main/grids-3i/${target}.grid

if [ "${emulator}" = true ]; then
  echo "Remapping emulator output..."
  mkdir -p "I4C_EMULATOR_CITY_DATA/${target}"
  ls I4C_EMULATOR_DATA/CORDEX-CMIP6/emulation/${domain}/${institution}/*/*/*/*/*/[df]*/${variable}/*/*.nc \
    | parallel --bar --jobs 8 'cdo remapbil,'"${target}"'.grid {} '"I4C_EMULATOR_CITY_DATA/${target}"'/{/}'
fi

if [ "${cprcm}" = true ]; then
  echo "Remapping CPRCM data..."
  mkdir -p "I4C_CPRCM_CITY_DATA/${target}"
  ls I4C_CPRCM_DATA/${domain}/${institution}/*/*/*/*/*/[df]*/${variable}/*/*.nc \
    | parallel --bar --jobs 8 'cdo remapbil,'"${target}"'.grid {} '"I4C_CPRCM_CITY_DATA/${target}"'/{/}'
fi
