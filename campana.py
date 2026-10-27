#!/usr/bin/env python3
"""
tool-aoe2-campanas — banco de datos (.dat) por campaña para AoE2 DE.

Comandos:
  python campana.py verificar            Comprueba que la librería lee y reescribe el .dat del juego sin cambios.
  python campana.py base                 Congela una copia del .dat original del juego (snapshot por versión).
  python campana.py nueva <Nombre>       Crea el mod local CAMP-<Nombre> a partir del último snapshot base.
  python campana.py info                 Lista las civilizaciones del .dat (índice, nombre interno).
  python campana.py info <civ>           Detalla una civ: techs propias (únicas, bonos, UU) y su árbol (lo deshabilitado).
  python campana.py info <civ> --mod CAMP-<Nombre>   Igual, pero leyendo el .dat de esa campaña.
  python campana.py visor [--mod CAMP-<Nombre>]       Genera visor-*.html con civs y catálogo de unidades.

Nunca modifica archivos del juego: solo lee de la instalación y escribe en la carpeta de la herramienta
y en mods/local.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from genieutils.datfile import DatFile

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "config.json"
DAT_NOMBRE = "empires2_x2_p1.dat"
# Archivos del juego que forman el "banco de datos" de una campaña
ARCHIVOS_DATOS = [DAT_NOMBRE, "civilizations.json"]
CARPETAS_DATOS = ["CivTechTrees"]


# ----------------------------------------------------------------- configuración
def cargar_config() -> dict:
    if not CONFIG.exists():
        sys.exit(f"Falta {CONFIG.name}. Copia config.ejemplo.json a config.json y ajusta las rutas.")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    for clave in ("juego_dat", "mods_local"):
        if clave not in cfg:
            sys.exit(f"config.json: falta la clave '{clave}'.")
    return cfg


def dat_del_juego(cfg: dict) -> Path:
    return Path(cfg["juego_dat"])


def carpeta_snapshots() -> Path:
    return RAIZ / "base"


def ultimo_snapshot() -> Path:
    snaps = sorted(p for p in carpeta_snapshots().glob("*") if p.is_dir())
    if not snaps:
        sys.exit("No hay snapshot base. Corre primero: python campana.py base")
    return snaps[-1]


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ----------------------------------------------------------------- verificar
def cmd_verificar(args, cfg):
    origen = dat_del_juego(cfg) / DAT_NOMBRE
    print(f"Leyendo {origen} ...")
    dat = DatFile.parse(origen)
    print(f"  versión del formato: {dat.version}")
    print(f"  civs: {len(dat.civs)} · techs: {len(dat.techs)} · efectos: {len(dat.effects)} "
          f"· unidades por civ: {len(dat.civs[0].units)}")
    import zlib
    crudo = zlib.decompress(origen.read_bytes(), wbits=-15)
    original = dat.to_bytes()
    if original != crudo:
        sys.exit("ERROR: al reescribirlo, el .dat no coincide byte a byte con el del juego. "
                 "No es seguro editarlo con esta versión de la librería.")
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / DAT_NOMBRE
        dat.save(copia)
        recargado = DatFile.parse(copia).to_bytes()
    if original == recargado:
        print("OK: el .dat se lee, se guarda y se vuelve a leer idéntico. La librería es compatible con esta versión del juego.")
    else:
        sys.exit("ERROR: el .dat cambia al reescribirlo. No es seguro editarlo con esta versión de la librería.")


# ----------------------------------------------------------------- base
def cmd_base(args, cfg):
    origen = dat_del_juego(cfg)
    dat_path = origen / DAT_NOMBRE
    huella = sha256(dat_path)[:12]
    existentes = [p for p in carpeta_snapshots().glob(f"*_{huella}") if p.is_dir()]
    if existentes:
        print(f"Ya existe un snapshot de esta versión del juego: {existentes[0].name}")
        return
    destino = carpeta_snapshots() / f"{datetime.now():%Y-%m-%d}_{huella}"
    destino.mkdir(parents=True)
    for nombre in ARCHIVOS_DATOS:
        shutil.copy2(origen / nombre, destino / nombre)
    for nombre in CARPETAS_DATOS:
        shutil.copytree(origen / nombre, destino / nombre)
    dat = DatFile.parse(destino / DAT_NOMBRE)
    manifiesto = {
        "creado": datetime.now().isoformat(timespec="seconds"),
        "origen": str(origen),
        "sha256_dat": sha256(destino / DAT_NOMBRE),
        "version_formato": dat.version,
        "civs": len(dat.civs),
        "techs": len(dat.techs),
    }
    (destino / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Snapshot base creado: {destino.name} ({manifiesto['civs']} civs, {manifiesto['techs']} techs)")


# ----------------------------------------------------------------- nueva
def cmd_nueva(args, cfg):
    snap = ultimo_snapshot()
    nombre_mod = f"CAMP-{args.nombre}"
    mod = Path(cfg["mods_local"]) / nombre_mod
    if mod.exists():
        sys.exit(f"Ya existe {mod}. Elige otro nombre.")
    dat_dir = mod / "resources" / "_common" / "dat"
    dat_dir.mkdir(parents=True)
    for nombre in ARCHIVOS_DATOS:
        shutil.copy2(snap / nombre, dat_dir / nombre)
    for nombre in CARPETAS_DATOS:
        shutil.copytree(snap / nombre, dat_dir / nombre)
    (mod / "resources" / "_common" / "scenario").mkdir(parents=True)
    (mod / "resources" / "_common" / "campaign").mkdir(parents=True)
    info = {
        "Author": cfg.get("autor", "Profesor M"),
        "CacheStatus": 0,
        "Description": f"Campaña {args.nombre} — banco de datos propio (base {snap.name}).",
        "Title": nombre_mod,
    }
    (mod / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    # Registro local: de qué base partió esta campaña (para 'reconstruir' tras un parche)
    registro = {"base": snap.name, "creado": datetime.now().isoformat(timespec="seconds"), "recetas": []}
    (mod / "campana.json").write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Mod creado: {mod}")
    print("Actívalo en el juego (Mods > Mis mods) y deja activo solo este data mod al usar el editor.")


# ----------------------------------------------------------------- info
TIPOS_EFECTO = {
    0: "fijar atributo", 1: "recurso (+/fijar)", 2: "habilitar/deshabilitar unidad", 3: "mejorar unidad",
    4: "sumar atributo", 5: "multiplicar atributo", 6: "multiplicar recurso", 7: "crear unidad",
    101: "costo de tech", 102: "deshabilitar tech", 103: "tiempo de tech",
}
ATRIBUTOS = {
    0: "vida", 1: "línea de visión", 2: "guarnición", 5: "velocidad", 8: "armadura", 9: "ataque",
    10: "recarga", 12: "alcance", 13: "ritmo de trabajo", 14: "capacidad de carga", 100: "costo",
    101: "tiempo de creación", 103: "costo oro", 104: "costo comida", 105: "costo madera", 106: "costo piedra",
}
# Clases de unidad (campo 'class' de la unidad)
CLASES = {
    0: "arqueros", 3: "edificios", 4: "aldeanos", 6: "infantería", 12: "caballería", 13: "asedio",
    18: "monjes", 19: "carretas de comercio", 20: "barcos de transporte", 21: "pesqueros", 22: "barcos de guerra",
    23: "conquistadores", 24: "elefantes", 35: "petardos", 36: "arqueros a caballo", 43: "monjes con reliquia",
    44: "cañón de mano", 46: "piqueros", 47: "exploradores", 51: "asedio empacado", 52: "torres",
    54: "asedio desempacado", 55: "escorpiones",
}
# Clases de ataque/armadura (codificadas en d = clase*256 + cantidad)
CLASES_ARMADURA = {
    1: "infantería", 3: "perforante", 4: "cuerpo a cuerpo", 5: "elefantes", 8: "caballería", 11: "todos los edificios",
    15: "arqueros", 16: "barcos", 17: "arietes", 19: "unidades únicas", 20: "asedio", 21: "edificios",
    22: "murallas y puertas", 23: "pólvora", 25: "monjes", 26: "castillos", 27: "piqueros", 28: "arqueros a caballo",
    29: "guerreros águila", 30: "camellos",
}
RECURSOS = {0: "comida", 1: "madera", 2: "piedra", 3: "oro", 4: "población", 32: "bonificación de población"}


def abrir_dat(args, cfg) -> DatFile:
    if getattr(args, "mod", None):
        ruta = Path(cfg["mods_local"]) / args.mod / "resources" / "_common" / "dat" / DAT_NOMBRE
    else:
        ruta = ultimo_snapshot() / DAT_NOMBRE if carpeta_snapshots().exists() and any(carpeta_snapshots().iterdir()) \
            else dat_del_juego(cfg) / DAT_NOMBRE
    return DatFile.parse(ruta)


def nombre_unidad(dat: DatFile, uid: int) -> str:
    unidades = dat.civs[0].units
    if 0 <= uid < len(unidades) and unidades[uid] is not None:
        return unidades[uid].name
    return f"#{uid}"


def nombre_tech(dat: DatFile, tid: int) -> str:
    return dat.techs[tid].name if 0 <= tid < len(dat.techs) else f"#{tid}"


def describir_comando(dat: DatFile, c) -> str:
    t = c.type
    base = t - 10 if 10 <= t <= 16 else t  # 10–16 = variantes "para el equipo"
    equipo = " (equipo)" if base != t else ""
    if base == 2:
        accion = "habilita" if c.b == 1 else "deshabilita"
        return f"{accion} {nombre_unidad(dat, c.a)}{equipo}"
    if base == 3:
        return f"mejora {nombre_unidad(dat, c.a)} → {nombre_unidad(dat, c.b)}{equipo}"
    if base in (0, 4, 5):
        objetivo = nombre_unidad(dat, c.a) if c.a >= 0 else CLASES.get(c.b, f"clase {c.b}")
        attr = int(c.c)
        atributo = ATRIBUTOS.get(attr, f"atributo {attr}")
        if attr in (8, 9) and base in (0, 4):  # ataque/armadura: d = clase*256 + cantidad
            clase, cant = divmod(int(c.d), 256)
            atributo = f"{atributo} {CLASES_ARMADURA.get(clase, f'clase {clase}')}"
            valor = f"{cant:+d}" if base == 4 else f"= {cant}"
            return f"{atributo} {valor} a {objetivo}{equipo}"
        if base == 5:
            pct = (c.d - 1) * 100
            return f"{atributo} ×{c.d:.3g} ({pct:+.0f}%) a {objetivo}{equipo}"
        signo = "=" if base == 0 else "+"
        return f"{atributo} {signo} {c.d:g} a {objetivo}{equipo}"
    if base in (1, 6):
        recurso = RECURSOS.get(c.a, f"recurso #{c.a}")
        if base == 6:
            return f"{recurso} ×{c.d:g}{equipo}"
        return f"{recurso} {'+' if c.b == 1 else '='}{c.d:g}{equipo}"
    if base == 102:
        return f"deshabilita tech {nombre_tech(dat, int(c.d))}"
    if base in (101, 103):
        return f"{TIPOS_EFECTO[base]}: {nombre_tech(dat, c.a)} ({c.d:+g})"
    return f"{TIPOS_EFECTO.get(base, f'tipo {t}')} a={c.a} b={c.b} c={c.c} d={c.d:g}{equipo}"


def buscar_civ(dat: DatFile, texto: str) -> int:
    if texto.isdigit():
        return int(texto)
    for i, civ in enumerate(dat.civs):
        if civ.name.lower() == texto.lower():
            return i
    candidatos = [i for i, c in enumerate(dat.civs) if texto.lower() in c.name.lower()]
    if len(candidatos) == 1:
        return candidatos[0]
    sys.exit(f"No encontré una civ única para '{texto}'. Usa el índice (python campana.py info).")


def cmd_info(args, cfg):
    dat = abrir_dat(args, cfg)
    if not args.civ:
        print(f"{'#':>3}  {'civ':<20} árbol  bono-equipo")
        for i, civ in enumerate(dat.civs):
            print(f"{i:>3}  {civ.name:<20} {civ.tech_tree_id:>5}  {civ.team_bonus_id:>5}")
        return
    i = buscar_civ(dat, args.civ)
    civ = dat.civs[i]
    print(f"== {civ.name} (civ #{i})")
    propias = [(tid, t) for tid, t in enumerate(dat.techs) if t.civ == i]
    print(f"\n-- Techs propias de la civ ({len(propias)}): únicas, bonos y habilitación de UU")
    # Agrupa las techs que comparten nombre y efecto (p. ej. un bono que se dispara con varias techs)
    grupos: dict[tuple[str, int], list[int]] = {}
    for tid, t in propias:
        grupos.setdefault((t.name, t.effect_id), []).append(tid)
    for (nombre, efecto), tids in grupos.items():
        ids = ", ".join(map(str, tids))
        print(f"  tech {ids}  {nombre}" + (f"  (×{len(tids)})" if len(tids) > 1 else ""))
        disparadores = sorted({nombre_tech(dat, r) for tid in tids for r in dat.techs[tid].required_techs if r >= 0})
        if disparadores and len(tids) > 1:
            print(f"            se activa con: {', '.join(disparadores)}")
        if 0 <= efecto < len(dat.effects):
            for c in dat.effects[efecto].effect_commands:
                print(f"            · {describir_comando(dat, c)}")
        else:
            print("            · (sin efecto propio)")
    if 0 <= civ.team_bonus_id < len(dat.effects):
        print(f"\n-- Bono de equipo (efecto {civ.team_bonus_id})")
        for c in dat.effects[civ.team_bonus_id].effect_commands:
            print(f"  · {describir_comando(dat, c)}")
    if 0 <= civ.tech_tree_id < len(dat.effects):
        cmds = dat.effects[civ.tech_tree_id].effect_commands
        des_tech = [nombre_tech(dat, int(c.d)) for c in cmds if c.type == 102]
        des_uni = [nombre_unidad(dat, c.a) for c in cmds if c.type == 2 and c.b == 0]
        otros = [c for c in cmds if c.type not in (2, 102) or (c.type == 2 and c.b != 0)]
        print(f"\n-- Árbol (efecto {civ.tech_tree_id}): lo que NO tiene")
        print(f"  techs deshabilitadas ({len(des_tech)}): {', '.join(des_tech) or '—'}")
        if des_uni:
            print(f"  unidades deshabilitadas ({len(des_uni)}): {', '.join(des_uni)}")
        for c in otros:
            print(f"  · {describir_comando(dat, c)}")


# ----------------------------------------------------------------- aplicar
IDIOMAS_TEXTOS = ["en", "es", "mx"]


def cmd_aplicar(args, cfg):
    import yaml
    import motor

    carpeta = Path(args.recetas)
    recetas = sorted(p for p in carpeta.glob("*.yaml") if not p.name.startswith("_")) if carpeta.is_dir() else [carpeta]
    ajustes_path = (carpeta if carpeta.is_dir() else carpeta.parent) / "_campana.yaml"
    ajustes = yaml.safe_load(ajustes_path.read_text(encoding="utf-8")) if ajustes_path.exists() else {}
    if not recetas:
        sys.exit(f"No hay recetas .yaml en {carpeta}")
    mod = Path(cfg["mods_local"]) / args.mod
    registro_path = mod / "campana.json"
    if not registro_path.exists():
        sys.exit(f"{mod} no es un mod creado con 'nueva'.")
    registro = json.loads(registro_path.read_text(encoding="utf-8"))
    snap = carpeta_snapshots() / registro["base"]
    dat_dir = mod / "resources" / "_common" / "dat"

    # Siempre se parte del .dat original congelado: aplicar dos veces da el mismo resultado.
    print(f"Leyendo base {snap.name} ... (tarda ~1 min)")
    dat = DatFile.parse(snap / DAT_NOMBRE)
    civs_json = json.loads((snap / "civilizations.json").read_text(encoding="utf-8"))
    cadenas: dict[int, str] = {}
    usadas: set[str] = set()
    for ruta in recetas:
        receta = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        try:
            for linea in motor.aplicar_receta(dat, receta):
                print(linea)
            cadenas.update(motor.aplicar_textos(dat, receta))
            cadenas.update(motor.actualizar_civilizations(dat, receta, civs_json))
            usadas.add(receta.get("archivo_arbol"))
            if receta.get("archivo_arbol"):
                nombre = f"{receta['archivo_arbol']}.json"
                arbol = json.loads((snap / "CivTechTrees" / nombre).read_text(encoding="utf-8"))
                for linea in motor.actualizar_arbol_json(dat, receta, arbol):
                    print(linea)
                (dat_dir / "CivTechTrees" / nombre).write_text(json.dumps(arbol, indent=2), encoding="utf-8")
        except motor.ErrorReceta as e:
            sys.exit(f"ERROR en {ruta.name}: {e}")

    if ajustes.get("apagar_civs", True):
        formato = ajustes.get("formato_apagado", "· {nombre} ·")
        apagadas = motor.apagar_civs(civs_json, usadas, formato)
        cadenas.update(apagadas)
        print(f"Civs sin usar renombradas: {len(apagadas)} (formato '{formato}')")
    (dat_dir / "civilizations.json").write_text(json.dumps(civs_json, indent=2), encoding="utf-8")

    destino = dat_dir / DAT_NOMBRE
    dat.save(destino)
    print(f"\n.dat guardado en {destino}")

    lineas = [f'{k} "{v}"'.replace("\n", "\\n") for k, v in sorted(cadenas.items())]
    for lang in IDIOMAS_TEXTOS:
        ruta = mod / "resources" / lang / "strings" / "key-value" / "key-value-modded-strings-utf8.txt"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"Textos: {len(cadenas)} cadenas en {', '.join(IDIOMAS_TEXTOS)}")

    registro["recetas"] = [str(r) for r in recetas]
    registro["aplicado"] = datetime.now().isoformat(timespec="seconds")
    registro_path.write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Listo. Abre el juego, activa solo este mod y revisa las civs en el editor de escenarios.")


def cmd_visor(args, cfg):
    import visor

    strings = Path(cfg.get("juego_strings") or Path(cfg["juego_dat"]).parents[1] / "en" / "strings" / "key-value")
    originales = visor.leer_textos(strings / "key-value-strings-utf8.txt")
    if not originales:
        sys.exit(f"No encontré los textos del juego en {strings} (agrega 'juego_strings' en config.json).")
    if args.mod:
        mod = Path(cfg["mods_local"]) / args.mod
        dat_dir = mod / "resources" / "_common" / "dat"
        textos = visor.leer_textos(strings / "key-value-strings-utf8.txt",
                                   mod / "resources" / "en" / "strings" / "key-value" / "key-value-modded-strings-utf8.txt")
        titulo, sub = args.mod, f"Civilizaciones y unidades del mod {args.mod}"
    else:
        dat_dir = ultimo_snapshot() if carpeta_snapshots().exists() and any(carpeta_snapshots().iterdir()) else dat_del_juego(cfg)
        textos, titulo, sub = originales, "AoE2 DE", "Civilizaciones y unidades del juego original"
    print("Leyendo .dat ... (tarda ~1 min)")
    dat = DatFile.parse(dat_dir / DAT_NOMBRE)
    civs_json = json.loads((dat_dir / "civilizations.json").read_text(encoding="utf-8"))
    datos = visor.extraer(dat, civs_json, textos, originales)
    sub += f" · generado {datetime.now():%Y-%m-%d %H:%M}"
    destino = RAIZ / f"visor-{args.mod or 'original'}.html"
    destino.write_text(visor.generar_html(datos, titulo, sub), encoding="utf-8")
    print(f"Visor: {destino}  ({len(datos['civs'])} civs, {len(datos['unidades'])} unidades). Ábrelo con doble clic.")


# ----------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description="Banco de datos por campaña para AoE2 DE")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verificar")
    sub.add_parser("base")
    n = sub.add_parser("nueva"); n.add_argument("nombre")
    i = sub.add_parser("info"); i.add_argument("civ", nargs="?"); i.add_argument("--mod")
    a = sub.add_parser("aplicar"); a.add_argument("recetas"); a.add_argument("--mod", required=True)
    v = sub.add_parser("visor"); v.add_argument("--mod")
    args = p.parse_args()
    cfg = cargar_config()
    {"verificar": cmd_verificar, "base": cmd_base, "nueva": cmd_nueva, "info": cmd_info,
     "aplicar": cmd_aplicar, "visor": cmd_visor}[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
