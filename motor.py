"""
motor.py — aplica una receta (YAML) a un DatFile de AoE2 DE.

Una receta convierte la civ de un "espacio" (una civ original, p. ej. Byzantine) en una civ ficticia:
  - limpia los bonos originales (techs C-Bonus, bonos del árbol, bono de equipo)
  - crea los bonos nuevos como techs automáticas por edad
  - reescribe las 2 techs únicas (Castillos e Imperial)
  - cambia o ajusta la unidad única
  - ajusta el árbol (sin / con)

Todo se hace sobre la copia del .dat del mod; nunca sobre el del juego.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from genieutils.effect import Effect, EffectCommand

# ------------------------------------------------------------------ tablas de nombres
EDAD = {"oscura": None, "feudal": 101, "castillos": 102, "imperial": 103}

ATRIBUTO = {
    "vida": 0, "vision": 1, "guarnicion": 2, "velocidad": 5, "armadura": 8, "ataque": 9,
    "recarga": 10, "alcance": 12, "ritmo_trabajo": 13, "capacidad_carga": 14,
    "radio_area": 22, "radio_busqueda": 23, "costo": 100, "tiempo_creacion": 101,
    "costo_oro": 103, "costo_comida": 104, "costo_madera": 105, "costo_piedra": 106,
}
TIPO_DANO = {"cuerpo": 4, "perforante": 3, "edificios": 21, "infanteria": 1, "caballeria": 8}
RECURSO_COSTO = {"comida": 0, "madera": 1, "piedra": 2, "oro": 3}

# Grupos con nombre: lista de ("clase", id) o ("unidad", id)
GRUPOS = {
    "edificios": [("clase", c) for c in (3, 27, 52, 49, 39)],
    "murallas_y_torres": [("clase", c) for c in (27, 52, 39)],
    "caballeria": [("clase", c) for c in (12, 23, 47, 36)],
    "unidades_de_establo": [("clase", c) for c in (12, 23, 47)],
    "infanteria": [("clase", 6)],
    "arqueros": [("clase", 0), ("clase", 36)],
    "monjes": [("clase", 18), ("clase", 43)],
    "asedio": [("clase", c) for c in (13, 51, 54, 55)],
    "camellos": [("unidad", u) for u in (282, 556, 1755, 329, 330, 207, 1007, 1009, 1263, 1923)],
    "lenadores": [("unidad", u) for u in (123, 218)],
    "granjas": [("unidad", u) for u in (50, 1187)],
    "piqueros": [("unidad", u) for u in (93, 358, 359)],
    "escaramuzadores": [("unidad", u) for u in (7, 6, 1155)],
    "lanceros_y_escaramuzadores_y_camellos": [("unidad", u) for u in (93, 358, 359, 7, 6, 1155, 329, 330, 207, 1755)],
    "castillo": [("unidad", 82)],
    "muelles": [("unidad", u) for u in (45, 47, 51, 133)],
    "monasterios": [("unidad", u) for u in (104, 30, 31)],
    "taller_de_asedio": [("unidad", u) for u in (49, 150)],
    "cuarteles": [("unidad", u) for u in (12, 20, 132, 498)],
    "establos": [("unidad", u) for u in (101, 86, 153)],
    "galerias_de_tiro": [("unidad", u) for u in (87, 10, 14)],
}
GRUPOS["edificios_militares"] = GRUPOS["cuarteles"] + GRUPOS["establos"] + GRUPOS["galerias_de_tiro"]


@dataclass
class Registro:
    lineas: list[str] = field(default_factory=list)

    def __call__(self, texto: str):
        self.lineas.append(texto)


class ErrorReceta(Exception):
    pass


# ------------------------------------------------------------------ utilidades
def buscar_civ(dat, ref) -> int:
    if isinstance(ref, int):
        return ref
    for i, c in enumerate(dat.civs):
        if c.name.lower() == str(ref).lower():
            return i
    raise ErrorReceta(f"No existe la civ '{ref}' en el .dat (usa el nombre interno de 'info').")


def buscar_tech(dat, ref) -> int:
    if isinstance(ref, int):
        return ref
    exactos = [i for i, t in enumerate(dat.techs) if t.name.lower() == str(ref).lower() and t.civ in (-1, 0)]
    if len(exactos) >= 1:
        return exactos[0]
    raise ErrorReceta(f"No encontré la tech '{ref}'. Usa su número (python campana.py info muestra los IDs).")


def objetivos(op: dict) -> list[tuple[str, int]]:
    """Devuelve [("clase"|"unidad", id), ...] a partir de grupo/clase/unidad(es)."""
    res = []
    if "grupo" in op:
        if op["grupo"] not in GRUPOS:
            raise ErrorReceta(f"Grupo desconocido '{op['grupo']}'. Válidos: {', '.join(sorted(GRUPOS))}")
        res += GRUPOS[op["grupo"]]
    for c in _lista(op.get("clase")):
        res.append(("clase", int(c)))
    for u in _lista(op.get("unidad")) + _lista(op.get("unidades")):
        res.append(("unidad", int(u)))
    if not res:
        raise ErrorReceta(f"La operación {op} no dice a qué aplica (grupo, clase o unidad).")
    return res


def _lista(x):
    if x is None:
        return []
    return list(x) if isinstance(x, (list, tuple)) else [x]


def comando(tipo, a=-1, b=-1, c=-1, d=0.0) -> EffectCommand:
    return EffectCommand(type=tipo, a=a, b=b, c=c, d=float(d))


def a_comandos(dat, op: dict) -> list[EffectCommand]:
    """Traduce una operación de receta a comandos de efecto del motor del juego."""
    tipo = op.get("op")
    if tipo in ("sumar", "multiplicar", "fijar"):
        attr_nombre = op["atributo"]
        if attr_nombre not in ATRIBUTO:
            raise ErrorReceta(f"Atributo desconocido '{attr_nombre}'. Válidos: {', '.join(ATRIBUTO)}")
        attr = ATRIBUTO[attr_nombre]
        codigo = {"fijar": 0, "sumar": 4, "multiplicar": 5}[tipo]
        valor = float(op["valor"])
        if attr in (8, 9):  # ataque/armadura: d = clase_de_dano*256 + cantidad
            dano = TIPO_DANO[op.get("tipo", "cuerpo")]
            valor = dano * 256 + int(op["valor"])
        cmds = []
        for kind, ident in objetivos(op):
            if kind == "clase":
                cmds.append(comando(codigo, -1, ident, attr, valor))
            else:
                cmds.append(comando(codigo, ident, -1, attr, valor))
            if attr == 1:  # la visión también amplía el radio de búsqueda
                cmds.append(comando(codigo, cmds[-1].a, cmds[-1].b, 23, valor))
        return cmds
    if tipo == "recurso":
        modo = op.get("modo", "sumar")
        if modo == "multiplicar":
            return [comando(6, int(op["id"]), -1, -1, op["valor"])]
        return [comando(1, int(op["id"]), 1 if modo == "sumar" else 0, -1, op["valor"])]
    if tipo == "costo_tech":
        tech = buscar_tech(dat, op["tech"])
        recursos = _lista(op.get("recursos")) or list(RECURSO_COSTO)
        return [comando(101, tech, RECURSO_COSTO[r], 2, op["multiplicar"]) for r in recursos]
    if tipo == "tiempo_tech":
        return [comando(103, buscar_tech(dat, op["tech"]), -1, 2, op["multiplicar"])]
    if tipo == "habilitar":
        return [comando(2, int(op["unidad"]), 1, -1, 0)]
    raise ErrorReceta(f"Operación desconocida: {op}")


def nuevo_efecto(dat, nombre: str, cmds: list[EffectCommand]) -> int:
    dat.effects.append(Effect(name=nombre[:31], effect_commands=cmds))
    return len(dat.effects) - 1


def ubicaciones(t):
    return [r for r in t.research_locations if r.location_id > 0]


# ------------------------------------------------------------------ pasos
def techs_de_civ(dat, ci):
    return [(tid, t) for tid, t in enumerate(dat.techs) if t.civ == ci]


def limpiar_bonos(dat, ci, log):
    plantilla = None
    for tid, t in techs_de_civ(dat, ci):
        if ubicaciones(t) or "(make avail)" in t.name:
            continue
        if t.effect_id < 0 and not t.name.startswith("C-Bonus"):
            continue  # la tech "nombre de la civ" y similares se quedan
        plantilla = plantilla or tid
        t.effect_id = -1
        t.civ = 0  # deja de investigarse sola para esta civ
        log(f"  bono original quitado: {t.name} (tech {tid})")
    civ = dat.civs[ci]
    arbol = dat.effects[civ.tech_tree_id]
    antes = len(arbol.effect_commands)
    arbol.effect_commands = [c for c in arbol.effect_commands if c.type in (102, 8) or (c.type == 2 and c.b == 0)]
    if len(arbol.effect_commands) != antes:
        log(f"  bonos del árbol quitados: {antes - len(arbol.effect_commands)} comandos")
    return plantilla


def plantilla_bono(dat):
    """Una tech automática cualquiera (sin ubicación de investigación) para copiar su forma."""
    for t in dat.techs:
        if t.name.startswith("C-Bonus") and not ubicaciones(t) and t.required_tech_count == 1:
            return t
    raise ErrorReceta("No encontré una tech de bono para usar como plantilla.")


def crear_bono(dat, ci, bono: dict, log):
    cmds = []
    for op in bono["efectos"]:
        cmds += a_comandos(dat, op)
    eid = nuevo_efecto(dat, f"HT {bono['nombre']}", cmds)
    t = copy.deepcopy(plantilla_bono(dat))
    t.name = f"HT {bono['nombre']}"[:60]
    t.civ = ci
    t.effect_id = eid
    edad = EDAD[bono.get("edad", "oscura")]
    t.required_techs = (edad if edad else -1, -1, -1, -1, -1, -1)
    t.required_tech_count = 1 if edad else 0
    dat.techs.append(t)
    log(f"  bono nuevo: {bono['nombre']} (tech {len(dat.techs) - 1}, {len(cmds)} comandos)")


def techs_castillo(dat, ci):
    castillo, imperial, otras = None, None, []
    candidatos = [(tid, t) for tid, t in techs_de_civ(dat, ci) if any(r.location_id == 82 for r in ubicaciones(t))]
    def boton(t):
        return next(r.button_id for r in ubicaciones(t) if r.location_id == 82)
    b7 = [x for x in candidatos if boton(x[1]) == 7]
    b8 = [x for x in candidatos if boton(x[1]) == 8]
    castillo = next((x for x in b7 if 102 in x[1].required_techs), b7[0] if b7 else None)
    imperial = next((x for x in b8 if 103 in x[1].required_techs), b8[0] if b8 else None)
    usados = {x[0] for x in (castillo, imperial) if x}
    otras = [tid for tid, t in candidatos if tid not in usados and boton(t) in (7, 8)]
    return castillo, imperial, otras


def reescribir_ut(dat, tid, ut: dict, log, etiqueta):
    cmds = []
    for op in ut["efectos"]:
        cmds += a_comandos(dat, op)
    t = dat.techs[tid]
    viejo = t.name
    t.effect_id = nuevo_efecto(dat, f"HT {ut['nombre']}", cmds)
    t.name = ut["nombre"][:60]
    log(f"  UT {etiqueta}: {viejo} → {ut['nombre']} (tech {tid})")


def unidad_unica(dat, ci, uu: dict, log):
    civ = dat.civs[ci]
    activar = next(((tid, t) for tid, t in techs_de_civ(dat, ci) if "(make avail)" in t.name), None)
    elite = next(((tid, t) for tid, t in techs_de_civ(dat, ci)
                  if any(r.location_id == 82 and r.button_id == 6 for r in ubicaciones(t))), None)
    if not activar or not elite:
        raise ErrorReceta("No encontré las techs de la unidad única de esta civ.")
    normal_id = dat.effects[activar[1].effect_id].effect_commands[0].a
    elite_id = dat.effects[elite[1].effect_id].effect_commands[0].b
    if "usar" in uu:
        normal_id, elite_id = (int(x) for x in uu["usar"])
        activar[1].effect_id = nuevo_efecto(dat, "HT UU make avail", [comando(2, normal_id, 1, -1, 0)])
        elite[1].effect_id = nuevo_efecto(dat, "HT UU elite", [comando(3, normal_id, elite_id, -1, 0)])
        for uid in (normal_id, elite_id):
            for loc in civ.units[uid].creatable.train_locations:
                if loc.unit_id < 0:
                    loc.unit_id = 82  # que se entrene en el castillo
                    loc.button_id = 1
        log(f"  UU cambiada a {civ.units[normal_id].name} / {civ.units[elite_id].name}")
    for uid in (normal_id, elite_id):
        u = civ.units[uid]
        for clave, valor in (uu.get("cambios") or {}).items():
            aplicar_cambio_unidad(u, clave, valor)
    if uu.get("cambios"):
        log(f"  UU ajustada: {uu['cambios']}")
    return normal_id, elite_id


def _ajustar(actual, valor):
    if isinstance(valor, str) and valor[:1] in "+-":
        return actual + float(valor)
    if isinstance(valor, str) and valor.startswith("x"):
        return actual * float(valor[1:])
    return float(valor)


def aplicar_cambio_unidad(u, clave, valor):
    t = u.type_50
    if clave == "vida":
        u.hit_points = int(round(_ajustar(u.hit_points, valor)))
    elif clave == "velocidad":
        u.speed = _ajustar(u.speed, valor)
    elif clave in ("ataque_cuerpo", "ataque_perforante"):
        clase = 4 if clave.endswith("cuerpo") else 3
        for a in t.attacks:
            if a.class_ == clase:
                a.amount = int(round(_ajustar(a.amount, valor)))
        t.displayed_attack = max(a.amount for a in t.attacks if a.class_ in (3, 4))
    elif clave in ("armadura_cuerpo", "armadura_perforante"):
        clase = 4 if clave.endswith("cuerpo") else 3
        for a in t.armours:
            if a.class_ == clase:
                a.amount = int(round(_ajustar(a.amount, valor)))
                if clase == 4:
                    t.displayed_melee_armour = a.amount
        if clase == 3 and u.creatable:
            u.creatable.displayed_pierce_armour = next(a.amount for a in t.armours if a.class_ == 3)
    elif clave == "pisoteo":
        t.blast_width = float(valor)
        t.blast_attack_level = 2
    elif clave.startswith("bonus_vs_"):
        clase = {"caballeria": 8, "camellos": 30, "elefantes": 5, "infanteria": 1,
                 "edificios": 21, "arqueros": 15}[clave[len("bonus_vs_"):]]
        for a in t.attacks:
            if a.class_ == clase:
                a.amount = int(round(_ajustar(a.amount, valor)))
    elif clave == "costo":       # {comida: 60, oro: 30}
        _poner_costo(u.creatable, valor)
    elif clave == "tiempo":      # segundos de entrenamiento
        for loc in u.creatable.train_locations:
            if loc.unit_id >= 0:
                loc.train_time = int(_ajustar(loc.train_time, valor))
    else:
        raise ErrorReceta(f"Cambio de unidad desconocido '{clave}'.")


def editar_unidades(dat, ci, ediciones: list, log):
    civ = dat.civs[ci]
    for ed in ediciones or []:
        ids = [i for k, i in objetivos(ed) if k == "unidad"]
        for uid in ids:
            u = civ.units[uid]
            if "poblacion" in ed:
                for r in u.resource_storages:
                    if r.type == 4:
                        r.amount = float(ed["poblacion"])
            if "costo" in ed:
                slots = list(u.creatable.resource_costs)
                for i, (rec, cant) in enumerate(ed["costo"].items()):
                    slots[i].type = RECURSO_COSTO[rec]
                    slots[i].amount = int(cant)
                    slots[i].flag = 1
                for j in range(len(ed["costo"]), len(slots)):
                    slots[j].type, slots[j].amount, slots[j].flag = -1, 0, 0
            for clave, valor in (ed.get("cambios") or {}).items():
                aplicar_cambio_unidad(u, clave, valor)
        log(f"  unidades editadas {ids}: { {k: v for k, v in ed.items() if k not in ('grupo', 'unidad', 'unidades')} }")


def _poner_costo(t, costo: dict):
    slots = list(t.resource_costs)
    for i, (rec, cant) in enumerate(costo.items()):
        slots[i].type, slots[i].amount, slots[i].flag = RECURSO_COSTO[rec], int(cant), 1
    for j in range(len(costo), len(slots)):
        slots[j].type, slots[j].amount, slots[j].flag = -1, 0, 0


def techs_propias(dat, ci, lista: list, log) -> list[int]:
    """Copia una tech (genérica o de otra civ) solo para esta civ, con nombre y costo propios.
    Las techs que 'reemplaza' se quitan del árbol de esta civ. Devuelve los IDs a deshabilitar."""
    quitar = []
    for tp in lista or []:
        base_id = buscar_tech(dat, tp["basada_en"]) if not isinstance(tp["basada_en"], int) else tp["basada_en"]
        t = copy.deepcopy(dat.techs[base_id])
        t.civ = ci
        t.name = f"HT {tp['nombre']}"[:60]
        if "costo" in tp:
            _poner_costo(t, tp["costo"])
        if "tiempo" in tp:
            for r in ubicaciones(t):
                r.research_time = int(tp["tiempo"])
        if "requiere" in tp:
            reqs = [buscar_tech(dat, x) for x in tp["requiere"]]
            t.required_techs = tuple(reqs + [-1] * (6 - len(reqs)))
            t.required_tech_count = len(reqs)
        dat.techs.append(t)
        tp["_id"] = len(dat.techs) - 1
        reemplaza = [buscar_tech(dat, x) for x in _lista(tp.get("reemplaza"))]
        quitar += reemplaza
        log(f"  tech propia: {tp['nombre']} (tech {tp['_id']}, copia de {dat.techs[base_id].name})"
            + (f", reemplaza a {', '.join(dat.techs[r].name for r in reemplaza)}" if reemplaza else ""))
    return quitar


def editar_techs_civ(dat, ci, lista: list, log):
    """Cambia costo/tiempo de techs que ya son de esta civ (p. ej. la mejora élite de la UU)."""
    for et in lista or []:
        if et["tech"] == "elite_unidad_unica":
            tid = next(tid for tid, t in techs_de_civ(dat, ci)
                       if any(r.location_id == 82 and r.button_id == 6 for r in ubicaciones(t)))
        else:
            tid = buscar_tech(dat, et["tech"])
            if dat.techs[tid].civ != ci:
                raise ErrorReceta(f"'{et['tech']}' es una tech compartida; usa techs_propias para cambiarla solo en esta civ.")
        t = dat.techs[tid]
        if "costo_x" in et:
            for c in t.resource_costs:
                if c.type >= 0:
                    c.amount = int(round(c.amount * float(et["costo_x"])))
        if "costo" in et:
            _poner_costo(t, et["costo"])
        log(f"  tech de la civ ajustada: {t.name} → {[(c.type, c.amount) for c in t.resource_costs if c.type >= 0]}")


def ajustar_arbol(dat, ci, arbol: dict, extra_sin: list[int], log):
    efecto = dat.effects[dat.civs[ci].tech_tree_id]
    actuales = {int(c.d) for c in efecto.effect_commands if c.type == 102}
    sin = {buscar_tech(dat, x) for x in _lista(arbol.get("sin"))} | set(extra_sin)
    con = {buscar_tech(dat, x) for x in _lista(arbol.get("con"))}
    efecto.effect_commands = [c for c in efecto.effect_commands if not (c.type == 102 and int(c.d) in con)]
    for tid in sorted(sin - actuales):
        efecto.effect_commands.append(comando(102, -1, -1, -1, tid))
    if sin - actuales:
        log(f"  árbol: quitadas {', '.join(dat.techs[t].name for t in sorted(sin - actuales))}")
    if con & actuales:
        log(f"  árbol: devueltas {', '.join(dat.techs[t].name for t in sorted(con & actuales))}")


# ------------------------------------------------------------------ textos y árbol visible
DESFASE_AYUDA = 79000  # CivTechTrees: "Help String ID" = language_dll_help + 79000 (el juego lo resta)
BASE_TEXTOS = 900000  # IDs propios de la campaña: 900000 + civ*100 + n


def ids_unidad_unica(dat, ci):
    activar = next(t for _, t in techs_de_civ(dat, ci) if "(make avail)" in t.name)
    elite = next(t for _, t in techs_de_civ(dat, ci)
                 if any(r.location_id == 82 and r.button_id == 6 for r in ubicaciones(t)))
    return (dat.effects[activar.effect_id].effect_commands[0].a,
            dat.effects[elite.effect_id].effect_commands[0].b)


def aplicar_textos(dat, receta: dict) -> dict[int, str]:
    """Asigna IDs de texto propios a la UU y las UT de la civ y devuelve {id: texto}."""
    ci = buscar_civ(dat, receta["espacio"])
    base = BASE_TEXTOS + ci * 100
    tx = receta.get("textos", {})
    cadenas: dict[int, str] = {}
    civ = dat.civs[ci]
    uu_nombre = tx.get("unidad_unica")
    if uu_nombre:
        normal, elite = ids_unidad_unica(dat, ci)
        for k, (uid, nombre) in enumerate(((normal, uu_nombre), (elite, f"Elite {uu_nombre}"))):
            u = civ.units[uid]
            u.language_dll_name = base + 1 + k
            cadenas[base + 1 + k] = nombre
            u.language_dll_creation = base + 3 + k
            cadenas[base + 3 + k] = f"Create <b>{nombre}<b> (<cost>)"
            if tx.get("unidad_unica_ayuda"):
                u.language_dll_help = base + 5 + k
                cadenas[base + 5 + k] = f"Create <b>{nombre}<b> (<cost>)\n{receta['nombre']} unique unit. {tx['unidad_unica_ayuda']}"
        # mejora élite en el castillo (si no, conserva el nombre original, p. ej. "Elite Woad Raider")
        te = next(t for _, t in techs_de_civ(dat, ci)
                  if any(r.location_id == 82 and r.button_id == 6 for r in ubicaciones(t)))
        te.language_dll_name, te.language_dll_description, te.language_dll_help = base + 7, base + 8, base + 9
        cadenas[base + 7] = f"Elite {uu_nombre}"
        cadenas[base + 8] = f"Research <b>Elite {uu_nombre}<b> (<cost>)"
        cadenas[base + 9] = f"Research <b>Elite {uu_nombre}<b> (<cost>)\nUpgrades your {uu_nombre}s to Elite {uu_nombre}s."
    # unidades renombradas (p. ej. Halberdier → Heavy Pikeman)
    n = 40
    for ed in receta.get("editar_unidades") or []:
        if "nombre" not in ed:
            continue
        nombres = _lista(ed["nombre"])
        ids = [i for k, i in objetivos(ed) if k == "unidad"]
        for uid, nombre in zip(ids, nombres + [nombres[-1]] * len(ids)):
            u = civ.units[uid]
            u.language_dll_name, u.language_dll_creation = base + n, base + n + 1
            cadenas[base + n], cadenas[base + n + 1] = nombre, f"Create <b>{nombre}<b> (<cost>)"
            if ed.get("ayuda"):
                u.language_dll_help = base + n + 2
                cadenas[base + n + 2] = f"Create <b>{nombre}<b> (<cost>)\n{ed['ayuda']}"
            n += 3
    # techs propias
    n = 70
    for tp in receta.get("techs_propias") or []:
        t = dat.techs[tp["_id"]]
        t.language_dll_name, t.language_dll_description, t.language_dll_help = base + n, base + n + 1, base + n + 2
        cadenas[base + n] = tp["nombre"]
        cadenas[base + n + 1] = f"Research <b>{tp['nombre']}<b> (<cost>)"
        cadenas[base + n + 2] = f"Research <b>{tp['nombre']}<b> (<cost>)\n{tp.get('ayuda', '')}".strip()
        n += 3
    castillo, imperial, _ = techs_castillo(dat, ci)
    for off, par, clave in ((10, castillo, "tech_castillos"), (20, imperial, "tech_imperial")):
        if not par or clave not in receta:
            continue
        t = dat.techs[par[0]]
        nombre = receta[clave]["nombre"]
        ayuda = receta[clave].get("ayuda", "")
        t.language_dll_name = base + off
        t.language_dll_description = base + off + 1
        t.language_dll_help = base + off + 2
        cadenas[base + off] = nombre
        cadenas[base + off + 1] = f"Research <b>{nombre}<b> (<cost>)"
        cadenas[base + off + 2] = f"Research <b>{nombre}<b> (<cost>)\n{ayuda}".strip()
    return cadenas


def receta_resumen(receta: dict) -> str:
    """Texto del árbol tecnológico: enfoque, bonos, UU, UT y bono de equipo."""
    tx = receta.get("textos", {})
    lineas = [f"{receta.get('descripcion', '')}", ""]
    # 'texto' (inglés, se ve en el juego); vacío = ya descrito en otro bono
    lineas += [f"• {b.get('texto', b['nombre'])}" for b in receta.get("bonos", []) if b.get("texto", b["nombre"])]
    lineas += [f"• {t}" for t in tx.get("bonos_extra", [])]
    if tx.get("unidad_unica"):
        lineas += ["", f"<b>Unique Unit:<b> {tx['unidad_unica']}"]
    for clave, edad in (("tech_castillos", "Castle"), ("tech_imperial", "Imperial")):
        if clave in receta:
            lineas.append(f"<b>{edad} Age Unique Tech:<b> {receta[clave]['nombre']}")
    if tx.get("bono_equipo"):
        lineas += ["", f"<b>Team Bonus:<b> {tx['bono_equipo']}"]
    return "\n".join(lineas)


def habilitadoras(dat):
    """unidad -> techs que la habilitan (efecto tipo 2 con b=1)."""
    mapa: dict[int, set[int]] = {}
    for tid, t in enumerate(dat.techs):
        if 0 <= t.effect_id < len(dat.effects):
            for c in dat.effects[t.effect_id].effect_commands:
                if c.type == 2 and c.b == 1:
                    mapa.setdefault(c.a, set()).add(tid)
    return mapa


def actualizar_arbol_json(dat, receta: dict, arbol: dict) -> list[str]:
    """Ajusta el JSON de CivTechTrees de la civ al .dat ya modificado."""
    ci = buscar_civ(dat, receta["espacio"])
    civ = dat.civs[ci]
    base = BASE_TEXTOS + ci * 100
    log = []
    sin = {int(c.d) for c in dat.effects[civ.tech_tree_id].effect_commands if c.type == 102}
    hab = habilitadoras(dat)
    tx = receta.get("textos", {})
    normal, elite = ids_unidad_unica(dat, ci)
    castillo, imperial, _ = techs_castillo(dat, ci)
    nodos = arbol["civ_techs_units"]

    # Techs propias que reemplazan una mejora: el nodo de la mejora vieja pasa a ser el de la nueva
    for tp in receta.get("techs_propias") or []:
        reemplaza = [buscar_tech(dat, x) for x in _lista(tp.get("reemplaza"))]
        nodo = next((n for n in nodos if reemplaza and n.get("Trigger Tech ID") == reemplaza[0]), None)
        if not nodo:
            continue
        efecto = dat.effects[dat.techs[tp["_id"]].effect_id].effect_commands
        resultado = next((c.b for c in efecto if c.type == 3), nodo["Node ID"])
        u = civ.units[resultado]
        viejo = nodo["Node ID"]
        nodo.update({"Name": tp["nombre"], "Trigger Tech ID": tp["_id"], "Node ID": resultado,
                     "Name String ID": u.language_dll_name, "Help String ID": u.language_dll_help + DESFASE_AYUDA,
                     "Picture Index": u.icon_id, "Node Status": "ResearchedCompleted"})
        for otro in nodos:  # lo que colgaba del nodo viejo ahora cuelga del nuevo
            if otro is not nodo and otro.get("Link ID") == viejo and otro.get("Building ID") == nodo.get("Building ID"):
                otro["Link ID"] = resultado
        log.append(f"  árbol visible: {tp['nombre']} reemplaza a {', '.join(dat.techs[r].name for r in reemplaza)}")

    # unidades con nombre propio de la campaña (p. ej. Palace Guard): el árbol muestra ese nombre
    for n in nodos:
        uid = n.get("Node ID")
        if n.get("Use Type") == "Unit" and n.get("Node Type") != "UniqueUnit" and isinstance(uid, int) \
                and 0 <= uid < len(civ.units) and civ.units[uid] and civ.units[uid].language_dll_name >= BASE_TEXTOS:
            n["Name String ID"] = civ.units[uid].language_dll_name
            n["Help String ID"] = civ.units[uid].language_dll_help + DESFASE_AYUDA

    for n in nodos:
        tipo, nid = n.get("Node Type"), n.get("Node ID")
        if tipo == "UniqueUnit":
            es_elite = "Trigger Tech ID" in n
            uid = elite if es_elite else normal
            u = civ.units[uid]
            n["Node ID"] = uid
            if es_elite:
                n["Link ID"] = normal
            n["Picture Index"] = u.icon_id
            n["Help String ID"] = u.language_dll_help + DESFASE_AYUDA
            if tx.get("unidad_unica"):
                n["Name"] = f"Elite {tx['unidad_unica']}" if es_elite else tx["unidad_unica"]
                n["Name String ID"] = base + (2 if es_elite else 1)
            continue
        if tipo == "UniqueTech":
            par, off, clave = ((castillo, 10, "tech_castillos") if n.get("Age ID") == 3
                               else (imperial, 20, "tech_imperial"))
            if par and clave in receta:
                n["Node ID"] = par[0]
                n["Name"] = receta[clave]["nombre"]
                n["Name String ID"] = base + off
                n["Help String ID"] = base + off + 2 + DESFASE_AYUDA
            continue
        if n.get("Use Type") == "Tech":
            disponible = nid not in sin
        elif "Trigger Tech ID" in n:
            disponible = n["Trigger Tech ID"] not in sin
        elif nid in hab and n.get("Node Type") == "Unit":
            disponible = any(t not in sin for t in hab[nid])
        else:
            continue
        if not disponible:
            nuevo = "NotAvailable"
        elif n["Node Status"] == "NotAvailable":
            nuevo = "ResearchedCompleted"
        else:
            nuevo = n["Node Status"]
        if nuevo != n["Node Status"]:
            log.append(f"  árbol visible: {n['Name']} → {nuevo}")
            n["Node Status"] = nuevo

    # En cascada: una mejora cuyo nodo previo no está disponible tampoco lo está
    por_id = {(n.get("Building ID"), n.get("Node ID")): n for n in nodos}
    cambio = True
    while cambio:
        cambio = False
        for n in nodos:
            previo = por_id.get((n.get("Building ID"), n.get("Link ID")))
            if (previo and n.get("Node Type") in ("UnitUpgrade", "Research", "UniqueUnit")
                    and previo["Node Status"] == "NotAvailable" and n["Node Status"] != "NotAvailable"
                    and n.get("Link Node Type") != "BuildingTech"):
                n["Node Status"] = "NotAvailable"
                log.append(f"  árbol visible: {n['Name']} → NotAvailable (depende de {previo['Name']})")
                cambio = True
    return log


def actualizar_civilizations(dat, receta: dict, civs_json: dict) -> dict[int, str]:
    """Ajusta la entrada de la civ en civilizations.json y devuelve los textos de nombre y descripción."""
    ci = buscar_civ(dat, receta["espacio"])
    civ = dat.civs[ci]
    entrada = next((e for e in civs_json["civilization_list"]
                    if e.get("tech_tree_name") == receta.get("archivo_arbol")), None)
    if not entrada:
        raise ErrorReceta(f"No encontré '{receta.get('archivo_arbol')}' en civilizations.json")
    normal, elite = ids_unidad_unica(dat, ci)
    castillo, imperial, _ = techs_castillo(dat, ci)
    entrada["unique_unit_id"] = normal
    entrada["elite_unique_unit_id"] = elite
    entrada["unique_unit_image_paths"] = [f"/resources/uniticons/{civ.units[normal].icon_id:03d}_50730.png"]
    entrada["unique_unit_string_ids"] = [{"name": civ.units[normal].language_dll_name,
                                          "description": civ.units[normal].language_dll_help}]
    if imperial:
        entrada["unique_tech_id_1"] = imperial[0]
    if castillo:
        entrada["unique_tech_id_2"] = castillo[0]
    tx = receta.get("textos", {})
    textos = {}
    if tx.get("civ"):
        textos[entrada["name_string_id"]] = tx["civ"]
    if "tech_tree_description_string_id" in entrada:
        textos[entrada["tech_tree_description_string_id"]] = receta_resumen(receta)
    return textos


def apagar_civs(civs_json: dict, usadas: set[str], formato: str) -> dict[int, str]:
    """Renombra las civs que la campaña no usa (p. ej. '· Britons ·')."""
    textos = {}
    for e in civs_json["civilization_list"]:
        if e.get("internal_name") == "Gaia" or e.get("tech_tree_name") in usadas:
            continue
        textos[e["name_string_id"]] = formato.format(nombre=e["internal_name"])
    return textos


# ------------------------------------------------------------------ entrada principal
def aplicar_receta(dat, receta: dict) -> list[str]:
    log = Registro()
    ci = buscar_civ(dat, receta["espacio"])
    log(f"== {receta['nombre']} (espacio: {dat.civs[ci].name}, civ #{ci})")

    if receta.get("limpiar_bonos", True):
        limpiar_bonos(dat, ci, log)
    for bono in receta.get("bonos", []):
        crear_bono(dat, ci, bono, log)

    civ = dat.civs[ci]
    if "bono_equipo" in receta:
        cmds = []
        for op in receta["bono_equipo"]:
            cmds += a_comandos(dat, op)
        dat.effects[civ.team_bonus_id].effect_commands = cmds
        log(f"  bono de equipo reemplazado ({len(cmds)} comandos)")

    castillo, imperial, otras = techs_castillo(dat, ci)
    if "tech_castillos" in receta:
        reescribir_ut(dat, castillo[0], receta["tech_castillos"], log, "Castillos")
    if "tech_imperial" in receta:
        reescribir_ut(dat, imperial[0], receta["tech_imperial"], log, "Imperial")

    if "unidad_unica" in receta:
        unidad_unica(dat, ci, receta["unidad_unica"], log)
    editar_unidades(dat, ci, receta.get("editar_unidades"), log)
    quitar = techs_propias(dat, ci, receta.get("techs_propias"), log)
    editar_techs_civ(dat, ci, receta.get("editar_techs"), log)
    ajustar_arbol(dat, ci, receta.get("arbol", {}), otras + quitar, log)
    # El nombre interno de la civ no se toca (el juego y la IA lo usan); el nombre visible va en 'textos'.
    return log.lineas
