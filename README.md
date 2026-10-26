# tool-aoe2-campanas

Un banco de datos (`.dat`) propio por cada campaña de AoE2 DE, generado desde recetas.

## Instalación (una vez)
```
pip install genieutils-py
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

## Reglas
- Nunca toca archivos del juego.
- En el juego, deja activo **un solo data mod** a la vez.
- `base/` no va a git (pesa ~12 MB por versión); las recetas y scripts sí.

## Próximo
`aplicar <receta>`, `reconstruir`, `arbol` (genera CivTechTrees + vista HTML), `validar`.
