<div align="center">

# Geomorphic Reclamation Designer

**Open-source QGIS plugin for fluvial-geomorphic mine reclamation design**

Design the drainage network that nature *would* build on your site — and the
stable landform that goes with it — entirely inside QGIS.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![QGIS 3.22+ / 4.x](https://img.shields.io/badge/QGIS-3.22%20%E2%86%92%204.x-green.svg)](https://qgis.org)
[![Qt5 / Qt6](https://img.shields.io/badge/Qt-5%20%7C%206-41cd52.svg)](https://qgis.org)
[![Tests](https://img.shields.io/badge/tests-84%20passing-brightgreen.svg)](tests/)

[Español](README.es.md) · [Documentation](docs/) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md)

</div>

---

## What it is

Conventional mine reclamation builds slopes and benches: straight lines that
look finished on the day of handover and start eroding the day after. The
**fluvial-geomorphic approach** does the opposite — it works out the drainage
network that would form naturally on that site, with those materials and that
climate, and builds *that*. The result needs no long-term maintenance because it
is already in equilibrium.

This plugin brings that whole workflow into QGIS:

```
boundary + valley bottoms + DEM
        │
        ├─ hydrology ......... rational-method peak flow, trapezoidal section,
        │                      Shields tractive force, Manning check
        ├─ long profile ...... concave, monotone Hermite (Fritsch–Carlson)
        ├─ plan view ......... meanders after Williams (1986), or type-A zigzag
        │                      where the slope exceeds 4 %
        ├─ hillslope relief .. ridge divides, sub-ridges at meander apexes,
        │                      swales, ridge saddles
        ├─ surface ........... TIN design surface, contours, sub-watersheds
        └─ earthworks ........ cut/fill balance, haul regions and routes
```

**Every element is a QGIS layer**, organised into groups and subgroups, with the
hydraulic properties carried as **editable attributes**. Edit any ridge, swale
or channel by hand with the standard QGIS tools and regenerate from there — the
workflow is re-entrant at every phase, which is the whole point.

## Highlights

| | |
|---|---|
| 🗺️ **Native QGIS** | No round-trip through CAD. Layers, attributes, styles, the layer tree, the map canvas — all of it |
| 📐 **Method-faithful** | Every equation traceable to the published literature. `tests/test_libro.py` verifies each one against its citation |
| ✅ **Design checker** | 22 built-in checks (closed sinks, crossing breaklines, tractive force, drainage density, slope limits…) with a filterable, clickable error log |
| ♻️ **Re-entrant** | Edit any phase by hand and regenerate. The project stores *references* to geometries, not copies |
| 🤖 **Optional local AI** | Optimise the design against cut/fill, haul distance or dozer-pushability with a model running on **your own machine** (Ollama / LM Studio). No cloud service: your design never leaves your computer. The only outbound connection is an **opt-in, off-by-default** web search for reference values — see [`SECURITY.md`](SECURITY.md) |
| 🌍 **Bilingual** | Full EN/ES interface guide. Setting names stay in English in both so they match the literature |
| 🧩 **QGIS 3.22 → 4.x** | Qt5 and Qt6, single codebase |

## Install

**From the plugin manager** (once published): *Plugins → Manage and Install
Plugins → All →* search for *Geomorphic Reclamation Designer*.

**From a ZIP:**

1. Download the latest `geomorphic_reclamation_designer_vX.Y.Z.zip` from
   [Releases](../../releases), or build it yourself with
   `python scripts/build_zip.py`.
2. *Plugins → Manage and Install Plugins → Install from ZIP.*
3. Enable **Geomorphic Reclamation Designer**. A toolbar button and a
   *Geomorphic Reclamation* menu appear.

**Requirements**: QGIS ≥ 3.22 (including 4.x), a **projected CRS in metres**
(e.g. EPSG:25830), and a DEM of the starting terrain. No pip dependencies.

## Quick start

1. **Settings** — enter the *local variables* measured on a stable natural
   reference area with the same material and climate: ridge-to-head distance,
   **outlet slope** (the single most critical value), 2yr-1h and 50yr-6h storm
   depths, target drainage density ± variance.
2. **Setup** — draw the boundary polygon and the valley-bottom lines (rough 2D,
   dendritic). Pick boundary → main channel → transition point → DEM. The panel
   shows area, elevations, valley length and drainage density with a
   green/red light.
3. **Channels** — add tributaries (validated against the method's rules) and set
   each channel's geometry and watershed parameters.
4. **Output** — *Draw Design Surface* (ridges + TIN + contours), then
   *Update Cut/Fill*.
5. **Iterate** — out of balance? Edit ridges or swales, or change elevations and
   settings, and regenerate. Repeat until drainage density and balance are both
   green.
6. **Check Design** at any point for the error log.

Full parameter guide: the **Help** button inside the plugin opens a bilingual
guide documenting all 97 settings and what happens when you change each one.

## Documentation

| | |
|---|---|
| [`docs/INSTALACION.md`](docs/INSTALACION.md) | Install and requirements |
| [`docs/DESARROLLO.md`](docs/DESARROLLO.md) | **How to continue development** |
| [`docs/BUILD.md`](docs/BUILD.md) | Building the installable ZIP |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | How the engine is put together |
| [`docs/MCP_QGIS.md`](docs/MCP_QGIS.md) | Driving QGIS from the editor via MCP |
| [`AGENTS.md`](AGENTS.md) | Working contract for AI coding agents |
| [`context/`](context/) | Project memory: method equations with citations, bug catalogue, decisions, invariants |

## The method

The plugin implements the published **fluvial-geomorphic landform design
method** (Natural Regrade with GeoFluv™), developed by Nicholas Bugosh and
described in the literature below. Every equation in the engine is traceable to
a citation in [`context/01_metodo_geofluv.md`](context/01_metodo_geofluv.md).

- **Bugosh, N. & Martín Duque, J.F. (2024).** *Geomorphic Reclamation Design.* — primary reference
- **Williams, G.P. (1986).** River meanders and channel size. *Journal of Hydrology* 88, 147–164.
- **Rosgen, D. (1996).** *Applied River Morphology.*
- **Dunne, T. & Leopold, L.B. (1978).** *Water in Environmental Planning.*
- **Martín Duque, J.F. et al. (2017).** Geomorphic reclamation for reestablishment of landform stability at a watershed scale in mined sites: El Machorro Mine, Spain. *Ecological Engineering.*
- **Bugosh, N. & Epp, E. (2019).** Evaluating sediment production from native and fluvial geomorphic-reclamation watersheds at La Plata Mine. *Catena* 174, 383–398.

> **Trademark and naming notice.** *GeoFluv™* and *Natural Regrade®* are
> trademarks of their respective owners (N. Bugosh / Carlson Software). This
> project is an **independent, open-source implementation of the published
> method**. It is not a derivative of, affiliated with, or endorsed by Carlson
> Software, and it is not compatible with or a replacement for their product.
>
> The plugin's name uses *"geomorphic reclamation"*, the standard descriptive
> term for the discipline. It is **not** the official companion software of
> *Geomorphic Reclamation Design* (2024); that book is cited here as a
> **source**, exactly as any scientific work is cited by an independent
> implementation of the methods it describes. Any errors in this implementation
> are ours, not its authors'.

## Who is behind this

Developed by **Samuel Sáez López**, with **Emilio Trigueros** — the same team
behind **[opengeorock.org](https://opengeorock.org/)**, working at the
**Universitat Politècnica de Cartagena (UPCT)** and **IMGA**.

The group's line of work is open, reproducible tooling for mining and applied
geology: making methods that until now lived inside expensive proprietary
software available to anyone with QGIS — public administrations, small
consultancies, universities and the mining operations that have to do the
restoration.

If this is useful to you, tell us how you used it. Field feedback from real
sites is what makes the calibration better.

## Contributing

Contributions are very welcome — bug reports with a reproducible case
especially. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first; it explains
the workflow, the conventions and the [CLA](CLA.md) you need to sign.

If you are using an AI coding assistant, point it at
[`AGENTS.md`](AGENTS.md) — it is written for exactly that.

## License

**AGPL-3.0-or-later.** See [`LICENSE`](LICENSE).

In plain words:

- ✅ **Free to use**, personally and professionally, for commercial projects,
  forever. No fee, no registration, no phone-home.
- ✅ **Free to modify** and to redistribute.
- ⚠️ If you distribute it, or **offer it to users over a network** (a web
  service, SaaS, an API), you must publish your source under the same license.
  That is AGPL §13, and it is the point.
- 📄 Contributions require the [CLA](CLA.md), which lets the author offer the
  project under a **separate commercial license** to organisations that want to
  run it as a network service without publishing their own code.

The code is open source and will stay open source. The CLA exists so that a
future commercial-service option remains possible — not to close anything that
is open today.

---

<div align="center">
<sub>© 2026 Samuel Sáez López and contributors · AGPL-3.0-or-later ·
</div>
