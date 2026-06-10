#!/bin/bash

target="ALPX-3i-Paris"
variable="tasmin"

test -f "${target}.grid" || wget https://raw.githubusercontent.com/impetus4change/T32-CPRCM/refs/heads/main/grids-3i/${target}.grid

mkdir -p ${target}

ls I4C_EMULATOR_OUTPUT/CORDEX-CMIP6/emulation/ALPX-3/IFCA/*/*/*/*-t??/*/*/${variable}/*/*.nc \
  | parallel --bar --jobs 8 'cdo remapbil,'"${target}"'.grid {} '"${target}"'/{/}'
