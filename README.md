# tool-aoe2-campanas

Un banco de datos (`.dat`) propio por cada campaña de AoE2 DE, generado desde recetas.

## Instalación (una vez)
```
pip install -r requirements.txt
copy config.ejemplo.json config.json   (ajusta rutas si cambian)
```

## Uso
| Comando | Qué hace |
|---|---|
| `python campana.py verificar` | Comprueba que la librería lee/escribe el `.dat` del juego sin alterarlo. Córrelo después de cada parche. |
| `python campana.py base` | Congela una copia del `.dat` original en `base/<fecha>_<huella>/`. |
| `python campana.py nueva Muisca` | Crea `mods/local/CAMP-Muisca` con su propio `.dat`. |
| `python campana.py info` | Lista las civs con su índice. |
| `python campana.py info Aztecs` | Techs propias, bono de equipo y lo que le falta en el árbol. |
| `python campana.py info Aztecs --mod CAMP-Muisca` | Lo mismo, leyendo el `.dat` de esa campaña. |
| `python campana.py visor --mod CAMP-HollowThrone` | Genera `visor-CAMP-HollowThrone.html`: fichas de las civs y catálogo de unidades con el `usar: [id, id]` listo para copiar. Sin `--mod`, el juego original. |
| `python campana.py aplicar recetas/hollow-throne --mod CAMP-HollowThrone` | Parte del `.dat` original congelado y aplica todas las recetas de la carpeta: bonos, UU, UT, árbol (`.dat` + `CivTechTrees`) y textos. Se puede repetir cuantas veces quieras. |

## Reglas
- Nunca toca archivos del juego.
- En el juego, deja activo **un solo data mod** a la vez.
- `base/` no va a git (pesa ~12 MB por versión); las recetas y scripts sí.

## Recetas
Cada civ es un `.yaml` en `recetas/<campaña>/`. Ver `recetas/hollow-throne/` como ejemplo.

## Próximo
`validar`.

## Campaña nueva
Ver [NUEVA_CAMPANA.md](NUEVA_CAMPANA.md): qué datos darle a Claude y el proceso completo.

## Estado actual
Ver [ESTADO.md](ESTADO.md) para retomar el trabajo en otra conversación.
