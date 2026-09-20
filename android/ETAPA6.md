# Etapa 6 — llamadas nativas ARM

**Todavía no hay un APK jugable, un motor completo enlazado ni ejecución del juego en Android.** Esta etapa adapta puentes de llamadas del port de Windows y vuelve a compilar la misma selección de fuentes con Android NDK. Los recursos siguen en modo LINK-ONLY, con tablas sintéticas deliberadamente no jugables.

## Revisión y resultados comprobados

Base de esta etapa: `c4e5b37621944ac9af09790c5e3caffcfb163996`.
Código comprobado: `75f0121a2692ffcaee0636f6351a30798371f819`.
Rama: `android/native-bootstrap`. No se modificaron `main`, `src/`, `port/` ni `include/`.

GitHub Actions: **35497633563**. NDK **28.2.13676358**, ARMv7, API 23.
Trabajo de compilación: **106043463705**; ejecución de pruebas ARM: **106043463906**; Thumb: **106043463830**.
Informe descargado: artefacto **10601027848**, `android-full-engine-compilation-report`.
SHA-256 de su ZIP: `337f71ef8c322219af12d899febdd2ff047d94f1258ea71688105b0c5f82e79c`.

| Unidades de compilación | Etapa 5 | Etapa 6 |
|---|---:|---:|
| Compiladas a objetos nativos | 11.056 | 11.262 |
| Con errores del compilador | 259 | 53 |
| Bloqueadas antes de compilar | 0 | 0 |
| Seleccionadas | 11.315 | 11.315 |

Se compararon las identidades de las unidades, no solo sus totales: la selección es idéntica. **206 unidades antes fallidas ahora compilan; ninguna unidad que antes compilaba pasó a fallar.** Son unidades de compilación, no funciones, archivos únicos ni porcentaje de juego terminado. El trabajo completo y la ejecución global de Actions siguen en rojo porque quedan 53 errores. No se excluyeron unidades para mejorar el recuento.

## Cambios de código

`android/full-engine/adapt_calls.py` genera copias para ARM en el directorio de compilación. Los puentes `__fastcall` que reservaban un segundo argumento para EDX pierden ese argumento tanto en la declaración/definición como en las llamadas explícitas. Los parámetros reales conservan su orden, incluidos los que pasan por registros o por la pila. Las anotaciones `__cdecl` revisadas se adaptan a la convención natural del compilador ARM.

Los dos puentes de retorno de vector, `port_actor_s30_base` y `whomp_s30`, ahora devuelven un agregado real de 12 bytes. Es el compilador quien genera el convenio nativo de retorno; los cuerpos recuperados que rellenan el vector se conservan. Esto evita tratar como equivalentes un retorno de puntero de Windows y un retorno de estructura de ARM.

La adaptación incluye dos cabeceras revisadas, también cuando CMake las fuerza con `/FI`, y normaliza la firma UTF-8 inicial antes de insertar comentarios o cabeceras generadas. La pasada final adaptó **219 fuentes y dos cabeceras**, sin errores de transformación.

Las entradas se comprueban contra los árboles Git originales fijados y contra hashes de las fuentes generadas revisadas. Un formato o archivo desconocido se rechaza. Los comentarios y literales no se reescriben. Las comprobaciones de atributos incompatibles siguen activadas; no se silenció `-Werror=ignored-attributes`. El adaptador es específico de esta revisión, no un conversor universal de ABI C++.

## Pruebas

- **33 tests Python aprobados**, incluidos 19 casos del nuevo adaptador y los 14 existentes.
- Comprobación ARM ELF de límites, alineación y posiciones relativas de los bloques de estado: aprobada.
- **18 casos de llamadas ejecutados y aprobados en ARM Linux, tanto en modo ARM como en Thumb, mediante QEMU**.
- Compilación y enlace de esas pruebas con Android NDK: aprobados. El ejecutable Android no se ejecutó en un teléfono.

La prueba usa llamadas virtuales compiladas en una unidad separada: enteros, punteros, argumentos adicionales en la pila, valores de 64 bits, punto flotante, ajustes del receptor, macros y llamadas explícitas. Incluye el llamador de modelos generado por `hostgen.py`, los cuerpos recuperados de retorno de vector de Actor y Whomp y **1.000 retornos de vector con comprobaciones de memoria alrededor del resultado**. Son pruebas de interfaz de llamadas, no una partida ni una validación completa de modelos o animaciones. Los recursos del modelo y su configuración son dobles de prueba expresamente identificados.

La primera ejecución de esta etapa falló al enlazar porque a la prueba le faltaba su proveedor de configuración `port_model_shrink_enabled`. Se añadió únicamente al fixture de prueba; no es una función vacía añadida al juego ni una implementación de la configuración de producción.

## Qué sigue pendiente

Agrupando por el primer diagnóstico de cada unidad, quedan **21 dependencias de Windows/x86** y **32 errores de declaraciones, tipos, control de flujo o secciones de inicialización**. Entre ellos están cabeceras de Windows, importaciones, arrays sin tamaño, firmas incompatibles, saltos C++ y una sección de inicializadores de Windows todavía no trasladada a ELF. Los diagnósticos completos están en `build/full-report/errors`.

El enlace completo puede descubrir problemas adicionales: alias de símbolos, tablas virtuales, destructores, punteros a miembro y servicios de plataforma. Compilar un objeto no demuestra que su ABI sea correcto en todas las rutas. No se validaron el guardado, restauración de estados, audio, controles, ciclo de vida Android, GPU, rendimiento, escenas ni niveles. Se mantiene el requisito de punteros de 32 bits; el módulo de fibras ARM64 no convierte el motor a ARM64.

El objetivo siguiente es resolver las unidades restantes y el enlace del motor antes de probar un escenario con recursos reales. No se incorporaron ROM, recursos de Nintendo, SDK propietario ni emulador de CPU de DS. QEMU solo ejecuta las pruebas de CI.

## Reproducción

Los módulos deben estar dentro del repositorio completo de la revisión indicada. El procedimiento del intento completo está en `.github/workflows/android-full-engine.yml`. Para las pruebas Python: `python3 -m unittest discover -s android/full-engine -p 'test_*.py' -v`.

`android/full-engine/check_call_abi.py` permite compilar las pruebas con `--compiler`, seleccionar los indicadores de compilación con `--flags` y ejecutarlas opcionalmente con `--runner`. Sin `--runner` solo compila y enlaza; con `--objects-only` ni siquiera enlaza. No presenta ninguna de esas modalidades como ejecución de Android.

Código nuevo bajo MIT; las fuentes del proyecto original conservan su licencia.
