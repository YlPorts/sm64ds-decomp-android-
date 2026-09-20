# Etapa 8 — salida de audio y transporte nativos

**Todavía no hay APK jugable, motor completo enlazado ni escenario ejecutándose en Android.** Esta etapa implementa límites de plataforma reales y continúa la compilación del mismo conjunto de fuentes. Los recursos permanecen en modo LINK-ONLY: tablas sintéticas, deliberadamente no jugables.

## Revisión comprobada

Base: `b55f622d8c64c5788b94194a8508ed47d3a242ed`. Código comprobado: `74d8c3a1e837b94036ce338a8260379d57e7a0fd`. Rama: `android/native-bootstrap`. Las fuentes originales `src/`, `port/`, `include/` y la rama `main` no se modifican.

GitHub Actions: **35518716426**, NDK **28.2.13676358**, ARMv7 y API 23. Trabajo de compilación: **106098963997**. Pruebas ARM: **106098964052**; Thumb: **106098963863**.

| Unidades de compilación | Etapa 7 | Etapa 8 |
|---|---:|---:|
| Compiladas | 11.303 | 11.307 |
| Con errores | 12 | 8 |
| Bloqueadas antes de compilar | 0 | 0 |
| Total seleccionado | 11.315 | 11.315 |

Se compararon las identidades de las 11.315 unidades: el conjunto es idéntico. **Cuatro unidades antes fallidas ahora compilan y ninguna unidad antes compilada pasó a fallar.** Son `comms_loopback.cpp`, la sustitución nativa de `sdat/out_win.cpp`, `rollback_probe.cpp` y `stage_geom.cpp`. La adaptación de `fs_mods.cpp`, que antes compilaba, continúa compilando.

Los 372 comandos de generación terminaron sin fallos ni fuentes faltantes. Las dos comprobaciones que requieren recursos reales permanecen explícitamente NOT RUN. La compilación completa y el resultado global de Actions siguen en rojo por las ocho unidades restantes. Estas cifras no son funciones, archivos únicos ni un porcentaje de juego terminado.

## Audio nativo

`out_android.cpp` reemplaza la unidad de salida Windows, manteniendo su identidad en el inventario y sus interfaces de `sdat.h`. El mezclador y secuenciador originales no se reescriben. El hilo del motor sigue llamando a `sd_mix_render`; publica PCM estéreo de 16 bits en una cola de un productor y un consumidor. El hilo de salida no accede al estado del juego ni ejecuta su mezclador.

La cola usa contadores atómicos sin bloqueo y tiene capacidad para 4.096 frames de audio. Si se llena, descarta el exceso nuevo sin sobrescribir datos que el consumidor esté leyendo; si faltan muestras, entrega silencio. La conversión de 32.768 a 48.000 Hz conserva la fase entre bloques. El reloj de producción alterna 546/547 muestras por tick y suma exactamente 32.768 en 60 ticks. Esto no mide ni garantiza los FPS del juego.

El dispositivo de producción abre AAudio mediante `dlopen`/`dlsym`, comprueba todos los símbolos y el formato obtenido y envía bloques desde un hilo dedicado. Maneja escrituras parciales, tiempos de espera y errores. Para cerrar, primero detiene y une el hilo escritor; después cierra la transmisión. Las funciones de apertura, cierre, envío, volumen y WAV requieren llamadas serializadas desde el hilo del motor. El ciclo de vida de la futura Activity y el foco de audio aún no están conectados.

**La salida audible requiere Android API 26 o posterior y un dispositivo AAudio que acepte el formato solicitado.** Se conserva la compilación base API 23 sin una dependencia obligatoria de `libaaudio.so`. En un sistema sin AAudio se informa de la ausencia de dispositivo y continúan la mezcla y la captura WAV, pero no hay reproducción audible. No se implementó una alternativa OpenSL ES. Una desconexión requiere cerrar y reabrir; no se afirma recuperación automática del dispositivo.

La primera ejecución de esta etapa, **35518535280**, detectó que `decltype` refería declaraciones AAudio no disponibles para API 23. La corrección declara los punteros dinámicos con tipos explícitos y contrasta las 16 firmas con las cabeceras reales del NDK en una compilación adicional API 26. El ELF API 23 se inspeccionó para comprobar que no exige la biblioteca ni símbolos AAudio sin resolver. No se desactivan los diagnósticos de disponibilidad ni se falsea la versión de Android.

## Red e inicialización

La adaptación de `comms_loopback.cpp` conserva su protocolo y lógica de sesión, sustituyendo WinSock por sockets POSIX reales. Incluye resolución IPv4, modo no bloqueante, cierre de descriptores, reintentos de llamadas interrumpidas y rechazo de datagramas truncados. No se añade un transporte simulado al juego. Las pruebas abren exclusivamente dos procesos locales en loopback; no prueban Internet, relay, permisos Android ni una partida multijugador.

El instalador de geometría deja de depender de `.CRT$XCV`. `fs_mods.cpp` lo invoca explícitamente después de instalar su propio filtro, y la instalación es idempotente. Así se conserva la cadena de estos dos filtros sin suponer que una prioridad genérica de constructor ELF equivale al orden de Windows. Se prueban los cuerpos de instalación adaptados con filtros de prueba; no todo el arranque ni la carga de recursos.

El diagnóstico `rollback_probe.cpp` utiliza el reloj monotónico ya adaptado en la etapa anterior. **Esto no implementa el seguimiento de páginas ni el sistema completo de rollback**, cuyo proveedor sigue pendiente.

## Pruebas comprobadas

**50 tests Python aprobados**, además de la comprobación ARM ELF de los bloques de estado. Las pruebas de llamadas y de fuentes/servicios de las etapas previas también pasaron.

En ARM Linux bajo QEMU, tanto en ARM como en Thumb, los nuevos ejecutables aprobaron:

- **29 comprobaciones de audio**: ritmo de muestras, continuidad al dividir bloques, cola llena/vacía, 200.000 frames entre productor y consumidor concurrentes, WAV, fallo de apertura, escrituras parciales, espera, desconexión, cierre y reapertura.
- **16 comprobaciones del límite UDP**: descriptores, puerto ocupado, datagramas demasiado grandes, vacíos y completos, resolución y errores.
- Cadena de filtros y reinstalación, enlazando las unidades en **dos órdenes opuestos**.
- **Dos procesos reales** completan el handshake del transporte original e intercambian un bloque de 32 bytes en cada dirección, comprobando sus contenidos.

**El mezclador y el dispositivo de las pruebas de audio son fixtures explícitos. No se ha escuchado audio del juego ni ejecutado AAudio en un teléfono.** La prueba de red conserva el transporte original, con fixtures solo en los límites del conductor del juego que no integra. Las pruebas de filtros utilizan cuerpos reales adaptados y proveedores sintéticos pequeños.

Los ejecutables de prueba compilaron y enlazaron con Android NDK. La implementación AAudio también pasó la comprobación de tipos API 26 y de carga opcional API 23. La ejecución local de los nuevos límites pasó con GCC, Clang y Clang con detección de comportamiento indefinido; la última comprobación Clang con detección se repitió después de la corrección AAudio. QEMU es exclusivamente una herramienta de CI, no parte del port.

## Ocho unidades pendientes y límites

| Archivo | Integración restante |
|---|---|
| `port/hal/oam_lists.cpp` | Memoria y diagnósticos de sprites |
| `port/unmatched/func_02043fdc_hostcopy.cpp` | Tratamiento de fallos de actores |
| `port/hal/asset_root_refuse.cpp` | Presentación de errores de recursos |
| `port/hal/pad_backend.cpp` | Entrada y mandos |
| `port/hal/rollback.cpp` | Seguimiento de modificaciones de memoria |
| `port/hal/scene_boot.cpp` | Arranque y servicios del anfitrión |
| `port/hal/sub_screen.cpp` | Entrada y presentación de la segunda pantalla |
| `port/tests/walk_window.cpp` | Ventana, bucle interactivo e interfaz |

El primer error de cada una sigue siendo una cabecera de Windows: quitar el include no implementa los servicios que contiene. Después de estas unidades queda completar el enlace, resolver los alias/ABI que aparezcan y arrancar con recursos reales. Persisten el requisito de punteros de 32 bits, la revisión de tablas virtuales y punteros a miembro y el desajuste de declaración de memoria de `backup.cpp` documentado anteriormente. No se valida guardado, restauración, rendimiento, GPU, controles ni un nivel.

## Evidencias y reproducción

Artefacto de compilación **10607897076**, SHA-256: `ebdbd81273445adffcfd49f687b1e7b8d3936391301c4755391469c733925383`.

Artefacto ARM **10607098604**, SHA-256: `db734049fa9817661ab5683100528071a245b462e60cc5ff53aeed350a285258`. Artefacto Thumb **10607891804**, SHA-256: `332de309c377e873cd21d9a03d583b438956e39417248155fd33291fd9e05344`.

Se verificaron los hashes de los ZIP descargados. Los **69 archivos de módulos/configuración anteriores a este informe** coinciden byte por byte con los incluidos en CI. Los cambios abarcan diez rutas, sin editar las fuentes originales. Este informe añade el archivo número 70 de la entrega.

El workflow `.github/workflows/android-full-engine.yml` contiene el procedimiento completo. `check_platform_backends.py --cxx <compilador> --output <directorio>` compila y enlaza; no ejecuta por defecto. Para un compilador de la máquina local, `--runner native` ejecuta los tests; para ARM Linux, use `--runner="qemu-arm -L /usr/arm-linux-gnueabihf"`. La prueba requiere el repositorio completo, no solo este ZIP.

Código nuevo bajo MIT; las fuentes originales conservan sus licencias. No se incluyen ROM, recursos de Nintendo, SDK propietario ni emulador de CPU de DS.
