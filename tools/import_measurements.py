"""Regenerate forge/anatomy/data/measured.json from the open trait datasets.

    python tools/import_measurements.py AVONET.csv FishShapes_specimensv1.csv PanTHERIA.txt

Only the rows named in TAXA are read into the output, together with their
units, specimen identifiers, source and licence. The full dataset files are
not needed at build time and are not kept in the project.

How raw measurements become profile values
  birds    AVONET has no body length, so each trait is size-corrected by the
           cube root of body mass and divided by the all-species median of the
           same ratio. 1.0 therefore means "as long as in the median bird".
           wingspan uses the wing chord ratio times the template default 1.9.
  fish     direct ratios to standard length, divided by the template's base
           ratios (depth 0.34, width 0.15, peduncle/depth 0.30).
  mammals  PanTHERIA head-body length becomes the default `size` in metres.
"""

import csv
import json
import os
import statistics
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "forge", "anatomy", "data", "measured.json")

# profile name -> (dataset, taxon, note)
TAXA = {
    "eagle": ("avonet", "Aquila chrysaetos", ""),
    "duck": ("avonet", "Anas platyrhynchos", ""),
    "chicken": ("avonet", "Gallus gallus", "wild red junglefowl; domestic breeds are heavier"),
    "parrot": ("avonet", "Amazona aestiva", ""),
    "owl": ("avonet", "Strix aluco", ""),
    "heron": ("avonet", "Ardea cinerea", ""),
    "goldfish": ("fishshapes", "Carassius carassius", "congener used as proxy; C. auratus is not in FishShapes v1"),
    "trout": ("fishshapes", "Salmo trutta", ""),
    "eel": ("fishshapes", "Anguilla anguilla", ""),
    "wolf": ("pantheria", "Canis lupus", ""),
    "fox": ("pantheria", "Vulpes vulpes", ""),
    "cat": ("pantheria", "Felis silvestris", "wildcat used as proxy; no head-body length for F. catus"),
    "lion": ("pantheria", "Panthera leo", ""),
    "bear": ("pantheria", "Ursus arctos", ""),
    "deer": ("pantheria", "Cervus elaphus", ""),
    "pig": ("pantheria", "Sus scrofa", "wild boar"),
}

SOURCES = {
    "avonet": {
        "title": "AVONET: morphological, ecological and geographical data for all birds",
        "citation": "Tobias et al. 2022, Ecology Letters 25:581-597, doi:10.1111/ele.13898",
        "url": "https://figshare.com/s/b990722d72a26b5bfead",
        "retrieved_from": "https://github.com/txm676/GlobalFDPDLoss (Data/AVONET_BIRDLIFE.csv, a copy of the "
                          "AVONET1_BirdLife sheet; Figshare refused automated download)",
        "license": "CC BY 4.0",
        "units": "mm, g",
        "level": "species means (BirdLife taxonomy); no specimen identifiers",
    },
    "fishshapes": {
        "title": "FishShapes v1: functionally relevant measurements of teleost shape and size on three dimensions",
        "citation": "Price et al. 2022, Ecology 103(12):e3829, doi:10.1002/ecy.3829",
        "url": "https://zenodo.org/records/6642650",
        "license": "CC0 1.0 per the dataset README and paper; the Zenodo record page says CC BY-NC 4.0",
        "units": "mm, g",
        "level": "individual specimens; SpecimenID is the Smithsonian NMNH (USNM) lot number",
    },
    "pantheria": {
        "title": "PanTHERIA 1.0 (WR05)",
        "citation": "Jones et al. 2009, Ecology 90:2648, doi:10.1890/08-1494.1",
        "url": "https://esapubs.org/archive/ecol/E090/184/",
        "license": "Ecological Archives data paper: free to use with citation",
        "units": "mm, g",
        "level": "species means (MSW05 taxonomy); no specimen identifiers",
    },
}

BIRD = {"leg": "Tarsus.Length", "beak": "Beak.Length_Culmen", "tail": "Tail.Length", "wing": "Wing.Length"}
FISH = ("Standard_length", "Max_body_depth", "Max_fish_width", "Min_caudalpeduncle_depth")


def num(text):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def birds(path, out):
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        rows = list(csv.DictReader(fh))
    ratios = {k: [] for k in BIRD}
    for r in rows:
        m = num(r["Mass"])
        for k, col in BIRD.items():
            v = num(r[col])
            if m and v:
                ratios[k].append(v / m ** (1 / 3))
    med = {k: statistics.median(v) for k, v in ratios.items()}
    by_name = {r["species"].replace("_", " "): r for r in rows}
    for prof, (ds, taxon, note) in TAXA.items():
        if ds != "avonet":
            continue
        r = by_name[taxon]
        cube = num(r["Mass"]) ** (1 / 3)
        rel = {k: num(r[col]) / cube / med[k] for k, col in BIRD.items()}
        out[prof] = {
            "dataset": ds, "taxon": taxon, "note": note, "specimens": [],
            "raw": dict({col: num(r[col]) for col in BIRD.values()}, Mass=num(r["Mass"])),
            "values": {"leg": round(rel["leg"], 2), "beak": round(rel["beak"], 2), "tail": round(rel["tail"], 2),
                       "wingspan": round(1.9 * rel["wing"], 2)},
        }
    return {"species": len(rows), "median_mm_per_cube_root_g": {k: round(v, 3) for k, v in med.items()}}


def fish(path, out):
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for prof, (ds, taxon, note) in TAXA.items():
        if ds != "fishshapes":
            continue
        mine = [r for r in rows if r["Tree_name"] == taxon.replace(" ", "_") and all(num(r[c]) for c in FISH)]
        mean = lambda a, b: statistics.mean(num(r[a]) / num(r[b]) for r in mine)
        out[prof] = {
            "dataset": ds, "taxon": taxon, "note": note,
            "specimens": ["USNM %s" % r["SpecimenID"] for r in mine],
            "raw": [{c: num(r[c]) for c in FISH} for r in mine],
            "values": {"body_height": round(mean("Max_body_depth", "Standard_length") / 0.34, 2),
                       "body_width": round(mean("Max_fish_width", "Standard_length") / 0.15, 2),
                       "peduncle": round(mean("Min_caudalpeduncle_depth", "Max_body_depth") / 0.30, 2)},
        }


def mammals(path, out):
    want = {t: p for p, (ds, t, _) in TAXA.items() if ds == "pantheria"}
    with open(path, encoding="latin-1") as fh:
        for line in fh:
            c = line.split("\t")
            if len(c) > 8 and c[4] in want and num(c[8]):
                prof = want[c[4]]
                out[prof] = {
                    "dataset": "pantheria", "taxon": c[4], "note": TAXA[prof][2], "specimens": [],
                    "raw": {"AdultHeadBodyLen_mm": num(c[8]), "AdultBodyMass_g": num(c[6])},
                    "values": {"size": round(num(c[8]) / 1000.0, 3)},
                }


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    out = {}
    stats = birds(argv[0], out)
    fish(argv[1], out)
    mammals(argv[2], out)
    missing = sorted(set(TAXA) - set(out))
    if missing:
        sys.exit("no usable rows for: " + ", ".join(missing))
    doc = {
        "_about": "GENERATED by tools/import_measurements.py - do not edit by hand. 'values' are laid over the "
                  "profile of the same name after inheritance; 'raw' keeps the original measurements in the "
                  "source's units. Profiles not listed here are still approximations.",
        "_sources": SOURCES,
        "_avonet_reference": stats,
        "_measured": {k: out[k] for k in sorted(out)},
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print("wrote %s (%d profiles)" % (os.path.normpath(OUT), len(out)))


if __name__ == "__main__":
    main(sys.argv[1:])
