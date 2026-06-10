#!/bin/bash

target="ALPX-3i-Paris"
var="tasmin"

function dumpdates() {
  tr ' _.' '\n\n\n' | grep -E '^[0-9]{8}-[0-9]{8}$' | tr '-' '\n' | sort -u
}

ls ${target}/${var}_ALPX-3_*.nc \
  | cut -d_ -f-9 \
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
