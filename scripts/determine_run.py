"""
determine_run.py
-----------------
Ermittelt bei geplanten (nicht manuellen) Laeufen des Workflows automatisch,
welcher der 4 taeglichen Laeufe (P4/P5/P5.5/P1) gerade dran ist - basierend
auf der aktuellen Uhrzeit in Europe/Berlin (automatisch MESZ/MEZ-korrekt,
keine manuelle Umstellung im Oktober noetig).

GitHubs Cron-Trigger fuer den "schedule"-Event ist bei einem 5-Minuten-Takt
nachweislich unzuverlaessig: in der Praxis kommt oft nur ein einziger Tick
pro Tag an, teils mehrere Stunden verspaetet (Ursache 1). Es gibt deshalb
KEINE Obergrenze mehr fuer die Verspaetung: Sobald die Zielzeit eines Laufs
erreicht ist, wird er beim naechsten ankommenden Tick nachgeholt - egal wie
spaet dieser Tick eintrifft.

Ein Dedupe-Check verhindert dabei, dass derselbe Lauf durch mehrere Ticks
am selben Tag doppelt ausgefuehrt wird (er prueft dazu generated_at_utc in
der jeweiligen *_latest.json).
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")

TARGETS = {
    "p4": (14, 45),
    "p5": (15, 25),
    "p55": (17, 0),
    "p1": (17, 15),
}


def already_done_today(run, now_berlin):
    path = f"data/{run}_latest.json"
    if not os.path.exists(path):
        return False
        try:
            with open(path) as fh:
                snap = json.load(fh)
                gen = datetime.fromisoformat(snap["generated_at_utc"])
                return gen.astimezone(BERLIN).date() == now_berlin.date()
        except Exception:
            return False


def pick_run(now_berlin):
    for run, (hour, minute) in TARGETS.items():
        target = now_berlin.replace(hour=hour, minute=minute, second=0, microsecond=0)
        age_minutes = (now_berlin - target).total_seconds() / 60
        in_window = age_minutes >= 0
        if in_window and not already_done_today(run, now_berlin):
            return run
    return None


def main():
now_berlin = datetime.now(BERLIN)
chosen = pick_run(now_berlin)
with open(os.environ["GITHUB_OUTPUT"], "a") as f:
    if chosen:
        f.write(f"run={chosen}\n")
        f.write("skip=false\n")
        print(f"Gewaehlter Lauf: {chosen}")
    else:
        f.write("run=none\n")
        f.write("skip=true\n")
        print("Kein Lauf faellig - wird uebersprungen.")


if __name__ == "__main__":
    main()
