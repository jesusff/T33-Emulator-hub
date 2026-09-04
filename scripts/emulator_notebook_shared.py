import re
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import xarray as xr


def normalize_year_slice(value):
    if isinstance(value, slice):
        return value
    if isinstance(value, (list, tuple)):
        return slice(*value)
    if isinstance(value, str):
        parts = [int(part.strip()) for part in value.split("-") if part.strip()]
        return slice(*parts)
    raise TypeError(f"Unsupported year-slice value: {value!r}")


def normalize_member_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(value)


def build_config(
    city,
    variable,
    diagnostic_id,
    reference_period,
    highlight_members,
    ranking_method='',
    ranking_start_year=None,
    force_recompute=False,
    open_chunks=None,
):
    reference_period = normalize_year_slice(reference_period)
    highlight_members = normalize_member_list(highlight_members)

    city_prefix = f"NSEA-3i-{city}" if city == "Bergen" else f"ALPX-3i-{city}"
    data_dir = Path("../I4C_EMULATOR_CITY_DATA") / city_prefix
    cprcm_data_dir = Path("../I4C_CPRCM_CITY_DATA") / city_prefix
    cache_base_dir = Path("../CACHE")
    cache_path = cache_base_dir / f"{city}_{variable}_{diagnostic_id}.nc"
    eobs_variable = dict(pr="rr", tasmax="tx", tasmin="tn")[variable]
    eobs_url = (
        "https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/"
        f"Grid_0.1deg_reg_ensemble/{eobs_variable}_ens_mean_0.1deg_reg_v33.0e.nc"
    )
    eobs_cache_path = cache_base_dir / f"{eobs_variable}_ens_mean_0.1deg_reg_v33.0e.nc"
    eobs_metric_cache_path = cache_base_dir / f"{city}_EOBS_{variable}_{diagnostic_id}.nc"
    cprcm_cache_path = cache_base_dir / f"{city}_CPRCM_{variable}_{diagnostic_id}.nc"
    figure_dir = Path("FIGURES") / city_prefix

    city_locations = {
        "Barcelona": (41.3874, 2.1686),
        "Paris": (48.8566, 2.3522),
        "Bergen": (60.39299, 5.32415),
        "Prague": (50.0755, 14.4378),
    }
    if city not in city_locations:
        raise ValueError(f"Unknown city: {city}")

    target_lat, target_lon = city_locations[city]

    return dict(
        CITY=city,
        VARIABLE=variable,
        DIAGNOSTIC_ID=diagnostic_id,
        REFERENCE_PERIOD=reference_period,
        HIGHLIGHT_MEMBERS=highlight_members,
        RANKING_METHOD=ranking_method,
        RANKING_START_YEAR=ranking_start_year,
        FORCE_RECOMPUTE=force_recompute,
        CITY_PREFIX=city_prefix,
        DATA_DIR=data_dir,
        CPRCM_DATA_DIR=cprcm_data_dir,
        CACHE_BASE_DIR=cache_base_dir,
        CACHE_PATH=cache_path,
        EOBS_VARIABLE=eobs_variable,
        EOBS_URL=eobs_url,
        EOBS_CACHE_PATH=eobs_cache_path,
        EOBS_METRIC_CACHE_PATH=eobs_metric_cache_path,
        CPRCM_CACHE_PATH=cprcm_cache_path,
        FIGURE_DIR=figure_dir,
        TARGET_LAT=target_lat,
        TARGET_LON=target_lon,
        OPEN_CHUNKS=open_chunks,
    )


def yearly_max_15day_mean(series, config, window_days=15):
    annual_metrics = []
    for year, year_series in series.groupby("time.year"):
        if year_series.sizes.get("time", 0) < window_days:
            continue
        rolling_mean = year_series.rolling(time=window_days, min_periods=window_days).mean()
        annual_value = rolling_mean.max(dim="time")
        annual_metrics.append(annual_value.expand_dims(year=[int(year)]))
    result = xr.concat(annual_metrics, dim="year")
    result.name = f"annual_max_{window_days}day_mean_tasmax"
    location_name = series.attrs.get("location_name", config["CITY"])
    result.attrs["long_name"] = (
        f"Yearly maximum {window_days}-day mean of {location_name} nearest-gridpoint tasmax"
    )
    result.attrs["units"] = series.attrs.get("units", "")
    result.attrs["window_days"] = window_days
    result.attrs["title"] = "Yearly maximum 15-day mean"
    return result


def winter_mean_precipitation(series, config, winter_months=(12, 1, 2)):
    winter_series = series.sel(time=series.time.dt.month.isin(winter_months))
    winter_year = xr.where(
        winter_series.time.dt.month == 12,
        winter_series.time.dt.year + 1,
        winter_series.time.dt.year,
    )
    winter_series = winter_series.assign_coords(winter_year=("time", winter_year.data))
    result = winter_series.groupby("winter_year").mean(dim="time", skipna=True).rename(
        {"winter_year": "year"}
    )
    result = result.assign_coords(year=result.year.astype(int))
    result.name = "winter_mean_precipitation"
    location_name = series.attrs.get("location_name", config["CITY"])
    result.attrs["long_name"] = f"Winter mean precipitation at {location_name}"
    result.attrs["units"] = series.attrs.get("units", "")
    result.attrs["winter_months"] = ",".join(str(month) for month in winter_months)
    result.attrs["title"] = "Winter mean precipitation"
    return result

def summer_mean(series, config, summer_months=(6, 7, 8)):
    summer_series = series.sel(time=series.time.dt.month.isin(summer_months))
    year = summer_series.time.dt.year
    summer_series = summer_series.assign_coords(year=("time", year.data))
    result = summer_series.groupby("year").mean(dim="time", skipna=True)
    result = result.assign_coords(year=result.year.astype(int))
    result.name = "summer_mean"
    location_name = series.attrs.get("location_name", config["CITY"])
    result.attrs["long_name"] = f"Summer mean at {location_name}"
    result.attrs["units"] = series.attrs.get("units", "")
    result.attrs["summer_months"] = ",".join(str(month) for month in summer_months)
    result.attrs["title"] = "Summer mean"
    return result

def yearly_no_min_above_20(series, config, threshold=20):
    annual_counts = []
    for year, year_series in series.groupby("time.year"):
        count = (year_series > threshold).sum(dim="time")
        annual_counts.append(count.expand_dims(year=[int(year)]))
    result = xr.concat(annual_counts, dim="year")
    result.name = "tn20"
    location_name = series.attrs.get("location_name", config["CITY"])
    result.attrs["long_name"] = (
        f"Yearly count of days with minimum temperature above {threshold} degC at {location_name}"
    )
    result.attrs["units"] = "days"
    result.attrs["threshold"] = threshold
    result.attrs["title"] = (
        f"Yearly count of days with minimum temperature above {threshold} degC"
    )
    return result


def yearly_max_1day_precipitation(series, config):
    annual_metrics = []
    for year, year_series in series.groupby("time.year"):
        if year_series.sizes.get("time", 0) < 1:
            continue
        annual_value = year_series.max(dim="time", skipna=True)
        annual_metrics.append(annual_value.expand_dims(year=[int(year)]))

    result = xr.concat(annual_metrics, dim="year")
    result.name = "rx1day"
    location_name = series.attrs.get("location_name", config["CITY"])
    result.attrs["long_name"] = f"Yearly maximum 1-day precipitation at {location_name}"
    result.attrs["units"] = series.attrs.get("units", "")
    result.attrs["title"] = "Yearly maximum 1-day precipitation"
    return result


METRIC_FUNCTIONS = {
    "tx15day": yearly_max_15day_mean,
    "tn20": yearly_no_min_above_20,
    "djfmean": winter_mean_precipitation,
    "jjamean": summer_mean,
    "rx1day": yearly_max_1day_precipitation,
}

FILENAME_PATTERN = re.compile(
    r"^(?P<variable>[^_]+)_(?P<domain>[^_]+)_(?P<driving_source_id>[^_]+)_(?P<experiment_id>[^_]+)_(?P<variant_label>[^_]+)_(?P<institution_id>[^_]+)_(?P<source_id>[^_]+)_(?P<version_realization>[^_]+)_(?P<frequency>[^_]+)_(?P<time_range>\d{8}-\d{8})(?P<fldmean>_fldmean)?$"
)
MEMBER_ID_FIELDS = ("driving_source_id", "experiment_id", "variant_label")


CPRCM_FILENAME_PATTERN = re.compile(
    r"^(?P<variable>[^_]+)_(?P<domain>[^_]+)_(?P<driving_source_id>[^_]+)_(?P<experiment_id>[^_]+)_(?P<variant_label>[^_]+)_(?P<institution_id>[^_]+)_(?P<source_id>[^_]+)_(?P<version_realization>[^_]+)_(?P<frequency>[^_]+)_(?P<time_range>\d{8}-\d{8})$"
)


def parse_filename(path):
    metadata = FILENAME_PATTERN.match(path.stem).groupdict()
    metadata["scenario_group"] = (
        "historical" if metadata["experiment_id"] == "historical" else "ssp"
    )
    metadata["member_id"] = "_".join(metadata[field] for field in MEMBER_ID_FIELDS)
    return metadata


def parse_cprcm_filename(path):
    metadata = CPRCM_FILENAME_PATTERN.match(path.stem).groupdict()
    metadata["scenario_group"] = (
        "historical" if metadata["experiment_id"] == "historical" else "ssp"
    )
    metadata["member_id"] = "CPRCM_" + "_".join(
        metadata[field] for field in MEMBER_ID_FIELDS
    )
    metadata["source_id"] = "CPRCM"
    return metadata


def select_nearest_gridpoint(data_array, config, target_lat=None, target_lon=None):
    target_lat = config["TARGET_LAT"] if target_lat is None else target_lat
    target_lon = config["TARGET_LON"] if target_lon is None else target_lon
    lat_name = next(name for name in ("latitude", "lat") if name in data_array.coords)
    lon_name = next(name for name in ("longitude", "lon") if name in data_array.coords)
    lat = data_array[lat_name]
    lon = data_array[lon_name]

    if lat.ndim == 1 and lon.ndim == 1:
        return data_array.sel({lat_name: target_lat, lon_name: target_lon}, method="nearest")

    distance = (lat - target_lat) ** 2 + (lon - target_lon) ** 2
    nearest_index = distance.argmin(dim=distance.dims)
    indexers = {dim: nearest_index[dim] for dim in distance.dims}
    return data_array.isel(indexers)


def compute_city_gridpoint_variable(
    ds,
    config,
    variable=None,
    location_name=None,
    target_lat=None,
    target_lon=None,
):
    variable = config["VARIABLE"] if variable is None else variable
    location_name = config["CITY"] if location_name is None else location_name
    target_lat = config["TARGET_LAT"] if target_lat is None else target_lat
    target_lon = config["TARGET_LON"] if target_lon is None else target_lon
    series = select_nearest_gridpoint(ds[variable], config, target_lat=target_lat, target_lon=target_lon)
    lat_name = next(name for name in ("latitude", "lat") if name in series.coords)
    lon_name = next(name for name in ("longitude", "lon") if name in series.coords)
    units = series.attrs.get("units", "")
    if units == "K":
        series = series - 273.15
        series.attrs["units"] = "degC"
    elif variable == "pr" and units in {"kg m-2 s-1", "kg m-2 s^-1"}:
        series = series * 86400
        series.attrs["units"] = "mm day-1"
    series.attrs["location_name"] = location_name
    series.attrs["variable"] = variable
    series.attrs["selected_lat"] = float(series[lat_name].item())
    series.attrs["selected_lon"] = float(series[lon_name].item())
    return series.rename(f"city_gridpoint_{variable}")


def build_metric_cache(files, config, open_chunks=None, metric_function=None):
    open_chunks = config["OPEN_CHUNKS"] if open_chunks is None else open_chunks
    metric_function = (
        METRIC_FUNCTIONS[config["DIAGNOSTIC_ID"]] if metric_function is None else metric_function
    )
    member_metrics = []
    for i, path in enumerate(files):
        metadata = parse_filename(path)
        if i % 10 == 0:
            print(f"Processing file {i + 1}/{len(files)}: {path.name}")
        with xr.open_dataset(path, engine="netcdf4", chunks=open_chunks) as ds:
            city_point = compute_city_gridpoint_variable(ds, config)
            annual_metric = metric_function(city_point, config).load()

        member_metric = annual_metric.expand_dims(member=[metadata["member_id"]])
        member_metric = member_metric.assign_coords(
            driving_source_id=("member", [metadata["driving_source_id"]]),
            experiment_id=("member", [metadata["experiment_id"]]),
            scenario_group=("member", [metadata["scenario_group"]]),
            variant_label=("member", [metadata["variant_label"]]),
            source_id=("member", [metadata["source_id"]]),
            time_range=("member", [metadata["time_range"]]),
        )
        member_metrics.append(member_metric)
    metric_cache = xr.concat(member_metrics, dim="member", join="outer").to_dataset()
    return metric_cache


def build_cprcm_metric_cache(files, config, open_chunks=None, metric_function=None):
    open_chunks = config["OPEN_CHUNKS"] if open_chunks is None else open_chunks
    metric_function = (
        METRIC_FUNCTIONS[config["DIAGNOSTIC_ID"]] if metric_function is None else metric_function
    )
    member_metrics = []
    for path in files:
        metadata = parse_cprcm_filename(path)
        with xr.open_dataset(path, engine="netcdf4", chunks=open_chunks) as ds:
            city_point = compute_city_gridpoint_variable(
                ds, config, location_name=f"{config['CITY']} CPRCM"
            )
            annual_metric = metric_function(city_point, config).load()

        member_metric = annual_metric.expand_dims(member=[metadata["member_id"]])
        member_metric = member_metric.assign_coords(
            driving_source_id=("member", [metadata["driving_source_id"]]),
            experiment_id=("member", [metadata["experiment_id"]]),
            scenario_group=("member", [metadata["scenario_group"]]),
            variant_label=("member", [metadata["variant_label"]]),
            source_id=("member", [metadata["source_id"]]),
            time_range=("member", [metadata["time_range"]]),
        )
        member_metrics.append(member_metric)
    metric_cache = xr.concat(member_metrics, dim="member", join="outer").to_dataset()
    return metric_cache


def load_or_build_dataset(cache_path, build_func, force_recompute=False):
    cache_path = Path(cache_path)
    if cache_path.exists() and not force_recompute:
        return xr.open_dataset(cache_path, engine="netcdf4")

    built = build_func()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    built.to_netcdf(cache_path)
    return built


def load_eobs_series(
    config,
    url=None,
    cache_path=None,
    target_lat=None,
    target_lon=None,
    location_name=None,
    open_chunks=None,
):
    url = config["EOBS_URL"] if url is None else url
    cache_path = config["EOBS_CACHE_PATH"] if cache_path is None else cache_path
    target_lat = config["TARGET_LAT"] if target_lat is None else target_lat
    target_lon = config["TARGET_LON"] if target_lon is None else target_lon
    location_name = config["CITY"] if location_name is None else location_name
    open_chunks = config["OPEN_CHUNKS"] if open_chunks is None else open_chunks
    cache_path = Path(cache_path)
    if not cache_path.exists():
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, cache_path)

    with xr.open_dataset(cache_path, engine="netcdf4", chunks=open_chunks) as ds:
        variable_name = "tx" if "tx" in ds.data_vars else next(iter(ds.data_vars))
        lat_name = "latitude" if "latitude" in ds.coords else "lat"
        lon_name = "longitude" if "longitude" in ds.coords else "lon"
        point_series = ds[variable_name].sel(
            {lat_name: target_lat, lon_name: target_lon},
            method="nearest",
        ).load()

    if point_series.attrs.get("units") == "K":
        point_series = point_series - 273.15
        point_series.attrs["units"] = "degC"

    point_series = point_series.rename("eobs_tasmax")
    point_series.attrs["location_name"] = location_name
    point_series.attrs["source"] = url
    point_series.attrs["selected_lat"] = float(point_series[lat_name].item())
    point_series.attrs["selected_lon"] = float(point_series[lon_name].item())
    point_series.attrs["cache_path"] = str(cache_path)
    return point_series


def load_or_build_eobs_metric(config, metric_cache_path=None, force_recompute=False):
    metric_cache_path = (
        config["EOBS_METRIC_CACHE_PATH"] if metric_cache_path is None else metric_cache_path
    )
    metric_cache_path = Path(metric_cache_path)
    if metric_cache_path.exists() and not force_recompute:
        with xr.open_dataset(metric_cache_path, engine="netcdf4") as ds:
            return ds.load()["eobs_metric"]

    eobs_series = load_eobs_series(config)
    eobs_metric = METRIC_FUNCTIONS[config["DIAGNOSTIC_ID"]](eobs_series, config).rename(
        "eobs_metric"
    )
    for attr_name in ["location_name", "source", "selected_lat", "selected_lon"]:
        if attr_name in eobs_series.attrs:
            eobs_metric.attrs[attr_name] = eobs_series.attrs[attr_name]
    eobs_metric.attrs["cache_path"] = str(metric_cache_path)
    metric_cache_path.parent.mkdir(parents=True, exist_ok=True)
    eobs_metric.to_dataset().to_netcdf(metric_cache_path)
    return eobs_metric


def build_driving_source_colors(metric, cmap_name="tab20"):
    driving_sources = sorted({str(value) for value in metric.driving_source_id.values})
    color_map = plt.colormaps[cmap_name]
    return {
        driving_source_id: color_map(index / max(len(driving_sources) - 1, 1))
        for index, driving_source_id in enumerate(driving_sources)
    }


def build_experiment_colors(metric, cmap_name="RdYlBu_r", historical_color="black"):
    ssp_experiment_ids = sorted(
        {str(value) for value in metric.experiment_id.values if str(value).startswith("ssp")}
    )
    color_map = plt.colormaps[cmap_name]
    colors = {
        experiment_id: color_map(index / max(len(ssp_experiment_ids) - 1, 1))
        for index, experiment_id in enumerate(ssp_experiment_ids)
    }
    if "historical" in {str(value) for value in metric.experiment_id.values}:
        colors["historical"] = historical_color
    return colors


def plot_member_ensemble(
    ax,
    metric,
    colors=None,
    alpha=0.75,
    linewidth=1.1,
    line_color=None,
    zorder=2,
    color_coord="driving_source_id",
    legend_title=None,
    alpha_by_color_value=None,
):
    labels_seen = set()
    alpha_by_color_value = alpha_by_color_value or {}
    for member in metric.member.values:
        member_series = metric.sel(member=member)
        color_value = str(member_series[color_coord].item())
        legend_label = color_value if color_value not in labels_seen else None
        labels_seen.add(color_value)
        series_color = line_color if line_color is not None else colors[color_value]
        series_alpha = alpha_by_color_value.get(color_value, alpha)
        ax.plot(
            member_series.year.values,
            member_series.values,
            color=series_color,
            alpha=series_alpha,
            linewidth=linewidth,
            label=legend_label,
            zorder=zorder,
        )
    if legend_title is not None:
        ax.legend(title=legend_title)


def plot_cprcm_anomaly(ax, cprcm_anomaly, color="black", linewidth=3.0, zorder=5, **kwargs):
    labels_seen = set()
    for member in cprcm_anomaly.member.values:
        member_series = cprcm_anomaly.sel(member=member)
        experiment_id = str(member_series.experiment_id.item())
        label = f"direct CPRCM ({experiment_id})" if experiment_id not in labels_seen else None
        labels_seen.add(experiment_id)
        ax.plot(
            member_series.year.values,
            member_series.values,
            color=color,
            alpha=1.0,
            linewidth=linewidth,
            label=label,
            zorder=zorder,
            **kwargs,
        )


def plot_highlight_member(ax, metric, members, color="black", linewidth=2.0, zorder=3, **kwargs):
    if isinstance(members, str):
        members = [members]

    for member in members:
        highlight_series = metric.sel(member=member)
        ax.plot(
            highlight_series.year.values,
            highlight_series.values,
            color=color,
            alpha=1.0,
            linewidth=linewidth,
            label=f"{member}",
            zorder=zorder,
            **kwargs,
        )


def format_time_series_axes(
    ax,
    title,
    ylabel,
    reference_period=None,
    show_zero_line=False,
    legend_title="driving_source_id",
):
    if reference_period is not None:
        ax.axvspan(
            reference_period.start,
            reference_period.stop,
            color="lightgrey",
            alpha=0.25,
            zorder=1,
            label=f"reference period: {reference_period.start}-{reference_period.stop}",
        )
    if show_zero_line:
        ax.axhline(0, color="black", linewidth=1.0, linestyle="--", alpha=0.7)
    ax.set_title(title)
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    ax.legend(frameon=True, title=legend_title, ncols=2)
    ax.grid(True, alpha=0.25)
    plt.tight_layout()


def compute_historical_reference(metric, summary, reference_period):
    return (
        metric.to_series()
        .rename("value")
        .reset_index()
        .merge(
            summary[["member", "driving_source_id", "experiment_id"]],
            on="member",
            how="left",
        )
        .query(
            "experiment_id == 'historical' and @reference_period.start <= year <= @reference_period.stop"
        )
        .groupby("driving_source_id")["value"]
        .mean()
        .rename("reference_value")
    )


def compute_anomaly_metric(metric, historical_reference, metric_name, reference_period):
    anomaly_metric = metric.copy()
    for member in anomaly_metric.member.values:
        driving_source_id = str(anomaly_metric.driving_source_id.sel(member=member).item())
        if driving_source_id not in historical_reference.index:
            continue
        anomaly_metric.loc[dict(member=member)] = (
            anomaly_metric.sel(member=member) - historical_reference.loc[driving_source_id]
        )

    anomaly_metric.attrs["long_name"] = (
        f"{metric.attrs.get('long_name', metric_name)} relative to "
        f"{reference_period.start}-{reference_period.stop} historical mean"
    )
    return anomaly_metric


def load_ranking_table(method, method_specs, repository, start_year=None):
    method_spec = method_specs[method]
    file_template = method_spec["file_template"]
    if "{start_year}" in file_template:
        file_name = file_template.format(start_year=start_year)
    else:
        file_name = file_template

    ranking_url = (
        "https://raw.githubusercontent.com/impetus4change/"
        f"{repository}/refs/heads/main/{method}/{file_name}"
    )
    return pd.read_csv("".join(ranking_url))


def load_ranking_members(method, method_specs, repository, start_year):
    ranking_table = load_ranking_table(method, method_specs, repository, start_year)
    method_spec = method_specs[method]

    if method_spec["layout"] == "long":
        ranking_table["member"] = (
            ranking_table["source_id"].astype(str)
            + "_"
            + ranking_table["experiment_id"].astype(str)
            + "_"
            + ranking_table["variant_label"].astype(str)
        )
        return ranking_table, ranking_table["member"].tolist()

    ranking_year = str(start_year)
    ranking_members = ranking_table[ranking_year].dropna().astype(str).tolist()
    return pd.DataFrame({"member": ranking_members}), ranking_members


def select_ranked_members(ranking_members, available_members, highlight_count):
    ranked_members = []
    selected_rows = []
    for member in ranking_members:
        is_selected = member in available_members and member not in ranked_members
        selected_rows.append(is_selected)
        if is_selected:
            ranked_members.append(member)
        if len(ranked_members) == highlight_count:
            break
    return ranked_members, selected_rows


def save_figure(fig, stem, config, output_dir=None, dpi=300):
    output_dir = config["FIGURE_DIR"] if output_dir is None else output_dir
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(stem)).strip("_")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{safe_stem}.png"
    pdf_path = output_dir / f"{safe_stem}.pdf"
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    return {"png": png_path, "pdf": pdf_path}


def load_common_analysis_inputs(config):
    files = sorted(
        path
        for path in config["DATA_DIR"].glob(f"{config['VARIABLE']}_*.nc")
        if not path.name.endswith("_fldmean.nc")
    )
    metric_cache = load_or_build_dataset(
        config["CACHE_PATH"],
        lambda: build_metric_cache(files, config),
        force_recompute=config["FORCE_RECOMPUTE"],
    )

    metric_name = next(iter(metric_cache.data_vars))
    summary = pd.DataFrame(
        {
            "member": metric_cache.member.values,
            "driving_source_id": metric_cache.driving_source_id.values,
            "experiment_id": metric_cache.experiment_id.values,
            "scenario_group": metric_cache.scenario_group.values,
            "variant_label": metric_cache.variant_label.values,
            "source_id": metric_cache.source_id.values,
            "time_range": metric_cache.time_range.values,
        }
    )

    metric = metric_cache[metric_name]
    historical_reference = compute_historical_reference(
        metric, summary, config["REFERENCE_PERIOD"]
    )
    anomaly_metric = compute_anomaly_metric(
        metric,
        historical_reference,
        metric_name,
        config["REFERENCE_PERIOD"],
    )

    cprcm_files = sorted(
        path
        for path in config["CPRCM_DATA_DIR"].glob(f"{config['VARIABLE']}_*.nc")
        if CPRCM_FILENAME_PATTERN.match(path.stem) is not None
    )
    cprcm_cache = load_or_build_dataset(
        config["CPRCM_CACHE_PATH"],
        lambda: build_cprcm_metric_cache(cprcm_files, config),
        force_recompute=config["FORCE_RECOMPUTE"],
    )
    cprcm_metric_name = next(iter(cprcm_cache.data_vars))
    cprcm_metric = cprcm_cache[cprcm_metric_name]
    cprcm_summary = pd.DataFrame(
        {
            "member": cprcm_cache.member.values,
            "driving_source_id": cprcm_cache.driving_source_id.values,
            "experiment_id": cprcm_cache.experiment_id.values,
        }
    )
    cprcm_historical_reference = compute_historical_reference(
        cprcm_metric, cprcm_summary, config["REFERENCE_PERIOD"]
    )
    cprcm_anomaly = compute_anomaly_metric(
        cprcm_metric,
        cprcm_historical_reference,
        cprcm_metric_name,
        config["REFERENCE_PERIOD"],
    )

    eobs_metric = load_or_build_eobs_metric(config)
    eobs_reference = eobs_metric.sel(
        year=slice(config["REFERENCE_PERIOD"].start, config["REFERENCE_PERIOD"].stop)
    ).mean()
    eobs_anomaly = (eobs_metric - eobs_reference).rename("eobs_anomaly")

    return {
        "files": files,
        "metric_cache": metric_cache,
        "metric_name": metric_name,
        "metric": metric,
        "summary": summary,
        "historical_reference": historical_reference,
        "anomaly_metric": anomaly_metric,
        "cprcm_cache": cprcm_cache,
        "cprcm_metric_name": cprcm_metric_name,
        "cprcm_metric": cprcm_metric,
        "cprcm_summary": cprcm_summary,
        "cprcm_historical_reference": cprcm_historical_reference,
        "cprcm_anomaly": cprcm_anomaly,
        "eobs_metric": eobs_metric,
        "eobs_reference": eobs_reference,
        "eobs_anomaly": eobs_anomaly,
    }
