# LEO Satellite Constellation Routing

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![NetworkX](https://img.shields.io/badge/NetworkX-graph%20routing-orange)
![MATLAB](https://img.shields.io/badge/MATLAB-mapping-0076A8)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

Analysis of **Low-Earth-Orbit (LEO) mega-constellations** (Starlink, Amazon Project Kuiper and Telesat) and of
**inter-satellite routing** between distant cities. Satellite positions were extracted from the
[SaVi](https://savi.sourceforge.io/) constellation simulator. Each constellation is modelled as a graph of
inter-satellite links (ISLs), and **Dijkstra's algorithm** finds the lowest-latency path from Paris to Los Angeles.
The end-to-end **round-trip time (RTT)** is then computed.

<p align="center">
  <img src="assets/shortest_path_starlink.png" width="800" alt="Starlink shortest path Paris to Los Angeles">
  <br><em>Starlink shortest path Paris → Los Angeles over 6 inter-satellite hops (MATLAB Mapping Toolbox)</em>
</p>

## Results: Paris → Los Angeles

| Constellation | Satellites | Shell altitude | ISL hops | Space-segment distance | End-to-end RTT |
|---|---|---|---|---|---|
| **Starlink** | 1,584 (72 planes × 22) | 550 km | 6 | 10,133 km | **75.1 ms** |
| **Project Kuiper** | 1,296 (36 planes × 36) | 610 km | 7 | 11,128 km | **85.7 ms** |

For comparison, a geostationary (GEO) satellite hop alone adds about 240 ms of RTT. LEO constellations bring
intercontinental latency into the range of terrestrial fibre.

> **Note:** the RTT values above include a fix to the ground ↔ satellite leg, which now uses the true slant range.
> The figures in the original [report](docs/final_report.pdf) (e.g. 74.9 ms for Starlink) were computed before this fix.

## Method

1. **Data extraction (SaVi).** For each constellation, SaVi exports every satellite's latitude, longitude and time to
   periapsis. These exports are stored in `data/*.xlsx`.
2. **Geometry.** Spherical coordinates are converted to Earth-centred Cartesian coordinates at the shell altitude.
3. **Intra-orbit grid.** Each satellite is linked to its previous and next neighbour in the same orbital plane.
4. **ISL graph.** Two satellites are connected when they are less than 2,000 km apart. The edge weight is the
   Euclidean distance.
5. **Routing.** Dijkstra's shortest path runs between the satellite serving Paris and the satellite closest to
   Los Angeles.
6. **Latency.** RTT = 2 × (uplink + ISL path + downlink) / *c*.

<p align="center">
  <img src="assets/starlink_grid_3d.png" width="420" alt="Starlink 3-D intra-orbit grid">
  <br><em>Starlink intra-orbit grid (generated with <code>--plot</code>)</em>
</p>

## Getting started

```bash
git clone https://github.com/AhmadAtwi10/leo-satellite-routing.git
cd leo-satellite-routing
pip install -r requirements.txt

python src/leo_routing.py starlink          # Paris -> Los Angeles over Starlink
python src/leo_routing.py kuiper --plot     # Project Kuiper, also saves output/kuiper_grid.png
```

Options:

| Flag | Description |
|---|---|
| `--src-city`, `--dst-city` | `paris`, `los-angeles`, `london`, `new-york` |
| `--source`, `--target` | override the source/target satellite IDs |
| `--threshold` | maximum ISL length in km (default 2000) |
| `--plot` | save a 3-D plot of the intra-orbit grid |
| `--periapsis` | print each satellite's next periapsis passage in Paris time |

Example output:

```
== Starlink: 1584 satellites, 72 orbits x 22, altitude 550 km
Closest satellite to los-angeles: 1178 (69.2 km)
Shortest path (6 hops): [1, 1285, 1286, 1175, 1176, 1177, 1178]
Space segment distance: 10132.8 km
End-to-end RTT paris <-> los-angeles: 75.147 ms
```

The MATLAB script `matlab/plot_shortest_path_starlink.m` draws the world map above. It needs the Mapping Toolbox.

## Repository structure

```
├── src/leo_routing.py                     # routing + RTT pipeline (all constellations)
├── matlab/plot_shortest_path_starlink.m   # world-map visualisation of the shortest path
├── data/
│   ├── starlink.xlsx, kuiper.xlsx         # SaVi exports used by the script
│   ├── telesat_polar.xlsx, telesat_inclined.xlsx
│   └── starlink_grid.csv                  # pre-computed Starlink intra-orbit grid
├── docs/
│   ├── final_report.pdf                   # full report (SaVi setup, method, results)
│   └── slides.pptx
└── assets/                                # figures
```

## Authors

**Ahmad Atwi**, **Ahmad Harakeh**, **Jamil Abou Ltaif**

Joint project at Université Paris-Saclay, supervised by Dr. Sahar Hoteit and Dr. Alexis Aravanis.

## License

Code released under the [MIT License](LICENSE).
