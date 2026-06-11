#!/bin/bash

target="ALPX-3i-Barcelona"
variable="orog"

emulator=false
cprcm=true

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
  ls I4C_EMULATOR_OUTPUT/CORDEX-CMIP6/emulation/ALPX-3/IFCA/*/*/*/*-t??/*/*/${variable}/*/*.nc \
    | parallel --bar --jobs 8 'cdo remapbil,'"${target}"'.grid {} '"I4C_EMULATOR_CITY_DATA/${target}"'/{/}'
fi

if [ "${cprcm}" = true ]; then
  echo "Remapping CPRCM data..."
  mkdir -p "I4C_CPRCM_CITY_DATA/${target}"
  ls I4C_CPRCM_DATA/ALPX-3/BCCR-UCAN/NorESM2-MM/*/*/*/*/*/${variable}/*/*.nc \
    | parallel --bar --jobs 8 'cdo remapbil,'"${target}"'.grid {} '"I4C_CPRCM_CITY_DATA/${target}"'/{/}'
fi