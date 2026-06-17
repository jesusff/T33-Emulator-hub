#!/bin/bash

target="ALPX-3i-Barcelona"
var="tasmin"
#BASEDIR="I4C_CPRCM_CITY_DATA"
BASEDIR="I4C_EMULATOR_CITY_DATA"

# Test for cdo and cmip7repack
if ! command -v cdo &> /dev/null; then
  echo "cdo could not be found. Please install cdo to run this script."
  exit 1
fi
if ! command -v cmip7repack &> /dev/null; then
  echo "cmip7repack could not be found. Please install cmip7repack to run this script."
  exit 1
fi

function dumpdates() {
  tr ' _.' '\n\n\n' | grep -E '^[0-9]{8}-[0-9]{8}$' | tr '-' '\n' | sort -u
}

ls ${BASEDIR}/${target}/${var}_ALPX-3_*.nc \
  | sed -e s/_[0-9]*-.*\.nc// \
  | sort -u \
  | while read -r file; do
      mergefiles=$(ls ${file}_*.nc)
      inidate=$(echo ${mergefiles} | dumpdates | head -n 1)
      enddate=$(echo ${mergefiles} | dumpdates | tail -n 1)
      outfile="${file}_${inidate}-${enddate}.nc"
      outfile=${outfile//ALPX-3_/${target}_}
      cdo mergetime ${mergefiles} ${outfile}
      cmip7repack -o ${outfile} 
      rm ${mergefiles}
    done
