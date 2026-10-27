# Cómo pedir una campaña nueva

Guía para arrancar otra campaña con esta herramienta cuando termines la actual.
Copia la plantilla de abajo, llénala (lo que no sepas, déjalo vacío) y pégasela a Claude.

## Qué pedir

> Quiero una campaña nueva de AoE2 con mi herramienta `tool-aoe2-campanas`. Aquí van los datos:

```
NOMBRE DE LA CAMPAÑA (en inglés):
NOMBRE DEL MOD: CAMP-<Nombre sin espacios>

IDEA GENERAL
- Tema / conflicto:
- Tono (oscuro, épico, político, fantasía, histórico…):
- Número de misiones:

PROTAGONISTAS
- Nombre — rol — en qué misiones se juega con él/ella:
- Antagonista(s):

RITMO
- Misiones introductorias:
- Misión con otro punto de vista / especial:
- Misiones temáticas (religiosa, comercio, naval, escolta…):
- Cierre y gran final:

CIVILIZACIONES
- Cuántas civs ficticias:
- Para cada una (si tengo preferencia): identidad, en qué civ original se basa, unidad única deseada
- (si lo dejo vacío, Claude elige y lo propone)

EXTRAS (opcional)
- Facciones, lugares o personajes que quiero sí o sí:
- Algo que NO quiero:
```

## Reglas fijas (Claude ya las conoce, pero van aquí por si acaso)

- Historia **lineal**, sin decisiones ni ramas.
- Nombres realistas; **nada de nombres griegos** (Nautikos, Alexandros…).
- Todo lo que se ve en el juego va en **inglés**: civs, unidades, techs, nombres de jugadores, intros, diálogos y finales. Las instrucciones para mí, en español.
- Civs **ficticias**, editadas a partir de las originales, no copias.
- Unidades únicas **parecidas a la original**: cambios pequeños y sutiles para no confundir (se pueden usar unidades del editor, con apariencia normal/élite coherente).
- Civs que no se usan aparecen **apagadas** (`· Britons ·`).
- Misiones **difíciles**, con varios enemigos (3 o más), recursos iniciales, objetivos secundarios con recompensa.
- **3 niveles de dificultad** (Normal = Standard/Moderate, Difícil = Hard, Pesadilla = Extreme): cambian recursos, tropas, oleadas y eventos, no solo la IA.
- **Eventos sencillos** (nivel "70 de 100"): solo triggers básicos — tiempo, unidad en área, objeto destruido; mensajes, diplomacia, cambio de dueño, mandar unidades ya colocadas. Sin cámaras ni cinemáticas.
- Cada misión trae su **tabla de triggers** lista para el editor.

## Qué entrega Claude

1. **Documento de campaña** (un solo doc): resumen, mundo, personajes, facciones, lugares, civilizaciones, misiones (intro, jugadores, mapa, inicio, tabla de dificultad, objetivos, secundarios, eventos, triggers, diálogos y final) y anexo técnico.
2. **Recetas**: carpeta `recetas/<campaña>/` con un `.yaml` por civ y `_campana.yaml`.
3. Si hace falta, mejoras a `motor.py` / `campana.py`.

## Qué hago yo

```
python campana.py nueva <Nombre>                     # una sola vez: crea mods/local/CAMP-<Nombre>
python campana.py aplicar recetas/<campaña> --mod CAMP-<Nombre>   # cada vez que cambien las recetas
python campana.py visor --mod CAMP-<Nombre>          # opcional: visor-CAMP-<Nombre>.html con civs y unidades
```

Después, en el juego:

1. Cierra el juego antes de `aplicar`.
2. Mods → activa **solo** `CAMP-<Nombre>` (un data mod a la vez; las campañas anteriores siguen intactas en su propio mod).
3. Editor de escenarios → arma los mapas siguiendo el documento.
4. Editor de campañas → une las misiones en `<Nombre>.aoe2campaign`.

Tras un parche del juego: `python campana.py verificar`, luego `python campana.py base` y volver a `aplicar`.
