# codestax-tournament

Slot list and points table for the **Code Stax Solo Tournament** (BGMI, solo, 25 Oct 2026).
Two territories (T13 and T1), two matches each.

The page is a single HTML file with:

- **Points Table**: per match, per territory overall, and combined overall for all territories
- **Slot List**: every registered player and their slot, with search
- Export to Excel (.xlsx), and copy as text (for WhatsApp) or as JSON

## Points

BGMI system: #1 10, #2 6, #3 5, #4 4, #5 3, #6 2, #7–8 1, #9+ 0, plus 1 per finish.
Placement is the in-game finish position.
Ties go to placement points, then finishes, then the best placement (#3 beats #10). Every player gets their own rank.

## Hosting on Vercel

`public/index.html` is the hosted page. It has IGNs, slots and results only: no names, phone numbers or agents.

1. In Vercel, **Add New → Project** and import this repo.
2. Framework preset: **Other**. Leave the build command empty. `vercel.json` already sets the output directory to `public`.
3. Deploy. Every push to `main` redeploys.

## Build

Player CSVs are not in this repo because they contain names and phone numbers.
Put them in `data/` first:

```
data/T13presentlist.csv
data/T1presentlist.csv
```

Then build:

```
python -I src/build.py
```

This writes two pages:

- `index.html`: full page with names and phones, for organisers. Local only, gitignored.
- `public/index.html`: the hosted page. The build stops if any name, phone or user id would end up in it.

Commit and push `public/index.html` to update the live site. Serve the full page locally with:

```
python -m http.server 8765 --bind 127.0.0.1
```

## Adding a match

Add an entry to `data/matches.json` with the place, in-game IGN and finishes for every player in the lobby.
Players are matched to the registered list by IGN. When the game shows an IGN differently,
add `"slot": <registered slot>` to link it. Anyone not matched to the list is ignored.
The build prints who was matched, linked, left out and missing, so check that output.
