"""Inter-satellite routing and latency analysis for LEO mega-constellations.

Pipeline (same for every constellation):
  1. Load satellite positions (latitude/longitude exported from SaVi) and convert
     them to Earth-centred Cartesian coordinates at the shell altitude.
  2. Build the intra-orbit grid (each satellite linked to its previous/next
     neighbour in the same orbital plane) and export it as CSV.
  3. Build an inter-satellite link (ISL) graph: two satellites are connected when
     their straight-line distance is below a threshold (default 2000 km).
  4. Run Dijkstra between the satellite serving the source city and the satellite
     serving the destination city, and compute the end-to-end round-trip time
     (ground -> satellite -> ... -> satellite -> ground).

Usage:
    python src/leo_routing.py starlink
    python src/leo_routing.py kuiper --plot
    python src/leo_routing.py starlink --source 1 --target 1178 --threshold 2500
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0
SPEED_OF_LIGHT_KM_S = 299_792.458
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CITIES = {
    "paris": (48.8566, 2.3522),
    "los-angeles": (34.0522, -118.2437),
    "london": (51.5074, -0.1278),
    "new-york": (40.7128, -74.0060),
}


@dataclass(frozen=True)
class Constellation:
    name: str
    data_file: str
    altitude_km: float
    num_orbits: int
    sats_per_orbit: int
    source_sat: int  # satellite serving the source city (Paris) in the report
    target_sat: int  # satellite serving the destination city (Los Angeles) in the report


CONSTELLATIONS = {
    "starlink": Constellation("Starlink", "starlink.xlsx", 550, 72, 22, source_sat=1, target_sat=1178),
    "kuiper": Constellation("Project Kuiper", "kuiper.xlsx", 610, 36, 36, source_sat=993, target_sat=712),
}


# --------------------------------------------------------------------------- geometry
def spherical_to_cartesian(latitude, longitude, altitude_km):
    """Geodetic (spherical Earth) coordinates in degrees/km -> ECEF-like x, y, z in km."""
    lat, lon = np.radians(latitude), np.radians(longitude)
    r = EARTH_RADIUS_KM + altitude_km
    return r * np.cos(lat) * np.cos(lon), r * np.cos(lat) * np.sin(lon), r * np.sin(lat)


def euclidean_distance_3d(x1, y1, z1, x2, y2, z2):
    return np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)


def ground_to_satellite_km(ground_latlon, sat_row, altitude_km):
    """Slant range between a point on the ground (altitude 0) and a satellite."""
    g = spherical_to_cartesian(*ground_latlon, 0)
    s = spherical_to_cartesian(sat_row["Latitude"], sat_row["Longitude"], altitude_km)
    return float(euclidean_distance_3d(*g, *s))


# --------------------------------------------------------------------------- data
def load_constellation(c: Constellation) -> pd.DataFrame:
    df = pd.read_excel(DATA_DIR / c.data_file)
    df = df.dropna(subset=["Satellite_number"]).copy()
    df["Satellite_number"] = df["Satellite_number"].astype(int)
    df = df.set_index("Satellite_number", drop=False)
    df["X"], df["Y"], df["Z"] = spherical_to_cartesian(df["Latitude"], df["Longitude"], c.altitude_km)
    return df


def intra_orbit_grid(df: pd.DataFrame, c: Constellation) -> pd.DataFrame:
    """Link every satellite to its previous and next neighbour in the same orbital plane."""
    rows = []
    for orbit in range(c.num_orbits):
        lo, hi = orbit * c.sats_per_orbit, (orbit + 1) * c.sats_per_orbit
        plane = df[(df["Satellite_number"] > lo) & (df["Satellite_number"] <= hi)]
        n = len(plane)
        for i in range(n):
            cur = plane.iloc[i]
            for nb in (plane.iloc[(i - 1) % n], plane.iloc[(i + 1) % n]):
                rows.append({
                    "Satellite1": int(cur["Satellite_number"]),
                    "Satellite2": int(nb["Satellite_number"]),
                    "Distance": euclidean_distance_3d(cur["X"], cur["Y"], cur["Z"], nb["X"], nb["Y"], nb["Z"]),
                    "Orbit": orbit,
                })
    return pd.DataFrame(rows)


def isl_graph(df: pd.DataFrame, threshold_km: float) -> nx.Graph:
    """Connect every pair of satellites closer than `threshold_km` (weight = distance in km)."""
    ids = df["Satellite_number"].to_numpy()
    xyz = df[["X", "Y", "Z"]].to_numpy()
    dist = np.sqrt(((xyz[:, None, :] - xyz[None, :, :]) ** 2).sum(-1))
    i, j = np.where(np.triu(dist < threshold_km, k=1))
    g = nx.Graph()
    g.add_weighted_edges_from((int(ids[a]), int(ids[b]), float(dist[a, b])) for a, b in zip(i, j))
    return g


def closest_satellite(df: pd.DataFrame, latlon, altitude_km) -> tuple[int, float]:
    """Closest satellite to a city, measured with the city projected to the shell altitude."""
    x, y, z = spherical_to_cartesian(*latlon, altitude_km)
    d = euclidean_distance_3d(df["X"], df["Y"], df["Z"], x, y, z)
    return int(d.idxmin()), float(d.min())


# --------------------------------------------------------------------------- plots
def plot_grid(df: pd.DataFrame, grid: pd.DataFrame, path: Path, title: str):
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(df["X"], df["Y"], df["Z"], color="b", marker="o", s=5)
    for s1, s2 in grid[["Satellite1", "Satellite2"]].itertuples(index=False):
        a, b = df.loc[s1], df.loc[s2]
        ax.plot([a.X, b.X], [a.Y, b.Y], [a.Z, b.Z], color="k", linewidth=0.4)
    ax.set_xlabel("X (km)"); ax.set_ylabel("Y (km)"); ax.set_zlabel("Z (km)")
    ax.set_title(title)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- main
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("constellation", choices=CONSTELLATIONS)
    p.add_argument("--src-city", default="paris", choices=CITIES)
    p.add_argument("--dst-city", default="los-angeles", choices=CITIES)
    p.add_argument("--source", type=int, help="source satellite id (default: value used in the report)")
    p.add_argument("--target", type=int, help="target satellite id (default: value used in the report)")
    p.add_argument("--threshold", type=float, default=2000, help="max ISL distance in km (default 2000)")
    p.add_argument("--out", type=Path, default=Path("output"), help="output directory")
    p.add_argument("--plot", action="store_true", help="save a 3-D plot of the intra-orbit grid")
    p.add_argument("--periapsis", action="store_true", help="print time of periapsis passage (Europe/Paris)")
    args = p.parse_args(argv)

    c = CONSTELLATIONS[args.constellation]
    args.out.mkdir(parents=True, exist_ok=True)
    df = load_constellation(c)
    print(f"== {c.name}: {len(df)} satellites, {c.num_orbits} orbits x {c.sats_per_orbit}, altitude {c.altitude_km} km")

    grid = intra_orbit_grid(df, c)
    grid_csv = args.out / f"{args.constellation}_grid.csv"
    grid.to_csv(grid_csv, index=False)
    print(f"Intra-orbit grid: {len(grid)} directed links -> {grid_csv}")
    if args.plot:
        png = args.out / f"{args.constellation}_grid.png"
        plot_grid(df, grid, png, f"{c.name} intra-orbit grid")
        print(f"3-D grid plot -> {png}")

    src_city, dst_city = CITIES[args.src_city], CITIES[args.dst_city]
    near_dst, d_near = closest_satellite(df, dst_city, c.altitude_km)
    print(f"Closest satellite to {args.dst_city}: {near_dst} ({d_near:.1f} km)")

    source = args.source or c.source_sat
    target = args.target or c.target_sat
    g = isl_graph(df, args.threshold)
    path = nx.dijkstra_path(g, source, target, weight="weight")
    space_km = nx.dijkstra_path_length(g, source, target, weight="weight")

    print(f"\nShortest path ({len(path) - 1} hops): {path}")
    print(f"Space segment distance: {space_km:.1f} km")
    for sat in path:
        print(f"  sat {sat:>5}: lat {df.at[sat, 'Latitude']:9.4f}, lon {df.at[sat, 'Longitude']:10.4f}")

    up_km = ground_to_satellite_km(src_city, df.loc[source], c.altitude_km)
    down_km = ground_to_satellite_km(dst_city, df.loc[target], c.altitude_km)
    rtt = lambda km: 2 * km / SPEED_OF_LIGHT_KM_S * 1000  # ms
    print(f"\nRTT {args.src_city} <-> sat {source}: {rtt(up_km):.3f} ms ({up_km:.1f} km)")
    print(f"RTT sat {source} <-> sat {target} (ISLs): {rtt(space_km):.3f} ms")
    print(f"RTT sat {target} <-> {args.dst_city}: {rtt(down_km):.3f} ms ({down_km:.1f} km)")
    print(f"End-to-end RTT {args.src_city} <-> {args.dst_city}: {rtt(up_km + space_km + down_km):.3f} ms")

    if args.periapsis:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("Europe/Paris")
        except ImportError:  # Python < 3.9
            import pytz
            tz = pytz.timezone("Europe/Paris")
        now = datetime.now(timezone.utc)
        col = "Time_to_periapsis"
        print("\nTime of periapsis passage (Europe/Paris):")
        for sat, secs in df[col].items():
            print(f"  sat {sat:>5}: {(now + timedelta(seconds=float(secs))).astimezone(tz):%Y-%m-%d %H:%M:%S %Z}")


if __name__ == "__main__":
    main()
