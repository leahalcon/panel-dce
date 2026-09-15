#!/usr/bin/env python3
"""Genera index.html del Panel DCE a partir de:
  - uno o más calendarios de Google en formato iCal (variable de entorno DCE_ICS_URLS,
    varias direcciones separadas por espacio o salto de línea);
  - la planilla de tareas de Google Sheets exportada como CSV (variable DCE_TASKS_CSV_URL).

Uso: DCE_ICS_URLS="https://..." DCE_TASKS_CSV_URL="https://..." python3 build.py
Sin variables, genera el panel vacío (sirve para probar la plantilla).
"""
import csv, io, json, os, re, sys, unicodedata, urllib.request
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

TZ = ZoneInfo("America/Argentina/Buenos_Aires") if ZoneInfo else timezone(timedelta(hours=-3))
HERE = os.path.dirname(os.path.abspath(__file__))
WEEKS_BACK, WEEKS_AHEAD = 8, 30
MEMBERS = ["Foschi", "Romero", "Garanzini", "Monzón", "Gauto Cabana", "Morali", "Lopardo", "Seia"]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "panel-dce-build/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def classify(title):
    t = norm(title)
    if re.search(r"licencia|guardia|franco|vacacion|carpeta medica|adicional", t):
        return "gua"
    if re.search(r"capacit|curso|jornada|instrucc|tiro|entrenam|examen|evaluac|practica|clase", t):
        return "cap"
    if re.search(r"reunion|administr|sade|sigaf|informe|nota|expediente|patrimonio|inventario|entrega|firma", t):
        return "adm"
    return "otr"


# ---------- calendario ----------
def load_events(urls):
    if not urls:
        return []
    import icalendar, recurring_ical_events
    today = datetime.now(TZ).date()
    start = today - timedelta(weeks=WEEKS_BACK)
    end = today + timedelta(weeks=WEEKS_AHEAD)
    out, n = [], 0
    for url in urls:
        cal = icalendar.Calendar.from_ical(fetch(url))
        for ev in recurring_ical_events.of(cal).between(start, end):
            n += 1
            dtstart = ev.get("DTSTART").dt
            dtend = ev.get("DTEND").dt if ev.get("DTEND") else None
            all_day = not isinstance(dtstart, datetime)
            if all_day:
                d0 = dtstart
                d1 = (dtend - timedelta(days=1)) if isinstance(dtend, date) and dtend > dtstart else dtstart
                s_txt = e_txt = ""
            else:
                if dtstart.tzinfo is None:
                    dtstart = dtstart.replace(tzinfo=TZ)
                dtstart = dtstart.astimezone(TZ)
                if dtend is not None:
                    if dtend.tzinfo is None:
                        dtend = dtend.replace(tzinfo=TZ)
                    dtend = dtend.astimezone(TZ)
                d0 = dtstart.date()
                d1 = dtend.date() if dtend else d0
                if dtend and dtend.time() == datetime.min.time() and dtend.date() > d0:
                    d1 = dtend.date() - timedelta(days=1)  # termina a medianoche → mismo día
                s_txt = dtstart.strftime("%H:%M")
                e_txt = dtend.strftime("%H:%M") if dtend else ""
            title = str(ev.get("SUMMARY", "")).strip() or "(sin título)"
            place = str(ev.get("LOCATION", "") or "").strip()
            desc = str(ev.get("DESCRIPTION", "") or "").strip()
            uid = str(ev.get("UID", ""))
            d = d0
            while d <= d1:
                out.append({
                    "id": f"{uid}@{d.isoformat()}",
                    "date": d.isoformat(),
                    "start": s_txt if d == d0 else "",
                    "end": e_txt if d == d1 else "",
                    "allDay": all_day,
                    "title": title,
                    "type": classify(title),
                    "place": place,
                    "who": "",
                    "notes": desc[:300],
                })
                d += timedelta(days=1)
    # quitar duplicados (mismo título/fecha/hora desde dos calendarios)
    seen, uniq = set(), []
    for e in out:
        k = (e["date"], e["start"], norm(e["title"]))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(e)
    uniq.sort(key=lambda e: (e["date"], e["start"]))
    print(f"calendario: {n} ocurrencias leídas, {len(uniq)} cargadas", file=sys.stderr)
    return uniq


# ---------- tareas ----------
CAT = {"capacitacion": "cap", "jornadas": "cap", "cap": "cap",
       "administrativa": "adm", "administrativo": "adm", "administrativas": "adm", "adm": "adm"}
PRIO = {"alta": "alta", "media": "media", "baja": "baja", "": "media"}
STATUS = {"pendiente": "pend", "pend": "pend", "": "pend",
          "en curso": "curso", "curso": "curso", "en progreso": "curso",
          "hecha": "hecha", "hecho": "hecha", "lista": "hecha", "terminada": "hecha", "ok": "hecha"}


def parse_due(s):
    s = str(s or "").strip()
    if not s:
        return ""
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    print(f"  aviso: fecha límite no reconocida: {s!r}", file=sys.stderr)
    return ""


def load_tasks(url):
    if not url:
        return []
    raw = fetch(url).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(raw)))
    tasks = []
    for i, r in enumerate(rows, 1):
        r = {norm(k): (v or "").strip() for k, v in r.items() if k}
        title = r.get("tarea", "")
        if not title:
            continue
        cat_raw = norm(r.get("bloque", ""))
        cat = next((v for k, v in CAT.items() if k in cat_raw), "adm")
        st = STATUS.get(norm(r.get("estado", "")), "pend")
        tasks.append({
            "id": f"s{i}",
            "cat": cat,
            "title": title,
            "who": r.get("responsable", ""),
            "due": parse_due(r.get("fecha limite", r.get("fecha", ""))),
            "prio": PRIO.get(norm(r.get("prioridad", "")), "media"),
            "status": st,
            "notes": r.get("notas", ""),
        })
    print(f"tareas: {len(tasks)} filas", file=sys.stderr)
    return tasks


def main():
    ics_urls = [u for u in re.split(r"\s+", os.environ.get("DCE_ICS_URLS", "")) if u]
    csv_url = os.environ.get("DCE_TASKS_CSV_URL", "").strip()
    events = load_events(ics_urls)
    tasks = load_tasks(csv_url)
    members = list(MEMBERS)
    for t in tasks:
        if t["who"] and t["who"] not in members:
            members.append(t["who"])
    state = {
        "generatedAt": datetime.now(TZ).strftime("%d/%m/%Y %H:%M"),
        "members": members,
        "events": events,
        "tasks": tasks,
    }
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    payload = json.dumps(state, ensure_ascii=False).replace("</", "<\\/")
    html = tpl.replace("__DCE_STATE__", payload)
    out_dir = os.environ.get("DCE_OUT_DIR", HERE)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html generado ({len(events)} actividades, {len(tasks)} tareas)", file=sys.stderr)


if __name__ == "__main__":
    main()
