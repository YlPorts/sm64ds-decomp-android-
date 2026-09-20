# Etapa 5 — compilación del conjunto completo de fuentes

**Todavía no hay un APK jugable ni un motor completo enlazado.** Esta etapa intenta compilar con el NDK todas las unidades que CMake selecciona para `walk_window` y sus dependencias. No es una prueba de partida ni una medición de rendimiento.

## Revisión comprobada

- Código: `75ddbbd5b319de35935c27f5cecf52c4830c198d`.
- Rama: `android/native-bootstrap`.
- GitHub Actions: `35495743118`, trabajo `106038229921`.
- Artefacto: `10600059675`, `android-full-engine-compilation-report`.
- NDK: `28.2.13676358`, ARMv7, API 23.
- La rama `main` y las fuentes originales `src/` y `port/` no se editaron.

## Resultado real

| Resultado | Unidades de compilación |
|---|---:|
| Compiladas a objetos nativos | 11.056 |
| Intentadas y rechazadas por el compilador | 259 |
| Bloqueadas por falta de fuente o tiempo de compilación | 0 |
| Total seleccionado | 11.315 |

Son unidades de compilación, no necesariamente archivos únicos, funciones ni porcentajes de juego terminado. La comprobación **termina en fallo** porque todavía hay 259 unidades que no compilan. El proceso no sustituye esas unidades por funciones vacías ni las retira del recuento.

Primera pasada de esta etapa, commit `847cba1e44a0f04bd6c975e7bc5b6efb5f0e019f`, ejecución `35494944209`: 11.038 compiladas, 251 con error y 26 bloqueadas. De las 26 antes bloqueadas, 17 ahora compilan y nueve muestran errores reales; además se resolvió la compilación de I/O con su adaptador nativo. El aumento de errores explícitos no representa un resultado aprobado: hace visibles fuentes antes no comprobadas.

## Qué se integró

1. Un lector del modelo de CMake que conserva la selección de fuentes, lenguaje por archivo, definiciones, cabeceras y opciones específicas. Los scripts y el workflow registran el resultado de cada unidad.
2. La reutilización de los adaptadores nativos ya revisados de `io.cpp`, `runtime.cpp`, `rt.cpp`, `backup.cpp` y `boot2_thread.cpp` dentro del intento de compilación completo. Los cinco archivos adaptados compilaron en la ejecución indicada. Esto aún no constituye su enlace con todo el juego.
3. La separación de los generadores de fuentes de las dependencias de compilación de Windows. Ninja proporciona el orden; se ejecutan los generadores originales revisados, sin invocar el compilador de Windows en esa fase. Resultado: **372 comandos de generación, cero fallos y cero fuentes faltantes**.
4. Anotaciones ELF de almacenamiento y reglas de enlace para las familias de estado. La prueba ARM de enlace relocatable comprueba los límites del bloque, exclusión de datos exclusivos del host, alineación, símbolos débiles y offsets de cartucho (+60 y +1444) y OAM (+8 y +32). Utiliza bloques de prueba con los nombres de sección reales: no valida el guardado de una partida ni el mapa completo del motor.

Los **14 tests Python** y la comprobación de distribución ARM ELF pasaron en Actions. El enlace del motor completo, el arranque de un escenario y la ejecución en teléfono no se realizaron.

## Fallos pendientes, agrupados por el primer diagnóstico de cada unidad

| Grupo | Unidades |
|---|---:|
| Convenciones de llamada de x86: `__fastcall` y `__cdecl` | 213 |
| Dependencias de Windows/x86: cabeceras e importaciones | 21 |
| Declaraciones, tipos y control de flujo C/C++ | 25 |

De las 213 primeras, 209 muestran `__fastcall`. Algunos puentes de tablas virtuales incluyen un segundo argumento reservado para EDX; borrar la palabra del compilador no corrige por sí mismo la firma ni la llamada. Las comprobaciones de atributos no compatibles siguen activadas. También quedan pendientes las diferencias en punteros a miembro, tablas virtuales, alias de símbolos y servicios de plataforma; un objeto que compila no garantiza compatibilidad binaria ni enlace correcto.

## Recursos y límites

Esta comprobación usa el modo explícito **LINK-ONLY** del proyecto: tablas sintéticas, deliberadamente no jugables. No se incluyó una ROM. Dos tareas que requieren imágenes extraídas reales (`romblob_verify.py` y `romblob_recipe.py`) figuran como **NOT RUN** y no se crea su marca de validación. La generación de C/C++ completa no significa que los recursos del juego estén validados.

Las tablas sintéticas de recursos se compilan a O0 para no agotar el límite de tiempo optimizando inicializadores que no serán una versión jugable. Esto se registra en `abi_review`; no es una validación de recursos reales optimizados. El resto conserva las opciones nativas traducibles de su grupo de CMake.

No se ha corregido ni validado el desajuste de declaración de tamaño del bloque de `backup.cpp` señalado en la etapa 4. La distribución de prueba no equivale a corregir ese acceso en el motor. Tampoco hay una implementación completa de restauración de estados.

El objetivo conserva punteros de **32 bits**. El módulo independiente de fibras ARM64 no convierte el juego completo a ARM64. Faltan la adaptación de los puentes de llamadas, las dependencias de Windows, el enlace completo y la integración/validación de recursos, pantalla, audio, controles y ciclo de vida de Android.

## Reproducir la comprobación

Los módulos deben estar dentro del repositorio completo de la revisión indicada; no son un compilador autónomo ni incluyen el SDK/NDK. El procedimiento exacto está en `.github/workflows/android-full-engine.yml`. Los informes contienen comandos por unidad y diagnósticos, y el paso devuelve código de error mientras quede alguna unidad sin compilar.

No interpretar una ejecución roja como un APK perdido: este workflow aún no construye un APK.
