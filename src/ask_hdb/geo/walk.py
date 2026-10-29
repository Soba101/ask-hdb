"""A walking router built from an OpenStreetMap extract: a graph of paths, Dijkstra, and turn-by-turn text.

The graph is built offline by scripts/build_walk_graph.py. OSM may miss void decks and covered links, so routes are estimates.
"""

import gzip
import heapq
import math
import xml.etree.ElementTree as ET
from itertools import pairwise
from pathlib import Path

import numpy as np

SPEED_MS = 1.39  # about 5 km/h; OneMap's own times work out near this speed
WALKABLE = {"footway", "pedestrian", "path", "steps", "cycleway", "residential", "service", "living_street", "unclassified",
            "tertiary", "secondary", "primary", "track", "corridor"}
# Cost per metre by kind of way: footpaths are preferred, big roads and stairs are avoided when a good alternative exists.
COST = {"footway": 1.0, "pedestrian": 1.0, "path": 1.0, "corridor": 1.0, "cycleway": 1.0, "living_street": 1.05,
        "residential": 1.1, "service": 1.15, "track": 1.2, "unclassified": 1.2, "tertiary": 1.25, "secondary": 1.4,
        "primary": 1.6, "steps": 1.5}
EARTH = 6371008.8


def metres(lat1, lng1, lat2, lng2):
    dy = math.radians(lat2 - lat1) * EARTH
    dx = math.radians(lng2 - lng1) * EARTH * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _walkable(tags):
    kind = tags.get("highway")
    # access=private is common on estate paths people do walk, so only an explicit ban (foot=no, access=no) removes a way.
    if tags.get("foot") == "no" or tags.get("access") == "no" and tags.get("foot") != "yes":
        return None
    if kind in WALKABLE or (kind in ("trunk", "motorway") and tags.get("foot") == "yes"):
        return kind if kind in COST else "primary"
    return None


def read_osm(path):
    """(ways, coordinates): walkable ways as (node ids, kind, name) and {node id: (lat, lng)} for the nodes they use."""
    ways = []
    with gzip.open(path, "rb") as handle:
        for _, element in ET.iterparse(handle, events=("end",)):
            if element.tag == "way":
                tags = {t.get("k"): t.get("v") for t in element.iter("tag")}
                kind = _walkable(tags)
                if kind:
                    ways.append(([int(n.get("ref")) for n in element.iter("nd")], kind, tags.get("name", "")))
            if element.tag in ("way", "node", "relation"):
                element.clear()
    needed = {node for nodes, _, _ in ways for node in nodes}
    coordinates = {}
    with gzip.open(path, "rb") as handle:
        for _, element in ET.iterparse(handle, events=("end",)):
            if element.tag == "node":
                identifier = int(element.get("id"))
                if identifier in needed:
                    coordinates[identifier] = (float(element.get("lat")), float(element.get("lon")))
            if element.tag in ("way", "node", "relation"):
                element.clear()
    return ways, coordinates


def build_graph(ways, coordinates):
    """Arrays: node lat/lng, edges (a, b, length m, cost, way id), and the way table (kind, name)."""
    index = {}
    lat, lng = [], []
    a, b, length, cost, way_id = [], [], [], [], []
    table = []
    for nodes, kind, name in ways:
        table.append((kind, name))
        previous = None
        for node in nodes:
            if node not in coordinates:
                previous = None
                continue
            if node not in index:
                index[node] = len(lat)
                lat.append(coordinates[node][0]); lng.append(coordinates[node][1])
            current = index[node]
            if previous is not None and previous != current:
                metre = metres(lat[previous], lng[previous], lat[current], lng[current])
                a.append(previous); b.append(current); length.append(metre); cost.append(metre * COST[kind]); way_id.append(len(table) - 1)
            previous = current
    graph = {"lat": np.array(lat), "lng": np.array(lng), "a": np.array(a, dtype=np.int32), "b": np.array(b, dtype=np.int32),
             "length": np.array(length, dtype=np.float32), "cost": np.array(cost, dtype=np.float32),
             "way": np.array(way_id, dtype=np.int32), "ways": np.array(table, dtype=object)}
    return largest_component(graph)


def largest_component(graph):
    """Keep only the paths connected to the biggest network, so a point never snaps onto an island nobody can reach."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    count = len(graph["lat"])
    matrix = coo_matrix((np.ones(len(graph["a"])), (graph["a"], graph["b"])), shape=(count, count))
    _, label = connected_components(matrix, directed=False)
    keep = label == np.bincount(label).argmax()
    remap = np.cumsum(keep) - 1
    edge = keep[graph["a"]] & keep[graph["b"]]
    out = {"lat": graph["lat"][keep], "lng": graph["lng"][keep], "ways": graph["ways"]}
    out["a"], out["b"] = remap[graph["a"][edge]].astype(np.int32), remap[graph["b"][edge]].astype(np.int32)
    for name in ("length", "cost", "way"):
        out[name] = graph[name][edge]
    return out


def save(graph, path):
    np.savez_compressed(path, **{k: v for k, v in graph.items() if k != "ways"},
                        way_kind=np.array([k for k, _ in graph["ways"]]), way_name=np.array([n for _, n in graph["ways"]]))


class Router:
    """Shortest walking path over the graph. Loads the arrays once; one route is a heap search (A*)."""

    def __init__(self, path):
        data = np.load(Path(path), allow_pickle=False)
        self.lat, self.lng = data["lat"], data["lng"]
        self.kind, self.name = data["way_kind"], data["way_name"]
        a, b, length, cost, way = data["a"], data["b"], data["length"], data["cost"], data["way"]
        count = len(self.lat)
        # Both directions, in compressed form: neighbours of node n are start[n]:start[n + 1] of the sorted arrays.
        src = np.concatenate([a, b]); dst = np.concatenate([b, a])
        order = np.argsort(src, kind="stable")
        self.dst = dst[order]
        self.length = np.concatenate([length, length])[order]
        self.cost = np.concatenate([cost, cost])[order]
        self.way = np.concatenate([way, way])[order]
        self.start = np.searchsorted(src[order], np.arange(count + 1))
        # A grid of 0.001 degree (about 110 m) cells, as sorted arrays: cheap in memory and quick to search.
        keys = self._key((self.lat * 1000).astype(np.int64), (self.lng * 1000).astype(np.int64))
        self.cell_order = np.argsort(keys, kind="stable")
        self.cell_keys = keys[self.cell_order]

    @staticmethod
    def _key(cell_lat, cell_lng):
        return cell_lat * 100000 + cell_lng

    def _cell(self, cx, cy):
        key = self._key(cx, cy)
        low, high = np.searchsorted(self.cell_keys, [key, key + 1])
        return self.cell_order[low:high]

    def nearest(self, lat, lng, reach=300):
        """The graph node closest to a point, or None if none is within `reach` metres."""
        cx, cy = int(lat * 1000), int(lng * 1000)
        best, best_d = None, reach
        for ring in (2, 3):  # two rings so a corner hit in a near cell cannot beat a closer node one cell further
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    for node in self._cell(cx + dx, cy + dy):
                        d = metres(lat, lng, self.lat[node], self.lng[node])
                        if d < best_d:
                            best, best_d = node, d
            if best is not None:
                return best
        return best

    def path(self, source, target):
        """Node list of the cheapest path, by A* with a straight-line estimate, or None when not connected."""
        goal_lat, goal_lng = self.lat[target], self.lng[target]
        best = {source: 0.0}
        came = {}
        queue = [(0.0, source)]
        while queue:
            _, node = heapq.heappop(queue)
            if node == target:
                out = [node]
                while out[-1] in came:
                    out.append(came[out[-1]])
                return out[::-1]
            for i in range(self.start[node], self.start[node + 1]):
                nxt = int(self.dst[i])
                new = best[node] + float(self.cost[i])
                if new < best.get(nxt, 1e18):
                    best[nxt] = new
                    came[nxt] = node
                    heuristic = metres(self.lat[nxt], self.lng[nxt], goal_lat, goal_lng)
                    heapq.heappush(queue, (new + heuristic, nxt))
        return None

    def route(self, start, end):
        """{distance_m, duration_s, line, steps} between two (lat, lng) points, or None."""
        a, b = self.nearest(*start), self.nearest(*end)
        if a is None or b is None:
            return None
        nodes = self.path(a, b)
        if nodes is None:
            return None
        return self.describe(nodes, start, end)

    def edge(self, u, v):
        """The cheapest edge from u to v (two ways can run between the same nodes)."""
        found = [i for i in range(self.start[u], self.start[u + 1]) if self.dst[i] == v]
        return min(found, key=lambda i: self.cost[i]) if found else None

    def describe(self, nodes, start, end):
        line = [[float(self.lng[n]), float(self.lat[n])] for n in nodes]
        line = [[start[1], start[0]], *line, [end[1], end[0]]]
        pieces = []  # (way id, metres) per run of one way
        for u, v in pairwise(nodes):
            i = self.edge(u, v)
            way, metre = int(self.way[i]), float(self.length[i])
            if pieces and pieces[-1][0] == way:
                pieces[-1][1] += metre
                pieces[-1][4], pieces[-1][5] = u, v  # the last edge of this run
            else:
                pieces.append([way, metre, u, v, u, v])
        total = sum(p[1] for p in pieces) + metres(*start, self.lat[nodes[0]], self.lng[nodes[0]]) + metres(
            self.lat[nodes[-1]], self.lng[nodes[-1]], *end)
        return {"distance_m": round(total), "duration_s": round(total / SPEED_MS), "line": line,
                "steps": self.steps(pieces, nodes), "pieces": len(pieces)}

    def steps(self, pieces, nodes):
        out = []
        for i, (way, metre, u, v, *_rest) in enumerate(pieces):
            name = str(self.name[way]) or {"steps": "the stairs", "footway": "the footpath", "path": "the path",
                                           "pedestrian": "the walkway", "service": "the service road"}.get(str(self.kind[way]), "the path")
            if str(self.kind[way]) == "steps":
                text = "Take the stairs"
            elif i == 0:
                text = f"Head {self.compass(self.bearing(u, v))} on {name}"
            else:
                turn = (self.bearing(u, v) - self.bearing(pieces[i - 1][4], pieces[i - 1][5])) % 360
                text = f"{self.turn_word(turn)} onto {name}"
            out.append({"text": text, "road": str(self.name[way]), "distance_m": round(metre)})
        return out

    def bearing(self, u, v):
        dy = self.lat[v] - self.lat[u]
        dx = (self.lng[v] - self.lng[u]) * math.cos(math.radians(self.lat[u]))
        return math.degrees(math.atan2(dx, dy)) % 360

    @staticmethod
    def compass(bearing):
        return ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")[int((bearing + 22.5) // 45) % 8]

    @staticmethod
    def turn_word(turn):
        if turn < 25 or turn > 335:
            return "Continue"
        if turn < 60:
            return "Bear right"
        if turn < 135:
            return "Turn right"
        if turn < 225:
            return "Turn back"
        if turn < 300:
            return "Turn left"
        return "Bear left"
