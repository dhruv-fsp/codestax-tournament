"""Build the tournament page from the player CSVs and match results.

Run:  python -I slot-list/src/build.py

Writes two pages:
  index.html         full page with names and phone numbers (local only, gitignored)
  public/index.html  hosted page with IGNs and results only (committed, served by Vercel)

Inputs (slot-list/data/):
  T13presentlist.csv, T1presentlist.csv  registered players
  matches.json                           results per match (place, IGN, kills)

Result IGNs that don't match a registered player of that territory are
treated as unregistered and left out of the points.
"""
import csv
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TEMPLATE = Path(__file__).resolve().parent / "template.html"
OUT = ROOT / "index.html"                  # full page with names and phones, never committed
OUT_PUBLIC = ROOT / "public" / "index.html"  # hosted page (Vercel), no personal data
SOURCES = [("T13", DATA_DIR / "T13presentlist.csv"), ("T1", DATA_DIR / "T1presentlist.csv")]


def fix(s: str) -> str:
    """Undo UTF-8 text that was decoded as Windows-1252 and saved again."""
    if s.isascii():
        return s
    b = bytearray()
    for ch in s:
        o = ord(ch)
        if o < 0x80:
            b.append(o)
            continue
        try:
            b += ch.encode("cp1252")
        except UnicodeEncodeError:
            if o <= 0xFF:  # bytes cp1252 leaves undefined come through as C1 chars
                b.append(o)
            else:
                return s
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return s


def clean_phone(s: str) -> str:
    s = (s or "").strip()
    if "E+" in s.upper():  # number mangled by Excel, digits are lost
        return ""
    return s.replace("91#", "")


def key(s: str) -> str:
    """Loose IGN key: the game font drops odd characters, so compare letters and digits only."""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", s).lower())


def load_players():
    players = []
    for territory, path in SOURCES:
        text = path.read_bytes().decode("utf-8-sig")
        for r in csv.DictReader(io.StringIO(text)):
            r = {k: fix(v or "").strip() for k, v in r.items()}
            reg = datetime.strptime(r["CreatedAtIST"].upper(), "%d/%m/%Y, %I:%M:%S %p")
            players.append({
                "id": r["UserId"],
                "territory": r["Territory"] or territory,
                "ign": r["IGN"],
                "name": r["Name"],
                "phone": clean_phone(r["PHONE"]),
                "age": r["Age"],
                "gender": r["Gender"],
                "agent": r["AgentName"],
                "agentCode": r["ReferredBy"],
                "agentPhone": clean_phone(r["AgentPhone"]),
                "attendance": r["Attendance"],
                "registered": reg.strftime("%d %b, %I:%M %p"),
                "_ts": reg.timestamp(),
            })

    # Slots per territory, earliest registration gets slot 1
    order = [t for t, _ in SOURCES]
    for t in order:
        group = sorted((p for p in players if p["territory"] == t), key=lambda p: p["_ts"])
        for i, p in enumerate(group, 1):
            p["slot"] = i
    players.sort(key=lambda p: (order.index(p["territory"]), p["slot"]))
    for p in players:
        del p["_ts"]

    for k in ("ign", "phone", "id"):
        dups = {v: n for v, n in Counter(p[k].lower() for p in players if p[k]).items() if n > 1}
        if dups:
            print(f"WARNING duplicate {k}: {dups}")
    print("players:", {t: sum(p["territory"] == t for p in players) for t in order})
    return players


def load_matches(players):
    path = DATA_DIR / "matches.json"
    if not path.exists():
        return []
    out = []
    for m in json.loads(path.read_text(encoding="utf-8")):
        pool = [p for p in players if p["territory"] == m["territory"]]
        exact = {p["ign"].lower(): p for p in pool}
        loose = {}
        for p in pool:
            loose.setdefault(key(p["ign"]), []).append(p)
        clashes = {k: [p["ign"] for p in v] for k, v in loose.items() if len(v) > 1}
        if clashes:
            print(f"  note: loose match off for {clashes}")

        places = [r["place"] for r in m["results"]]
        if len(places) != len(set(places)):
            sys.exit(f"{m['id']}: a placement is listed twice")

        by_slot = {p["slot"]: p for p in pool}
        results, unregistered, seen = [], [], set()
        for r in sorted(m["results"], key=lambda r: r["place"]):
            if "slot" in r:  # explicit link to a registered player, for IGNs the game shows differently
                p = by_slot.get(r["slot"])
                if not p:
                    sys.exit(f"{m['id']}: no {m['territory']} player in slot {r['slot']}")
                if p["ign"].lower() != r["ign"].lower():
                    print(f"  {m['id']}: '{r['ign']}' linked by slot {r['slot']} to {p['ign']}")
            else:
                p = exact.get(r["ign"].lower())
                if not p:
                    hits = loose.get(key(r["ign"]), [])
                    p = hits[0] if len(hits) == 1 else None
                    if p:
                        print(f"  {m['id']}: '{r['ign']}' matched to {p['ign']}")
            if not p:
                unregistered.append(r["ign"])
                continue
            if p["id"] in seen:
                sys.exit(f"{m['id']}: {p['ign']} is listed twice")
            seen.add(p["id"])
            results.append({"pid": p["id"], "place": r["place"], "kills": int(r["kills"])})

        # Placement counted among registered players only (used if the page is set to that mode)
        for i, r in enumerate(results, 1):
            r["regPlace"] = i

        dnp = [p["ign"] for p in pool if p["id"] not in seen]
        print(f"{m['id']} ({m['map']}): {len(results)} registered played, "
              f"unregistered left out: {unregistered or 'none'}, did not play: {dnp or 'none'}")
        out.append({
            "id": m["id"], "territory": m["territory"], "match": m["match"],
            "map": m.get("map", ""), "date": m.get("date", ""),
            "results": results, "unregistered": len(unregistered),
        })
    return out


def to_js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def render(players, matches, public: bool) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    return (html.replace("/*DATA*/", to_js(players))
                .replace("/*MATCHES*/", to_js(matches))
                .replace("/*PUBLIC*/false", "true" if public else "false"))


def public_view(players, matches):
    """Only territory, slot and IGN. Player ids become T13-05 style keys."""
    new_id = {p["id"]: f"{p['territory']}-{p['slot']:02d}" for p in players}
    pub_players = [{"id": new_id[p["id"]], "territory": p["territory"], "slot": p["slot"], "ign": p["ign"]}
                   for p in players]
    pub_matches = [{**m, "results": [{**r, "pid": new_id[r["pid"]]} for r in m["results"]]} for m in matches]
    return pub_players, pub_matches


def check_no_pii(html: str, players) -> None:
    leaks = []
    for p in players:
        for value in (p["phone"], p["agentPhone"], p["id"]):
            if value and value in html:
                leaks.append(value)
        if p["name"] and f'"{p["name"]}"' in html:
            leaks.append(p["name"])
    for k in ('"name":', '"phone":', '"agentPhone":', '"agent":'):
        if k in html:
            leaks.append(k)
    if leaks:
        sys.exit(f"STOP: public build would include player data, e.g. {leaks[:3]}")


def main():
    players = load_players()
    matches = load_matches(players)

    OUT.write_text(render(players, matches, public=False), encoding="utf-8")
    print("wrote", OUT, "(full, local only)")

    pub_html = render(*public_view(players, matches), public=True)
    check_no_pii(pub_html, players)
    OUT_PUBLIC.parent.mkdir(exist_ok=True)
    OUT_PUBLIC.write_text(pub_html, encoding="utf-8")
    print("wrote", OUT_PUBLIC, "(public: IGNs and results only, no names or phones)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
