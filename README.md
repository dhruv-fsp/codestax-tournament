# codestax-tournament

Slot list and points table for the **Code Stax Solo Tournament** (BGMI, solo, 25 Oct 2026).
Two territories (T13 and T1), two matches each.

The page is a single HTML file with:

- **Points Table**: per match, per territory overall, and combined overall for all territories
- **Slot List**: every registered player and their slot, with search
- Export to Excel (.xlsx), and copy as text (for WhatsApp) or as JSON

## Points

BGMI system: #1 10, #2 6, #3 5, #4 4, #5 3, #6 2, #7–8 1, #9+ 0, plus 1 per finish.
Unregistered players in the lobby are not counted. Placement is the in-game finish position.
Ties go to WWCDs, then placement points, then finishes, then the latest match placement.

## Build

Player CSVs are not in this repo because they contain names and phone numbers.
Put them in `data/` first:

```
data/T13presentlist.csv
data/T1presentlist.csv
```

Then build the page:

```
python -I src/build.py
```

This writes `index.html`. Serve it locally:

```
python -m http.server 8765 --bind 127.0.0.1
```

## Adding a match

Add an entry to `data/matches.json` with the place, in-game IGN and finishes for every player in the lobby.
Players are matched to the registered list by IGN. When the game shows an IGN differently,
add `"slot": <registered slot>` to link it. Anyone not matched is treated as unregistered and left out.
The build prints who was matched, linked, left out and missing, so check that output.
