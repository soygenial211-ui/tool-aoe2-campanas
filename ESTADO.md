# Estado del proyecto (para retomar en otra conversación)

Última actualización: 2026-10-27.

> **Para Claude:** lee este archivo completo antes de tocar nada. Aquí está dónde vive cada cosa, qué está hecho, qué falta y las trampas técnicas ya descubiertas.

## Dónde está todo

| Qué | Dónde |
| --- | --- |
| Repo | GitHub `soygenial211-ui/tool-aoe2-campanas` (rama `main`) |
| Carpeta local | `C:\Users\genia\Desktop\CODING-WORKSTATION\genial99\tool-aoe2-campanas` |
| Juego (solo lectura) | `D:\SteamLibrary\steamapps\common\AoE2DE\resources\_common\dat` |
| Textos del juego (inglés) | `D:\SteamLibrary\steamapps\common\AoE2DE\resources\en\strings\key-value\key-value-strings-utf8.txt` |
| Mod de la campaña | `C:\Users\genia\Games\Age of Empires 2 DE\76561198293149089\mods\local\CAMP-HollowThrone` |
| Documento de la campaña | Claude Doc «The Hollow Throne — Biblia de campaña»: https://claude.ai/artifact/B9WUe4ze8nmwu8kefbtPdt |
| Visor de civs y unidades | Artifact «Hollow Throne Armory»: https://claude.ai/artifact/BW1nTjmHEQ8AfYiyPpgoFj (o `python campana.py visor --mod CAMP-HollowThrone`) |
| Snapshot base del .dat | `base/2026-10-25_4aa2f0a719e8/` (no va en git) |

Martín corre los comandos en Windows (genieutils-py no se instala en la VM del puente). Claude puede leer y escribir su carpeta por el puente del escritorio cuando está conectado.

## Reglas de Martín (no negociables)

- Historia lineal, sin decisiones. Varios protagonistas. Nada de nombres griegos.
- Todo lo que se ve en el juego, en **inglés** (civs, unidades, techs, nombres de jugadores, intros, diálogos). Instrucciones para él, en **español**.
- Civs ficticias editadas de las originales; las que no se usan aparecen apagadas (`· Britons ·`).
- Unidades únicas **fieles a la original**, con cambios pequeños.
- Misiones **difíciles**, 3+ enemigos, recursos iniciales, secundarios con recompensa, **3 dificultades** (Normal = Standard/Moderate, Difícil = Hard, Pesadilla = Extreme) que cambian recursos, tropas, oleadas y eventos.
- Eventos sencillos (“un 70 de 100”): solo triggers básicos, sin cámaras ni cinemáticas. Cada misión trae su tabla de triggers.
- Nunca modificar archivos del juego. Un solo data mod activo a la vez.

## Las 5 civs de The Hollow Throne (`recetas/hollow-throne/`)

| Civ | Espacio | UU (base) | UT Castillos / Imperial |
| --- | --- | --- | --- |
| Varenese | Bizantinos | Iron Lancer (Catafracta, sin cambios) | Bastion Doctrine / Old Guard |
| Castelari | Francos | Outrider (Coustillier, sin cambios) | Scaffolding / Iron Stirrups |
| Durnovars | Teutones | Eisenbruder (Caballero Teutón, +1 armadura perforante) | Ordensregel / Eiserner Wille |
| Zahrani | Sarracenos | Qawwas (Arquero de ratán, sin cambios) | Caravanserai / Desert Mail |
| Harlands | Celtas | Hearthguard (Konnik desmontado 1252/1253, +10 vida, 60 comida + 30 oro, 12 s) | Heavy Chainmail / Vassalage |

Bonos, bono de equipo y árbol: en cada `.yaml` y en el documento (sección Civilizaciones).

## Documento de campaña: estado

7 misiones con intro, jugadores (nombres en inglés), mapa, inicio, tabla de dificultad, objetivos, secundarios, eventos, triggers, diálogos y final.

1. The Silent Frontier — Corvell — introductoria, reconquista (rehecha el 27-oct: retomar Greyholt, cortar los 3 apoyos de Weiss, asaltar Ostwald; Kessler quema la aldea del oeste si no la proteges).
2. The Price of Order — Corvell — introductoria, toma de ciudad.
3. The Queen of Castelar — Isabela — expansión sin conquista (regla de Isabela: no destruir lo que gobernará; Redmoor se rinde por hambre).
4. The Iron Order — Konrad — cruzada religiosa (templos herejes, 4 reliquias, purificación con monjes).
5. Gold and Salt — Harun — comercio con guerra naval (ruta de la sal, compra de Port Salen, desembarco en Brandholm).
6. Broken Oaths — Corvell — cierre, escolta y retirada.
7. Ashes of the Throne — Corvell — final épico, dificultad extrema.

## Trampas técnicas ya resueltas

- **Ayuda del árbol tecnológico:** en `CivTechTrees/*.json`, `Help String ID` = `language_dll_help + 79000` (el juego resta 79000). `civilizations.json` usa el ID directo. Ya lo hace `motor.py` (`DESFASE_AYUDA`).
- **Mejora élite de la UU** (tech del castillo, botón 6): hay que renombrarla o conserva el nombre original («Elite Woad Raider»). Ya lo hace `aplicar_textos`.
- **Unidades del editor** como UU (p. ej. Konnik desmontado) pueden no tener costo ni tiempo: usar `cambios: {costo: {...}, tiempo: N}`.
- **«Failed to load world asset»**: apareció al copiar techs nuevas (`techs_propias`: Heavy Pikeman, Legionario) y editar unidades regionales. Se revirtió y funcionó. Si se reintenta, mejor modificar la tech existente en vez de copiarla, y probar una por una.
- `civilizations.json` tiene el mismo orden que `dat.civs` (índice 0 = Gaia).
- Los textos propios van en `resources/{en,es,mx}/strings/key-value/key-value-modded-strings-utf8.txt` con IDs 900000 + civ·100 + n.
- `aplicar` siempre parte del snapshot base: es repetible.

## Pendientes

1. Martín: `git pull`, `python campana.py aplicar recetas/hollow-throne --mod CAMP-HollowThrone`, activar el mod y comprobar en el editor: Outrider, ayudas del árbol con texto, costo del Hearthguard, Eisenbruder con +1.
2. Construir el mapa de la Misión 1 en el editor siguiendo el documento; después ajustar balance de recursos y oleadas con lo que se sienta al jugar.
3. Seguir con los mapas 2 a 7.
4. Opcional: reintentar Heavy Pikeman (Varenese) y Legionario (Harlands) modificando techs existentes.
5. Herramienta: comando `validar` (referencias rotas antes de abrir el juego).
6. Campaña siguiente: ver `NUEVA_CAMPANA.md`.

## Cómo retomar

Pídele a Claude: «Retomemos la campaña de AoE2: lee `ESTADO.md` del repo `soygenial211-ui/tool-aoe2-campanas` y el documento de la campaña». Si la computadora de juego está conectada, Claude puede trabajar directo en la carpeta local.
