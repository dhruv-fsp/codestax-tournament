"""Add one squad finals match from a quick text list, rebuild the pages, print the standings.

Usage (from slot-list/):
  python -I -B src/finals_add.py --match 1 results.txt          # save + rebuild
  python -I -B src/finals_add.py --match 1 results.txt --dry    # check only, nothing saved

One team per line, as read from the result screen:
  <place> <team> <finishes>              e.g.  1 itachinj11 12     or   1 5 12   (5 = team slot)
  <place> | <ign>=<k>, <ign>=<k>, ...    per-player finishes, summed for the team
<team> can be the team slot or any one player's IGN. Letters and digits are enough
("Try Hard", "TAGCHILLI16" and "chor" style shortcuts work); odd characters can be left out.
Lines that match no finals team are ignored (and listed). Blank lines and # comments are skipped.
"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

FINALS = build.DATA_DIR / "finals.json"
PTS = {1: 10, 2: 6, 3: 5, 4: 4, 5: 3, 6: 2, 7: 1, 8: 1}


def team_index(players, finals):
    by_ign = {p["ign"]: p for p in players}
    idx = []  # (key, ign, slot)
    for tm in finals["teams"]:
        for ign in tm["players"]:
            p = by_ign.get(ign)
            real = p["ign"] if p else ign
            idx.append((build.key(real), real, tm["slot"]))
    return idx


def resolve(name, idx, slots):
    """Return (slot, how) for a team slot number or any member IGN, or (None, reason)."""
    name = name.strip()
    if name.isdigit() and int(name) in slots:
        return int(name), "slot"
    k = build.key(name)
    exact = {ign.lower(): slot for _, ign, slot in idx}
    if name.lower() in exact:
        return exact[name.lower()], "exact"
    hits = {slot for key, _, slot in idx if key == k}
    if len(hits) == 1:
        return hits.pop(), "letters"
    if k and len(k) >= 3:
        part = {slot for key, _, slot in idx if k in key}
        if len(part) == 1:
            return part.pop(), "part of name"
    scored = sorted(((SequenceMatcher(None, k, key).ratio(), ign, slot) for key, ign, slot in idx), reverse=True)
    if scored and scored[0][0] >= 0.8 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.1):
        return scored[0][2], f"close to {scored[0][1]} ({scored[0][0]:.2f})"
    return None, "no match; closest: " + ", ".join(f"{ign} (slot {s})" for _, ign, s in scored[:3])


def parse(lines, idx, slots):
    results, ignored, notes = [], [], []
    for n, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "|" in line:  # per-player form
            place_s, rest = line.split("|", 1)
            place = int(place_s.strip())
            parts = [x.strip() for x in rest.split(",") if x.strip()]
            team_slots, kills = set(), 0
            for part in parts:
                ign, _, k = part.rpartition("=")
                slot, how = resolve(ign, idx, slots)
                if slot is None:
                    notes.append(f"line {n}: '{ign}' {how}")
                    continue
                team_slots.add(slot)
                kills += int(k)
            if len(team_slots) > 1:
                sys.exit(f"line {n}: those players are in different teams: {sorted(team_slots)}")
            if not team_slots:
                ignored.append(line)
                continue
            results.append({"place": place, "slot": team_slots.pop(), "kills": kills})
            continue
        m = re.match(r"^\s*(\d+)\s+(.+?)\s+(\d+)\s*$", line)
        if not m:
            sys.exit(f"line {n}: expected '<place> <team> <finishes>', got: {raw!r}")
        place, team, kills = int(m.group(1)), m.group(2), int(m.group(3))
        slot, how = resolve(team, idx, slots)
        if slot is None:
            ignored.append(f"{line}   <- {how}")
            continue
        if how not in ("slot", "exact"):
            notes.append(f"line {n}: '{team}' -> slot {slot} ({how})")
        results.append({"place": place, "slot": slot, "kills": kills})

    places = [r["place"] for r in results]
    dup_p = sorted({p for p in places if places.count(p) > 1})
    used = [r["slot"] for r in results]
    dup_s = sorted({s for s in used if used.count(s) > 1})
    if dup_p or dup_s:
        sys.exit(f"STOP: place listed twice {dup_p or ''} / team listed twice {dup_s or ''}")
    return sorted(results, key=lambda r: r["place"]), ignored, notes


def standings(teams, matches):
    rows = []
    for tm in teams:
        res = [r for m in matches for r in m["results"] if r["slot"] == tm["slot"]]
        if not res:
            continue
        pp = sum(PTS.get(r["place"], 0) for r in res)
        k = sum(r["kills"] for r in res)
        rows.append((tm["slot"], pp + k, pp, k, sorted(r["place"] for r in res)))
    width = max((len(r[4]) for r in rows), default=0)
    padded = lambda pl: tuple(pl) + (float("inf"),) * (width - len(pl))
    rows.sort(key=lambda r: (-r[1], -r[2], -r[3], padded(r[4]), r[0]))
    return rows


def show(title, teams, rows):
    names = {tm["slot"]: ", ".join(tm["players"]) for tm in teams}
    print(f"\n{title}")
    print(f"{'#':>3}  {'slot':>4}  {'pts':>4}  {'place':>5}  {'fin':>3}  team")
    for i, (slot, total, pp, k, places) in enumerate(rows, 1):
        print(f"{i:>3}  {slot:>4}  {total:>4}  {pp:>5}  {k:>3}  {names[slot]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--match", type=int, required=True)
    ap.add_argument("--date", default="2026-10-25")
    ap.add_argument("--map", default="")
    ap.add_argument("--dry", action="store_true", help="check and print only, save nothing")
    a = ap.parse_args()

    players = build.load_players()
    finals = json.loads(FINALS.read_text(encoding="utf-8"))
    idx = team_index(players, finals)
    slots = {tm["slot"] for tm in finals["teams"]}
    results, ignored, notes = parse(Path(a.results).read_text(encoding="utf-8").splitlines(), idx, slots)

    for line in notes:
        print("  check:", line)
    for line in ignored:
        print("  ignored (not a finals team):", line)
    missing = sorted(slots - {r["slot"] for r in results})
    print(f"match {a.match}: {len(results)} teams read, finishes {sum(r['kills'] for r in results)}, "
          f"teams missing: {missing or 'none'}")

    others = [m for m in finals.get("matches", []) if m["match"] != a.match]
    new = {"match": a.match, "date": a.date, "map": a.map, "results": results}
    all_matches = sorted(others + [new], key=lambda m: m["match"])
    show(f"FINALS MATCH {a.match}", finals["teams"], standings(finals["teams"], [new]))
    show("FINALS OVERALL", finals["teams"], standings(finals["teams"], all_matches))

    if a.dry:
        print("\n(dry run: nothing saved)")
        return
    finals["matches"] = all_matches
    FINALS.write_text(json.dumps(finals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nsaved", FINALS)
    build.main()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
