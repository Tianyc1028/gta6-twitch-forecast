"""Forecast GTA VI's launch-day Twitch viewers, hour by hour.

Entry for make.fun's gta6-twitch-ccu-forecast-01: given one case file (the
release day's first hour already printed), write five quantiles of the
concurrent-viewer count for each of hours 2..24.

How it works
------------
The case ships with the hourly Twitch curves of dozens of past big game
launches ("comparables"). Launches differ wildly in shape, but the ones
whose unlock rolled round the world at local midnight -- the way GTA VI
unlocks -- share one family of curves: a small overnight dip after hour 1,
a jump when the US east coast unlocks, a quieter midday, then a big evening
rise into US prime time, peaking around hours 19-22 before fading.

The key fact the data shows is that the *steepness* of that curve depends
on how big hour 1 already is: when hour 1 is huge (most of the world was
already watching) the evening barely rises above it; when hour 1 is small
(only the early time zones were in) the evening can be several times
higher. So for each hour h we fit, over the midnight-rolling launches, a
straight line in log space

    log(viewers_h / viewers_1) = a_h + b_h * log(viewers_1)

and read the forecast off that line at this case's hour-1 print. The
spread comes from the same fit's residual scatter, so hours and launches
that history says are harder to call get wider quantile bands.

Everything is fitted at run time from the case file itself, so the same
program adapts to whatever comparables a case carries. It is fully
deterministic (no randomness, no clock, no network), standard library only.

Safety nets: if the comparables cannot be used for any reason the program
falls back to a flat persistence forecast (every hour at the hour-1 print
with a widening band), so it still writes a valid file. Hour-1 prints
outside the range the comparables cover are clamped to that range instead
of extrapolating the line, and no median ratio is allowed below 0.5.
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module
# shipped beside this file would import. (This entry is one file, but the
# line keeps the door open without changing any behaviour.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z_SCORES = [-1.645, -0.674, 0.0, 0.674, 1.645]

# How much of the fitted residual spread to use for the quantile bands.
# 1.0 is the raw residual scatter; slightly less than that scored a touch
# better in leave-one-out checks on the past launches.
SPREAD_SHRINK = 0.85
# No hour's band is allowed narrower than this, in natural-log units.
SPREAD_FLOOR = 0.10
# No hour's median is allowed below this multiple of the hour-1 print.
RATIO_FLOOR = 0.5
# A launch only joins the fit if it has at least this many release-day
# hours recorded (hour 1 plus the hours the fit needs).
MIN_HOURS = 20
# The midnight-rolling family must have at least this many launches, or
# the fit falls back to every comparable with a usable curve.
MIN_FAMILY = 8


def parse_instant(text):
    """An ISO-8601 UTC instant like 2026-11-19T00:00:00Z, as a datetime."""
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def round_half_up_2dp(value):
    """Round to 2 decimals, halves away from zero, returned as int when whole."""
    scaled = value * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    rounded = whole / 100.0
    return int(rounded) if float(rounded).is_integer() else rounded


def day_curve(comparable):
    """A launch's 24 release-day hourly viewer counts, None where missing.

    Hours are counted from the comparable's own day_start, so hour 1 is
    00:00-01:00 UTC of its release date, the same cut every case uses.
    """
    start = parse_instant(comparable["day_start"])
    hours = [None] * 24
    for point in comparable.get("hourly", []):
        try:
            at = parse_instant(point["from"])
            viewers = point["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        slot = int((at - start).total_seconds() // 3600)
        if 0 <= slot < 24 and isinstance(viewers, (int, float)) and viewers > 0:
            hours[slot] = float(viewers)
    return hours


def unlocks_at_local_midnight(comparable):
    """True when the launch unlocked rolling at local midnight, like GTA VI.

    The case's notes describe each launch's unlock; the midnight-rolling
    ones say so in so many words. Anything else (one simultaneous global
    unlock, early access, unverified) is not in the family.
    """
    note = (comparable.get("unlock") or "").lower()
    return "rolling midnight" in note or "midnight local" in note


def usable_curves(case):
    """The release-day curves the fit may learn from, best family first.

    Prefers the midnight-rolling launches; falls back to every comparable
    with a usable curve when that family is too small to fit on.
    """
    curves = []
    rolling = []
    for comparable in case.get("comparables", []):
        try:
            curve = day_curve(comparable)
        except (KeyError, TypeError, ValueError):
            # One malformed comparable must not sink the whole case.
            continue
        if curve[0] is None:
            continue
        if sum(1 for value in curve if value is not None) < MIN_HOURS:
            continue
        curves.append(curve)
        if unlocks_at_local_midnight(comparable):
            rolling.append(curve)
    if len(rolling) >= MIN_FAMILY:
        return rolling
    return curves


def fit_line(xs, ys):
    """Least squares for y = a + b*x; returns (a, b, residual_sd)."""
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx else 0.0
    intercept = mean_y - slope * mean_x
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    dof = max(n - 2, 1)
    spread = math.sqrt(sum(r * r for r in residuals) / dof)
    return intercept, slope, spread


def hour_forecast(first_print, curves, hour):
    """Five quantiles of one hour's viewers, from the fitted line for it."""
    log_first = math.log(first_print)
    train_first = [math.log(curve[0]) for curve in curves]
    # Never extrapolate the line past the launches it was fitted on.
    log_first = min(max(log_first, min(train_first)), max(train_first))
    xs = []
    ys = []
    for curve in curves:
        if curve[hour - 1] is not None:
            xs.append(math.log(curve[0]))
            ys.append(math.log(curve[hour - 1] / curve[0]))
    if len(xs) < 3:
        # Too little to fit this hour: stay flat with a wide band.
        return flat_quantiles(first_print, hour)
    intercept, slope, spread = fit_line(xs, ys)
    log_ratio = intercept + slope * log_first
    log_ratio = max(log_ratio, math.log(RATIO_FLOOR))
    median = first_print * math.exp(log_ratio)
    sigma = max(spread, SPREAD_FLOOR) * SPREAD_SHRINK
    quantiles = [median * math.exp(z * sigma) for z in Z_SCORES]
    return clean_quantiles(quantiles)


def flat_quantiles(first_print, hour):
    """Fallback forecast: every hour at the hour-1 print, band widening.

    Used when a case carries no usable comparables, or an hour has too few
    launches to fit. It keeps the output valid even then.
    """
    sigma = 0.15 * math.sqrt(hour - 1)
    quantiles = [first_print * math.exp(z * sigma) for z in Z_SCORES]
    return clean_quantiles(quantiles)


def clean_quantiles(quantiles):
    """Round, clamp to (0, 1e9], and force non-decreasing, as the rules ask."""
    cleaned = []
    previous = 0.0
    for value in quantiles:
        rounded = round_half_up_2dp(max(1.0, min(value, 1_000_000_000.0)))
        rounded = max(rounded, previous)
        cleaned.append(rounded)
        previous = rounded
    return cleaned


def first_print_of(case):
    """Hour 1's print: the case's known row, else the last hourly point."""
    for row in case.get("known", []):
        if row.get("hour") == 1:
            return max(1.0, float(row["viewers"]))
    hourly = case.get("history_hourly") or []
    if hourly:
        return max(1.0, float(hourly[-1]["viewers"]))
    return 1.0


def forecast_case(case):
    """The forecast object for one case: 23 rows, hours 2..24."""
    first = first_print_of(case)
    curves = usable_curves(case)
    rows = []
    for row in case["forecast"]:
        hour = row["hour"]
        if curves:
            quantiles = hour_forecast(first, curves, hour)
        else:
            quantiles = flat_quantiles(first, hour)
        rows.append({"hour": hour, "q": quantiles})
    rows.sort(key=lambda row: row["hour"])
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        try:
            forecast = forecast_case(case)
        except Exception:
            # Never leave a case without an output: fall back to the flat
            # forecast around hour 1, which is always a valid file.
            try:
                first = first_print_of(case)
            except Exception:
                first = 1.0
            hours = case.get("forecast") or [{"hour": h} for h in range(2, 25)]
            forecast = {
                "hours": [
                    {"hour": row["hour"], "q": flat_quantiles(first, row["hour"])}
                    for row in hours
                ]
            }
        text = json.dumps(forecast, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / (path.stem + ".out")).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
