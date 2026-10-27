"""Genera un visor HTML (un solo archivo) con las civilizaciones y el catálogo de unidades del .dat."""
from __future__ import annotations

import json
import re
from pathlib import Path

RECURSOS = {0: "food", 1: "wood", 2: "stone", 3: "gold"}
CLASES = {
    1: "Infantry", 2: "Turtle Ships", 5: "Elephants", 8: "Cavalry", 11: "All Buildings",
    13: "Stone Defense", 15: "Archers", 16: "Ships", 17: "Rams", 19: "Unique Units",
    20: "Siege", 21: "Buildings", 22: "Walls & Gates", 23: "Gunpowder", 25: "Monks",
    26: "Castles", 27: "Spearmen", 28: "Cav. Archers", 29: "Eagles", 30: "Camels",
    34: "Fishing Ships", 35: "Mamelukes", 36: "Heroes", 39: "Skirmishers",
}
CLASES_UNIDAD = {0: "Archer", 6: "Infantry", 12: "Cavalry", 13: "Siege", 18: "Monk", 22: "Warship",
                 23: "Mounted Gunpowder", 35: "Petard", 36: "Cav. Archer", 38: "Skirmisher", 44: "Hand Cannoneer",
                 47: "Scout", 51: "Packed Trebuchet", 54: "Trebuchet", 55: "Scorpion", 56: "Raider",
                 57: "Cavalry Raider", 58: "Livestock", 59: "King"}


def leer_textos(*rutas: Path) -> dict[int, str]:
    """Lee archivos key-value del juego (id "texto"); los posteriores pisan a los anteriores."""
    textos: dict[int, str] = {}
    patron = re.compile(r'^(\d+)\s+"(.*)"\s*$')
    for ruta in rutas:
        if not ruta or not ruta.exists():
            continue
        for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
            m = patron.match(linea)
            if m:
                textos[int(m.group(1))] = m.group(2).replace("\\n", "\n").replace('\\"', '"')
    return textos


def _limpiar(texto: str) -> str:
    """Quita etiquetas, la línea 'Create/Research X (<cost>)' y la lista de mejoras/estadísticas."""
    t = (texto or "").replace("<cost>", "")
    t = re.split(r"<GREY>|<i>\s*Upgrades|\n<hp>", t)[0]
    t = re.sub(r"<[^>]*>", "", t)
    t = re.sub(r"^(Create|Research|Build) [^\n]*?\(\s*\)\s*", "", t.strip())
    return t.replace("\n", " ").strip()


def _stats(u) -> dict:
    t = u.type_50
    c = u.creatable
    costo = {RECURSOS[r.type]: r.amount for r in c.resource_costs if r.flag and r.type in RECURSOS and r.amount}
    tiempo = next((l.train_time for l in c.train_locations if l.unit_id >= 0), 0)
    bonos = [[CLASES.get(a.class_, f"class {a.class_}"), a.amount]
             for a in t.attacks if a.class_ not in (3, 4) and a.amount > 0]
    return {
        "hp": u.hit_points, "atk": t.displayed_attack, "ma": t.displayed_melee_armour,
        "pa": c.displayed_pierce_armour, "rng": round(t.displayed_range, 1), "spd": round(u.speed, 2),
        "los": round(u.line_of_sight, 1), "rel": round(t.displayed_reload_time, 2),
        "costo": costo, "tiempo": tiempo, "bonos": bonos,
        "tipo": CLASES_UNIDAD.get(u.class_, f"class {u.class_}"),
    }


def extraer(dat, civs_json: dict, textos: dict[int, str], originales: dict[int, str]) -> dict:
    """Arma el JSON del visor. `originales` = textos del juego sin el mod (para nombres de civs apagadas)."""
    def tx(i):
        return textos.get(i, "")

    civs, uu_ids, propio = [], {}, {}
    for ci, e in enumerate(civs_json["civilization_list"]):  # mismo orden que dat.civs
        if ci == 0 or ci >= len(dat.civs):  # 0 = Gaia
            continue
        civ = dat.civs[ci]
        nombre = tx(e["name_string_id"])
        apagada = nombre.startswith("·")
        original = originales.get(e["name_string_id"], nombre)
        uu = []
        for uid in (e.get("unique_unit_id"), e.get("elite_unique_unit_id")):
            if isinstance(uid, int) and 0 <= uid < len(civ.units) and civ.units[uid]:
                u = civ.units[uid]
                uu.append({"id": uid, "nombre": tx(u.language_dll_name) or u.name,
                           "ayuda": _limpiar(tx(u.language_dll_help)), **_stats(u)})
        for x in uu:
            propio.setdefault(x["id"], ci)
        if uu:
            uu_ids.setdefault(uu[0]["id"], []).append(original if apagada or nombre == original else f"{nombre} ({original})")
        ut = []
        for clave, edad in (("unique_tech_id_2", "Castle"), ("unique_tech_id_1", "Imperial")):
            tid = e.get(clave)
            if isinstance(tid, int) and 0 <= tid < len(dat.techs):
                t = dat.techs[tid]
                ayuda = _limpiar(tx(t.language_dll_help))
                costo = {RECURSOS[r.type]: r.amount for r in t.resource_costs if r.flag and r.type in RECURSOS and r.amount}
                ut.append({"id": tid, "edad": edad, "nombre": tx(t.language_dll_name) or t.name,
                           "ayuda": ayuda, "costo": costo})
        desc = tx(e.get("tech_tree_description_string_id", -1))
        civs.append({
            "indice": ci, "interno": civ.name, "arbol": e.get("tech_tree_name", ""),
            "nombre": original if apagada else nombre, "original": original, "apagada": apagada,
            "campana": (not apagada) and nombre != original,
            "descripcion": re.sub(r"<b>(.*?)<b>", r"\1", desc),
            "uu": uu, "ut": ut,
        })

    # Catálogo: todas las unidades militares entrenables de cualquier civ (la primera civ que la tenga)
    unidades, vistas = [], set()
    for ci, civ in enumerate(dat.civs):
        if ci == 0:
            continue
        for uid, u in enumerate(civ.units):
            if uid in propio:  # la UU se lee de la civ dueña (con su nombre y cambios de campaña)
                u = dat.civs[propio[uid]].units[uid]
            if uid in vistas or u is None or u.type != 70 or not u.creatable or u.hit_points <= 0:
                continue
            if not any(l.unit_id >= 0 for l in u.creatable.train_locations) and uid not in uu_ids:
                continue
            nombre = tx(u.language_dll_name)
            if not nombre or u.class_ in (4, 58, 2, 21):  # aldeanos, ganado, comercio, barcos pesqueros
                continue
            vistas.add(uid)
            donde = sorted({l.unit_id for l in u.creatable.train_locations if l.unit_id >= 0})
            unidades.append({"id": uid, "nombre": nombre, "interno": u.name,
                             "uu_de": uu_ids.get(uid, []), "castillo": 82 in donde,
                             "edificios": donde, **_stats(u)})
    # pareja normal -> élite (para el snippet usar: [a, b])
    elites = {}
    for e in civs_json["civilization_list"]:
        if isinstance(e.get("unique_unit_id"), int) and isinstance(e.get("elite_unique_unit_id"), int):
            elites[e["unique_unit_id"]] = e["elite_unique_unit_id"]
    for t in dat.techs:
        if 0 <= t.effect_id < len(dat.effects):
            for c in dat.effects[t.effect_id].effect_commands:
                if c.type == 3 and c.a in vistas and c.b in vistas:
                    elites.setdefault(c.a, c.b)
    for u in unidades:
        u["elite"] = elites.get(u["id"])
    unidades.sort(key=lambda u: (not u["uu_de"], u["nombre"]))
    return {"civs": civs, "unidades": unidades}


def generar_html(datos: dict, titulo: str, subtitulo: str, completo: bool = True) -> str:
    plantilla = (Path(__file__).resolve().parent / "visor_plantilla.html").read_text(encoding="utf-8")
    js = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    cuerpo = (plantilla.replace("__TITULO__", titulo).replace("__SUBTITULO__", subtitulo)
              .replace("__DATOS__", js))
    if not completo:
        return cuerpo
    return ('<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            '<style>body{margin:0}[hidden]{display:none!important}</style>\n'
            f"{cuerpo}\n</html>\n")
