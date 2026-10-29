"""Build data/clean/walk_graph.npz from the OpenStreetMap extract in data/raw/walk/Singapore.osm.gz (BBBike, ODbL)."""

import time
from pathlib import Path

from ask_hdb.geo import walk

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    start = time.time()
    ways, coordinates = walk.read_osm(ROOT / "data/raw/walk/Singapore.osm.gz")
    print(len(ways), "walkable ways,", len(coordinates), "nodes", round(time.time() - start), "s")
    graph = walk.build_graph(ways, coordinates)
    output = ROOT / "data/clean/walk_graph.npz"
    temp = output.with_name("walk_graph.tmp.npz")
    walk.save(graph, temp)
    temp.replace(output)  # an interrupted run never leaves a half-written file
    print(len(graph["lat"]), "graph nodes,", len(graph["a"]), "edges,", output.stat().st_size // 1_000_000, "MB")
