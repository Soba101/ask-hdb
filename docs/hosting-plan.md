# Hosting plan (2026-10-29)

Goal: a link on the GitHub page that people can open, at no cost to the owner.

## What GitHub can and cannot do
GitHub stores code and serves static pages (GitHub Pages). It cannot run the Python server or a model. A link in the README must point somewhere else that runs the app, or to a static page.

## Options checked
| Option | Free? | Fits this app? |
|---|---|---|
| Hugging Face Docker Space | No. [Docker Spaces need a paid plan to create](https://huggingface.co/docs/hub/spaces-overview) (PRO). Static Spaces are free. | No (my earlier suggestion was wrong; I had not checked). |
| Render free web service | Yes, no card. [512 MB RAM, 0.1 CPU, sleeps after 15 min, 750 hours a month](https://render.com/docs/free) | Too small: the app uses about 400 MB idle and needs CPU for the map data. Not enough for chat. |
| Google Cloud Run | Free allowance, but a payment method is required | A card is needed, and a surprise bill is possible. |
| Oracle Cloud Always Free | Free allowance, a card is required, capacity is often full, limits changed in 2026 | You run the server yourself. Fragile. |
| This Mac with a Cloudflare tunnel | Free | Works. The Mac must stay on, and a quick tunnel address changes on restart. A stable address needs a domain. |
| GitHub Pages (static) | Free, no card | Map and layers only; the chat cannot run there. |

## Plan
1. **Static demo on GitHub Pages** (free, never sleeps). Export the map data, cards and 3D outlines as files. The map, layers, card, nearby lists and 3D work. Chat and walking routes show "run the app yourself" and link to a short demo video. No keys and no server, so nothing to abuse.
2. **README link** to the demo, the screenshots and the run steps.
3. **Live chat for friends:** the Mac tunnel, started by the owner when wanted, with the free model chain. The address is shared in person, not in the README.
4. **If real public chat is wanted later:** a small rented server (a few dollars a month) with a hosted model. That is the first step that costs money.

## What step 1 needs
- A build script that writes `docs/demo/` (or a `gh-pages` branch): `index.html` and the static files, plus JSON files for `/map/features`, `/map/metrics`, `/map/buildings`, `/sun`, and the per-block cards and amenity lists.
- A small switch in the page: when `window.DEMO` is set, use the files instead of the API and hide chat and routes.
- A size check: per-block cards for 9,496 blocks could be large; generate them on demand from one compressed file or limit them to the facts the card shows.
- A GitHub Actions workflow is optional; the owner can also build locally and push.

## Risks
- Static files expose the same data the app already shows. Licences: HDB/LTA open data and OpenStreetMap (credits already on the page).
- The OpenStreetMap tile server is for light use only. A static demo with many visitors should use a hosted tile provider.
