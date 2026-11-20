#!/usr/bin/env python3
"""
savant_swings.py  --  Bat Speed 3.0 data pull

Pulls every regular-season pitch from Baseball Savant for the chosen seasons,
one day per request, then keeps only swings with the columns needed for the
contact-point work (bat speed, swing length, attack angle/direction, swing
path tilt, and the batter-CoM-relative intercept point).

Setup (once):
    pip install requests pandas pyarrow

Run:
    python savant_swings.py                      # 2024, 2025, 2026
    python savant_swings.py --seasons 2026       # just one season
    python savant_swings.py --workers 2          # gentler if Savant is grumpy
    python savant_swings.py --build-only         # rebuild outputs from cache

It is safe to stop (Ctrl+C) and rerun at any time. Finished days are cached in
./savant_cache and skipped on the next run; a day that keeps failing is left
out of the cache, so simply rerunning retries only the missing days.

Outputs (in ./savant_out):
    swings_2024.parquet, swings_2025.parquet, swings_2026.parquet
    coverage_report.txt   <- attach this along with the parquet files
"""

from __future__ import annotations

import argparse
import gzip
import io
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

SAVANT_CSV = "https://baseballsavant.mlb.com/statcast_search/csv"
SAVANT_ROW_CAP = 25_000  # Savant silently truncates a CSV export at this many rows

# Regular-season games only (hfGT=R) so a generous window is harmless:
# off days and spring training simply come back empty.
SEASON_WINDOW = ("03-15", "10-05")

SWING_DESCRIPTIONS = {
    "foul", "foul_tip", "foul_bunt", "foul_pitchout",
    "hit_into_play", "hit_into_play_no_out", "hit_into_play_score",
    "swinging_strike", "swinging_strike_blocked", "swinging_pitchout",
    "missed_bunt", "bunt_foul_tip",
}
BUNT_DESCRIPTIONS = {"foul_bunt", "missed_bunt", "bunt_foul_tip"}

KEEP_COLUMNS = [
    # identifiers and game context
    "game_date", "game_year", "game_type", "game_pk", "at_bat_number", "pitch_number",
    "inning", "inning_topbot", "home_team", "away_team",
    "batter", "pitcher", "player_name", "stand", "p_throws", "age_bat",
    "balls", "strikes", "outs_when_up", "on_1b", "on_2b", "on_3b", "bat_score_diff",
    "n_thruorder_pitcher", "n_priorpa_thisgame_player_at_bat",
    # pitch characteristics and full trajectory (for time-to-contact work)
    "pitch_type", "pitch_name", "release_speed", "effective_speed", "release_extension",
    "release_pos_x", "release_pos_y", "release_pos_z", "arm_angle",
    "release_spin_rate", "spin_axis", "pfx_x", "pfx_z",
    "api_break_z_with_gravity", "api_break_x_batter_in",
    "plate_x", "plate_z", "sz_top", "sz_bot", "zone",
    "vx0", "vy0", "vz0", "ax", "ay", "az",
    # outcome
    "type", "description", "events", "bb_type",
    "launch_speed", "launch_angle", "launch_speed_angle", "hit_distance_sc", "hc_x", "hc_y",
    "estimated_ba_using_speedangle", "estimated_woba_using_speedangle",
    "estimated_slg_using_speedangle", "woba_value", "woba_denom", "delta_run_exp",
    "hyper_speed",
    # bat tracking
    "bat_speed", "swing_length", "attack_angle", "attack_direction", "swing_path_tilt",
    "intercept_ball_minus_batter_pos_x_inches", "intercept_ball_minus_batter_pos_y_inches",
]
# Also keep any column Savant adds later that looks swing/contact related.
EXTRA_COLUMN_PATTERN = re.compile(
    r"(intercept|swing|attack|stance|batter_pos|bat_speed|contact|foot|sweet|squared|blast)"
)
REQUIRED_TRACKING = [
    "bat_speed", "swing_length",
    "intercept_ball_minus_batter_pos_x_inches", "intercept_ball_minus_batter_pos_y_inches",
]
CATEGORICAL = [
    "game_type", "inning_topbot", "home_team", "away_team", "player_name", "stand",
    "p_throws", "pitch_type", "pitch_name", "type", "description", "events", "bb_type",
]
INTEGER_LIKE = [
    "game_year", "game_pk", "at_bat_number", "pitch_number", "inning", "batter", "pitcher",
    "age_bat", "balls", "strikes", "outs_when_up", "on_1b", "on_2b", "on_3b",
    "bat_score_diff", "n_thruorder_pitcher", "n_priorpa_thisgame_player_at_bat", "zone",
    "launch_speed_angle",
]

print_lock = threading.Lock()


def log(msg: str) -> None:
    with print_lock:
        print(msg, flush=True)


# --------------------------------------------------------------------------- fetch

def build_params(day: date) -> dict:
    d = day.isoformat()
    return {
        "all": "true", "hfPT": "", "hfAB": "", "hfGT": "R|", "hfPR": "", "hfZ": "",
        "hfStadium": "", "hfBBL": "", "hfNewZones": "", "hfPull": "", "hfC": "",
        "hfSea": f"{day.year}|", "hfSit": "", "player_type": "batter", "hfOuts": "",
        "hfOpponent": "", "pitcher_throws": "", "batter_stands": "", "hfSA": "",
        "game_date_gt": d, "game_date_lt": d, "hfMo": "", "hfTeam": "", "home_road": "",
        "hfRO": "", "position": "", "hfInfield": "", "hfOutfield": "", "hfInn": "",
        "hfBBT": "", "hfFlag": "", "metric_1": "", "group_by": "name",
        "min_pitches": "0", "min_results": "0", "min_pas": "0", "sort_col": "pitches",
        "player_event_sort": "api_p_release_speed", "sort_order": "desc", "type": "details",
    }


class BadResponse(Exception):
    pass


def parse_savant_csv(raw: bytes) -> tuple[str, int]:
    """Return (text, n_data_rows). Raises BadResponse if this isn't a Savant CSV."""
    if not raw or not raw.strip():
        raise BadResponse("empty body")
    text = raw.decode("utf-8-sig", errors="replace")
    header = text.split("\n", 1)[0]
    if "pitch_type" not in header or "game_date" not in header:
        snippet = re.sub(r"\s+", " ", text[:120])
        raise BadResponse(f"not a Statcast CSV (starts with: {snippet!r})")
    n_rows = sum(1 for line in text.splitlines()[1:] if line.strip())
    return text, n_rows


def cache_paths(cache_dir: Path, day: date) -> tuple[Path, Path]:
    folder = cache_dir / str(day.year)
    return folder / f"{day.isoformat()}.csv.gz", folder / f"{day.isoformat()}.empty"


def is_cached(cache_dir: Path, day: date) -> bool:
    data, empty = cache_paths(cache_dir, day)
    return data.exists() or empty.exists()


def fetch_day(day: date, args, session: requests.Session, stop: threading.Event):
    """Fetch one day with patient retries. Returns (day, status, n_rows, note)."""
    data_path, empty_path = cache_paths(args.cache_dir, day)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    last_error = ""
    for attempt in range(1, args.max_attempts + 1):
        if stop.is_set():
            return day, "stopped", 0, ""
        time.sleep(random.uniform(args.min_delay, args.max_delay))  # be polite
        try:
            resp = session.get(args.base_url, params=build_params(day),
                               timeout=(20, args.read_timeout))
            if resp.status_code != 200:
                raise BadResponse(f"HTTP {resp.status_code}")
            text, n_rows = parse_savant_csv(resp.content)
        except (requests.RequestException, BadResponse) as exc:
            last_error = str(exc)[:160]
            if attempt < args.max_attempts:
                wait = min(300.0, args.backoff * 2 ** (attempt - 1)) * random.uniform(0.8, 1.3)
                log(f"  {day}  attempt {attempt} failed ({last_error}); retrying in {wait:.0f}s")
                # sleep in small steps so Ctrl+C is responsive
                end = time.time() + wait
                while time.time() < end and not stop.is_set():
                    time.sleep(min(1.0, end - time.time()))
            continue

        if n_rows == 0:
            empty_path.touch()
            return day, "empty", 0, ""
        note = ""
        if n_rows >= SAVANT_ROW_CAP:
            note = f"WARNING: {n_rows} rows hits Savant's {SAVANT_ROW_CAP} cap, may be truncated"
        tmp = data_path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, data_path)  # atomic: a cached file is always complete
        return day, "ok", n_rows, note
    return day, "failed", 0, last_error


def all_days(seasons: list[int], start: str | None, end: str | None) -> list[date]:
    yesterday = date.today() - timedelta(days=1)
    days: list[date] = []
    for yr in seasons:
        d0 = date.fromisoformat(start) if start else date.fromisoformat(f"{yr}-{SEASON_WINDOW[0]}")
        d1 = date.fromisoformat(end) if end else date.fromisoformat(f"{yr}-{SEASON_WINDOW[1]}")
        d1 = min(d1, yesterday)
        d = d0
        while d <= d1:
            if d.year == yr:
                days.append(d)
            d += timedelta(days=1)
    return days


def run_fetch(args) -> list[tuple[date, str]]:
    days = all_days(args.seasons, args.start, args.end)
    todo = [d for d in days if not is_cached(args.cache_dir, d)]
    log(f"{len(days)} days in range, {len(days) - len(todo)} already cached, {len(todo)} to fetch "
        f"with {args.workers} workers.")
    if not todo:
        return []

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/csv,*/*",
    })
    adapter = requests.adapters.HTTPAdapter(pool_connections=args.workers,
                                            pool_maxsize=args.workers)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    stop = threading.Event()
    failures: list[tuple[date, str]] = []
    done = 0
    t0 = time.time()
    pool = ThreadPoolExecutor(max_workers=args.workers)
    futures = [pool.submit(fetch_day, d, args, session, stop) for d in todo]
    try:
        for fut in as_completed(futures):
            day, status, n_rows, note = fut.result()
            done += 1
            elapsed = time.time() - t0
            eta = elapsed / done * (len(todo) - done)
            if status == "failed":
                failures.append((day, note))
            if status != "stopped":
                extra = f"  {note}" if note else ""
                log(f"[{done:>4}/{len(todo)}] {day}  {status:<6} {n_rows:>5} pitches   "
                    f"eta {eta / 60:5.1f} min{extra}")
    except KeyboardInterrupt:
        log("\nStopping... finished days are cached; rerun the same command to resume.")
        stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
        sys.exit(130)
    pool.shutdown(wait=True)
    return failures


# --------------------------------------------------------------------------- build

def slim_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Keep swings only, flag bunts (using the play text before it's dropped), trim columns."""
    has_tracking = df["bat_speed"].notna() if "bat_speed" in df else pd.Series(False, index=df.index)
    df = df.loc[df["description"].isin(SWING_DESCRIPTIONS) | has_tracking].copy()
    bunt = df["description"].isin(BUNT_DESCRIPTIONS)
    for text_col in ("events", "des"):
        if text_col in df:
            bunt |= df[text_col].astype(str).str.contains("bunt", case=False, na=False)
    keep = [c for c in df.columns
            if c in KEEP_COLUMNS or (EXTRA_COLUMN_PATTERN.search(c) and not c.startswith("post_"))]
    df = df[keep]
    df["is_bunt"] = bunt.values
    return df


def optimise_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if col in CATEGORICAL:
            df[col] = df[col].astype("string").astype("category")
        elif col in INTEGER_LIKE:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif col == "game_date":
            df[col] = pd.to_datetime(df[col], errors="coerce")
        elif col == "is_bunt":
            df[col] = df[col].astype(bool)
        elif df[col].dtype == object:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().sum() >= df[col].notna().sum() * 0.99:
                df[col] = converted.round(3).astype("float32")
        elif pd.api.types.is_float_dtype(df[col]):
            # 3 decimals is far finer than tracking precision and roughly halves file size
            df[col] = df[col].round(3).astype("float32")
    return df


ATTACH_LIMIT_MB = 28.0  # keep each file comfortably under a typical 30 MB upload cap


def write_frame(df: pd.DataFrame, path: Path, fmt: str) -> None:
    if fmt == "parquet":
        df.to_parquet(path, index=False, compression="zstd", compression_level=9)
    else:
        df.to_csv(path, index=False, compression="gzip")


def write_season(swings: pd.DataFrame, out_dir: Path, season: int, fmt: str) -> list[Path]:
    """Write one file per season; if it's too big to attach, split it by half-season."""
    for old in out_dir.glob(f"swings_{season}*"):
        old.unlink()
    path = out_dir / f"swings_{season}.{fmt}"
    write_frame(swings, path, fmt)
    if path.stat().st_size / 1e6 <= ATTACH_LIMIT_MB:
        return [path]
    path.unlink()
    first_half = swings["game_date"].dt.month <= 6
    parts = []
    for tag, mask in (("a_thru_june", first_half), ("b_july_on", ~first_half)):
        part = out_dir / f"swings_{season}_{tag}.{fmt}"
        write_frame(swings.loc[mask], part, fmt)
        parts.append(part)
    return parts


def build_outputs(args, failures: list[tuple[date, str]]) -> None:
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report: list[str] = [f"Bat Speed 3.0 coverage report  ({datetime.now():%Y-%m-%d %H:%M})", ""]
    try:
        import pyarrow  # noqa: F401
        fmt = "parquet"
    except ImportError:
        fmt = "csv.gz"
        log("pyarrow not installed; writing .csv.gz instead (pip install pyarrow for parquet).")

    for season in args.seasons:
        files = sorted((args.cache_dir / str(season)).glob("*.csv.gz"))
        n_empty = len(list((args.cache_dir / str(season)).glob("*.empty")))
        if not files:
            report += [f"== {season}: no cached data", ""]
            continue
        log(f"Building {season} from {len(files)} cached days...")
        frames, total_pitches, header_cols = [], 0, None
        for f in files:
            df = pd.read_csv(f, low_memory=False)
            total_pitches += len(df)
            if header_cols is None:
                header_cols = list(df.columns)
            frames.append(slim_frame(df))
        swings = optimise_dtypes(pd.concat(frames, ignore_index=True))

        # Empty days between the first and last game day should only be off days
        # (All-Star break etc). A long list here means Savant returned blanks by mistake.
        game_days = sorted(date.fromisoformat(f.name[:10]) for f in files)
        empties_inside = sorted(
            date.fromisoformat(f.name[:10])
            for f in (args.cache_dir / str(season)).glob("*.empty")
            if game_days[0] <= date.fromisoformat(f.name[:10]) <= game_days[-1])

        outputs = write_season(swings, args.out_dir, season, fmt)
        out_desc = ", ".join(f"{o.name} ({o.stat().st_size / 1e6:.1f} MB)" for o in outputs)

        tracked = swings[swings["bat_speed"].notna()] if "bat_speed" in swings else swings.iloc[0:0]
        missing_cols = [c for c in REQUIRED_TRACKING if c not in swings.columns]
        report += [
            f"== {season}",
            f"days with games cached: {len(files)}   empty days: {n_empty}",
            f"date range: {swings['game_date'].min():%Y-%m-%d} to {swings['game_date'].max():%Y-%m-%d}",
            f"total pitches: {total_pitches:,}   swings kept: {len(swings):,}   "
            f"bunts flagged: {int(swings['is_bunt'].sum()):,}",
            f"output: {out_desc}   [{swings.shape[1]} columns]",
            f"no-game days inside the season ({len(empties_inside)}): "
            + (", ".join(d.strftime("%m-%d") for d in empties_inside) or "none"),
        ]
        if len(empties_inside) > 12:
            report.append("   ^ more blank days than expected. To re-pull them, delete those "
                          ".empty files in savant_cache and rerun.")
        if missing_cols:
            report.append(f"MISSING COLUMNS: {missing_cols}")
        report.append("share of swings with each tracking field:")
        for col in REQUIRED_TRACKING + ["attack_angle", "attack_direction", "swing_path_tilt"]:
            if col in swings:
                report.append(f"   {col:<45} {swings[col].notna().mean():6.1%}")

        ix, iy = ("intercept_ball_minus_batter_pos_x_inches",
                  "intercept_ball_minus_batter_pos_y_inches")
        if ix in swings and iy in swings and len(tracked):
            outcome = pd.Series("foul", index=swings.index)
            outcome[swings["description"].astype(str).str.startswith("hit_into_play")] = "in_play"
            outcome[swings["description"].astype(str).str.contains("swinging|missed")] = "whiff"
            report.append("intercept coverage by outcome (share non-null):")
            for grp, sub in swings.groupby(outcome):
                report.append(f"   {grp:<8} n={len(sub):>7,}   x {sub[ix].notna().mean():6.1%}   "
                              f"y {sub[iy].notna().mean():6.1%}")
            report.append("intercept means by batter side (sign-convention check), inches:")
            for side, sub in swings.groupby("stand", observed=True):
                report.append(
                    f"   {side}  x mean {sub[ix].mean():6.2f}  sd {sub[ix].std():5.2f}   "
                    f"y mean {sub[iy].mean():6.2f}  sd {sub[iy].std():5.2f}   n={sub[iy].notna().sum():,}")
            q = tracked[[ix, iy, "bat_speed", "swing_length"]].describe(
                percentiles=[.01, .5, .99]).T[["min", "1%", "50%", "99%", "max"]]
            report.append("distribution of tracked swings:")
            report += ["   " + line for line in q.round(2).to_string().splitlines()]
        new_cols = sorted(c for c in (header_cols or [])
                          if EXTRA_COLUMN_PATTERN.search(c) and c not in KEEP_COLUMNS
                          and not c.startswith("post_"))
        if new_cols:
            report.append(f"extra swing/contact columns found and kept: {new_cols}")
        report.append("")

    if failures:
        report.append("DAYS THAT FAILED (rerun the script to retry just these):")
        report += [f"   {d}  {why}" for d, why in sorted(failures)]
    else:
        report.append("No failed days.")

    text = "\n".join(report)
    (args.out_dir / "coverage_report.txt").write_text(text, encoding="utf-8")
    log("\n" + text)
    log(f"\nDone. Attach the files in {args.out_dir.resolve()} to the chat.")


# --------------------------------------------------------------------------- main

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    p.add_argument("--workers", type=int, default=3, help="parallel requests (default 3)")
    p.add_argument("--start", help="override start date YYYY-MM-DD (for partial pulls)")
    p.add_argument("--end", help="override end date YYYY-MM-DD")
    p.add_argument("--cache-dir", type=Path, default=Path("savant_cache"))
    p.add_argument("--out-dir", type=Path, default=Path("savant_out"))
    p.add_argument("--build-only", action="store_true", help="skip fetching; rebuild outputs")
    p.add_argument("--max-attempts", type=int, default=7)
    p.add_argument("--backoff", type=float, default=15.0, help="first retry wait, seconds; doubles each retry")
    p.add_argument("--min-delay", type=float, default=1.0)
    p.add_argument("--max-delay", type=float, default=3.0)
    p.add_argument("--read-timeout", type=float, default=180.0)
    p.add_argument("--base-url", default=SAVANT_CSV, help=argparse.SUPPRESS)
    args = p.parse_args()

    failures = [] if args.build_only else run_fetch(args)
    build_outputs(args, failures)


if __name__ == "__main__":
    main()
