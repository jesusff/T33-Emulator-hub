#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
NOTEBOOKS_DIR="$REPO_ROOT/notebooks"

CACHE_NOTEBOOK=${CACHE_NOTEBOOK:-$NOTEBOOKS_DIR/city_level_emulator_ensemble_and_observations.ipynb}
RANKING_NOTEBOOK=${RANKING_NOTEBOOK:-$NOTEBOOKS_DIR/city_level_emulator_ranking_analysis.ipynb}
OUTPUT_DIR=${OUTPUT_DIR:-$NOTEBOOKS_DIR}

CITIES=${CITIES:-"Barcelona Paris Prague"}
RANKING_METHODS=${RANKING_METHODS:-"Blend2C NAO-Teleconnect BSC-DPPB_PatCor_tos_NAtl_1-3"}
VARIABLE=${VARIABLE:-tasmax}
DIAGNOSTIC_IDS=${DIAGNOSTIC_IDS:-tx15day}

# CSV file with columns: city,diagnostic_id,ranking_method,start_year
START_YEAR_FILE=${START_YEAR_FILE:-$SCRIPT_DIR/ranking_start_years.csv}

mkdir -p "$OUTPUT_DIR"

pushd "$NOTEBOOKS_DIR"

lookup_start_year_from_file() {
  local city="$1"
  local diagnostic_id="$2"
  local ranking_method="$3"

  [ -f "$START_YEAR_FILE" ] || return 1

  grep -m1 -F "${city},${diagnostic_id},${ranking_method}," "$START_YEAR_FILE" | cut -d, -f4
}

for city in $CITIES; do
  for diagnostic_id in $DIAGNOSTIC_IDS; do
    cache_out="$OUTPUT_DIR/papermill__city_level_emulator_ensemble_and_observations__${city}_${VARIABLE}_${diagnostic_id}.ipynb"

    echo "Caching common workflow for $city / $VARIABLE / $diagnostic_id"
    papermill "$CACHE_NOTEBOOK" "$cache_out" \
      -p CITY "$city" \
      -p VARIABLE "$VARIABLE" \
      -p DIAGNOSTIC_ID "$diagnostic_id"

    for ranking_method in $RANKING_METHODS; do
      ranking_start_year=$(lookup_start_year_from_file "$city" "$diagnostic_id" "$ranking_method")
      safe_method=$(printf '%s' "$ranking_method" | tr -c 'A-Za-z0-9._-' '_')
      output_notebook="$OUTPUT_DIR/papermill__city_level_emulator_ranking_analysis__${city}_${VARIABLE}_${diagnostic_id}_${safe_method}_${ranking_start_year}.ipynb"
      
      echo "Ranking workflow for $city / $VARIABLE / $diagnostic_id / $ranking_method / $ranking_start_year"
      papermill "$RANKING_NOTEBOOK" "$output_notebook" \
        -p CITY "$city" \
        -p VARIABLE "$VARIABLE" \
        -p DIAGNOSTIC_ID "$diagnostic_id" \
        -p RANKING_METHOD "$ranking_method" \
        -p RANKING_START_YEAR "$ranking_start_year"
    done
  done
done

popd
