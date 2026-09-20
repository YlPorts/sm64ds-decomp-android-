# Etapa 7 — portabilidad de fuentes y servicios nativos

**No hay APK jugable, motor completo enlazado ni ejecución de un escenario en Android.** Esta etapa continúa la compilación nativa del mismo conjunto de fuentes; los recursos siguen en modo LINK-ONLY, con tablas sintéticas no jugables.

## Revisión y resultados

Base: `f8bf844acc82da790f02187351cad64f73021816`. Código comprobado: `ae8d14dc7b210ebcd4541a0d9b2705f2c32182a9`. Rama: `android/native-bootstrap`. No se modifican `main`, `src/`, `port/` ni `include/`.

GitHub Actions: **35517105337**, NDK **28.2.13676358**, ARMv7, API 23. Trabajo NDK: **106094783638**; pruebas ARM: **106094783668**; pruebas Thumb: **106094783705**.

| Unidades de compilación | Etapa 6 | Etapa 7 |
|---|---:|---:|
| Compiladas | 11.262 | 11.303 |
| Con errores | 53 | 12 |
| Bloqueadas antes de compilar | 0 | 0 |
| Total seleccionado | 11.315 | 11.315 |

Se compararon las identidades de todas las unidades: la selección es idéntica. **41 unidades antes fallidas ahora compilan y ninguna unidad antes compilada pasó a fallar.** Los generadores terminaron sin errores. La ejecución completa sigue en rojo por las 12 unidades pendientes; las pruebas ARM y Thumb terminaron correctamente. Estas cifras no son funciones, archivos únicos ni un porcentaje de juego terminado.

La primera pasada de esta etapa, `2aef98749ff4440339a6aa743febe528c7a724e1`, ejecución **35516714966**, compiló 11.302 unidades y dejó 13 con error. La corrección final adapta un diagnóstico exclusivo de x86 en `scene_vs_menu.cpp` y permite compilar una unidad más.

## Cambios

El nuevo adaptador `adapt_sources.py` usa un manifiesto de **44 entradas de fuentes/cabecera fijadas mediante SHA-256**. La pasada final generó **43 unidades adaptadas**, sin errores de transformación. Conserva todas las unidades seleccionadas, compone las correcciones con los adaptadores anteriores y rechaza entradas modificadas o patrones inesperados.

Se corrigen declaraciones de tablas externas que C++ interpretaba como definiciones incompletas; no se crea almacenamiento ficticio. Los callbacks se convierten explícitamente a los tipos de almacenamiento que esperan sus receptores, conservando direcciones y argumentos. Se concilian prototipos con sus proveedores existentes y tres funciones sin resultados pasan a declararse `void`, junto con los llamadores afectados, sin inventar valores de retorno. Las correcciones de saltos C++ no adelantan las lecturas ni inicializaciones de rutas que el salto omite.

Los temporizadores e intervalos utilizan servicios nativos: `clock_gettime`, `CLOCK_MONOTONIC`, `CLOCK_BOOTTIME` y `nanosleep`, reanudando correctamente las esperas interrumpidas. La lectura del identificador de instancia utiliza el entorno del proceso y conserva sus límites y saneamiento.

Los diagnósticos usan `dladdr`, el desenrollador nativo y una lectura de `/proc/self/maps`. Esta última es solo una instantánea de accesibilidad: **no demuestra que un objeto siga vivo, no es una frontera de seguridad y no protege frente a desmapeos concurrentes**. No se implementa SEH ni se afirma que el desenrollador atraviese correctamente pilas de fibras fabricadas.

El diagnóstico de `scene_vs_menu.cpp` inspeccionaba una posición de pila hipotética de llamadas x86. En ARM se registra el receptor real y se conserva su llamada al cuerpo existente; la medición inaplicable se etiqueta expresamente como `NOT APPLICABLE`, sin fabricar valores de pila. La primera pasada conservaba una referencia al intrínseco y el NDK la detectó; la corrección final elimina esa interpretación de pila, no el comportamiento del juego.

## Pruebas

Las **44 pruebas Python** de los adaptadores y la comprobación ARM ELF de distribución de estado pasaron. Las pruebas Python también se repitieron localmente.

En ARM Linux, mediante QEMU, se ejecutaron y aprobaron en cada modo ARM y Thumb:

- **22 comprobaciones de código recuperado/adaptado**, incluyendo registro DMA, almacenamiento de callbacks y construcción de RotatingFirebar con proveedores de frontera expresamente simulados.
- **22 comprobaciones de servicios nativos**, incluyendo tiempos, espera interrumpida por señal, regiones protegidas, límites, dirección del módulo y trazas.
- **8 casos de identificador de instancia**, cada uno en un proceso separado.
- Los **18 casos de interfaz de llamadas** de la etapa anterior.

El registro DMA y la función que almacena la palabra de callback se compilan desde sus archivos originales. Las demás dependencias que las pruebas no integran son fixtures explícitos; no son funciones vacías añadidas al juego. No se validan un nivel, modelos completos ni animaciones.

Los ejecutables de prueba compilaron y enlazaron también con Android NDK. **No se ejecutaron en un teléfono.** QEMU solo es una herramienta de pruebas de CI, no parte del port. Las 22 pruebas de servicios también pasaron localmente con GCC, Clang y Clang con detección de comportamiento indefinido.

## Doce unidades pendientes

| Archivo | Área pendiente |
|---|---|
| `port/hal/comms_loopback.cpp` | Transporte con WinSock |
| `port/hal/oam_lists.cpp` | Memoria y diagnóstico de sprites dependientes de Windows |
| `port/hal/sdat/out_win.cpp` | Salida de audio y su rama no Windows |
| `port/unmatched/func_02043fdc_hostcopy.cpp` | Tratamiento de fallos de actores dependiente de Windows |
| `port/hal/asset_root_refuse.cpp` | Presentación de errores de recursos |
| `port/hal/pad_backend.cpp` | Entrada y mandos |
| `port/hal/rollback.cpp` | Seguimiento de cambios de memoria |
| `port/hal/rollback_probe.cpp` | Diagnóstico de restauración |
| `port/hal/scene_boot.cpp` | Arranque y servicios del anfitrión |
| `port/hal/stage_geom.cpp` | Orden de inicialización y sección `.CRT$XCV` |
| `port/hal/sub_screen.cpp` | Entrada/presentación de la segunda pantalla |
| `port/tests/walk_window.cpp` | Ventana, bucle interactivo e interfaz de Windows |

Estas no son doce correcciones triviales. Después de compilarlas falta completar el enlace, donde pueden aparecer alias sin resolver y diferencias de tablas virtuales, destructores y punteros a miembro. El inicializador `.CRT$XCV` requiere preservar su orden respecto a otros inicializadores; quitar su atributo sin más no resuelve ese contrato.

Sigue pendiente el desajuste de tamaño de la declaración del bloque del cartucho de `backup.cpp` documentado en la etapa 4. No se ha validado guardado, restauración, recursos reales, audio, controles, presentación, ciclo de vida Android, rendimiento ni GPU. El conjunto conserva punteros de 32 bits; las fibras ARM64 no convierten el juego a 64 bits.

## Evidencias y reproducción

Artefacto final de compilación **10607187038**, SHA-256 del ZIP: `a4d210a6798bba70d27cf06a54c02a6d911ec09456d70c8d7c42d2c32f4cbda7`.

Artefactos de ejecución ARM **10607425998** y Thumb **10607765042**. Se verificaron los hashes de los tres ZIP descargados. Los **60 archivos de código y configuración anteriores a este informe** coinciden byte por byte con los incluidos en la ejecución final de CI.

Los módulos necesitan el repositorio completo. El procedimiento del intento NDK está en `.github/workflows/android-full-engine.yml`. Pruebas de adaptadores: `python3 -m unittest discover -s android/full-engine -p 'test_*.py' -v`.

`check_source_portability.py` acepta `--cc`, `--cxx`, `--flags`, `--output` y `--runner`. Sin runner solo compila y enlaza. Los informes conservan comandos y diagnósticos; el intento completo devuelve error mientras alguna unidad siga sin compilar.

Código nuevo bajo MIT; las fuentes originales conservan su licencia. No se añaden ROM, recursos de Nintendo ni SDK propietario.
