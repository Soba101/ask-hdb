# Walking routes: our own router against OneMap (2026-10-29)

## Why
OneMap needs a login that cannot live in a static page, has a quota, and can be down. We built our own router from OpenStreetMap paths
(`src/ask_hdb/geo/walk.py`, built by `scripts/build_walk_graph.py`) and compared it with OneMap on the same pairs.

## What it is
- Source: the BBBike Singapore extract of OpenStreetMap (78.5 MB, 25 Oct 2026, ODbL), checksum verified.
- Graph: 254,394 walkable ways, 709,972 nodes, 803,270 edges, 18 MB. Only the biggest connected network is kept.
- Cost per metre: footpaths 1.0, residential 1.1, service roads 1.15, big roads up to 1.6, stairs 1.5. Walking speed 1.39 m/s.
- Search: A* on a heap. One route takes about 2 ms in memory and the graph loads in 0.3 s (about 240 MB of memory).
- Steps are written from road names and turn angles. OSM has few names on footpaths, so many steps read "the footpath".

## The test (`scripts/compare_routing.py`)
60 random block to nearby-place pairs (supermarket, MRT exit, bus stop), seed 7, each routed by both. OneMap is the reference for distance only.

| Measure | Result |
|---|---|
| Both routed | 60 of 60 (before keeping the main network, ours failed on 3) |
| Ours / OneMap distance, median | 1.13 (ours is 13% longer) |
| Within 10% of OneMap | 40% |
| Within 25% of OneMap | 61% |
| Detour (route / straight line), median | ours 1.67, OneMap 1.39 |
| Median gap between the two lines | 20 m (90th percentile 111 m) |
| Time per route | ours 2 ms |

By trip type (ratio ours / OneMap, median): MRT 1.04, supermarket 1.17, bus stop 1.22.
By straight-line distance: under 200 m 1.33 (38% within 25%); 200 to 600 m 1.10 (71%); over 600 m 1.08 (78%).
Nine of 60 pairs were more than 1.5 times OneMap's distance, mostly short bus-stop trips. Four were shorter than 0.8 times.

## Why ours is worse on short trips
Checked one case (a bus stop 142 m away: ours 1,215 m, OneMap 189 m). Around the start and around the stop, OpenStreetMap
has two small pockets of paths with a 71 m gap between them. Relaxing the access=private rule changed nothing. OneMap crosses the gap
(probably void decks and open links that OSM does not map). Our router can only go the long way round.

## Verdict
- **OneMap is more accurate**, especially for short trips. Use it when it is available.
- **Ours is good enough as a backup and for the static demo:** it matches OneMap well on longer trips (MRT median 1.04), works with no login, no quota
  and no network, and answers in 2 ms.
- To avoid showing a clearly wrong route, a route longer than 3 times the straight line plus 150 m is dropped, and the page says no route was found.
- In the live app, OneMap stays first. Our router answers only when OneMap has no login, hits its quota or is down. That answer is labelled "OpenStreetMap paths".

## Not done
- Linking the pockets (for example by joining paths that lie within a few metres across an open area) could cut the short-trip errors.
  It needs a map review, because a wrong link would make a route go through a building.
- Step text is plain. It does not name crossings or overhead bridges.
