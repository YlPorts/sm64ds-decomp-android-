# Etapa 12 — separación de símbolos y enlace nativo

**Todavía no hay un Super Mario 64 DS jugable ni un motor completo enlazado.**
Esta entrega trabaja en el motor; no genera otra APK de controles ni sustituye el juego por un emulador. La interfaz vertical de la etapa 11 queda intacta.

## Resultado comprobado

Base remota de esta integración: `908c2a5d062e52926481c6f385c1eb6037675766`.
Código probado y publicado: `4775a05f400604ade0648b5c7131005ce8172e63`.
Rama: `android/native-bootstrap`. No se modifican `main`, `src/`, `port/`, `include/` ni `android/touch-ui/`.

| Comprobación sobre el mismo conjunto | Primera pasada | Con separación de identificadores |
|---|---:|---:|
| Unidades seleccionadas | 11.315 | 11.315 |
| Unidades compiladas | 11.314 | 11.314 |
| Unidades con error | 1 | 1 |
| Bloqueadas antes de compilar | 0 | 0 |
| Grupos de símbolos fuertes duplicados | 810 | 21 |

Son **789 grupos de duplicados menos**, no 789 archivos nuevos compilados ni un porcentaje de juego terminado. No se excluyeron unidades del conjunto ni se habilitó una opción del enlazador para tolerar duplicados.

La comparación local verificó la identidad, el objetivo y el hash de las fuentes de las 11.315 unidades, sin regresiones de compilación. Después se reprodujo la doble compilación desde cero en GitHub Actions, con el mismo resultado de 21 grupos pendientes.

## Qué cambia

Una parte del port de Windows utiliza identificadores C escritos literalmente como `_ZN...` y `_ZTV...`, con la forma de nombres C++ codificados. En Android, el compilador también emite esos nombres para los métodos y tablas C++ auténticos. Antes coexistían implementaciones y puentes diferentes con el mismo nombre de enlace.

`android/full-engine/isolate_symbols.py` construye un mapa de identificadores a partir del censo real de la primera pasada. Recompila todas las unidades con una cabecera adicional que separa los identificadores explícitos bajo el prefijo `sm64ds_cabi`. Los nombres que el compilador genera para métodos C++ no se cambian mediante esas macros.

Esto conserva ambas direcciones del puente: C hacia C++, y métodos C++ que llaman a implementaciones C recuperadas. No se eliminan sus cuerpos ni sus conversiones de parámetros y resultados. Tampoco se mezclan las tablas explícitas con las tablas que produce el compilador. Las 64 fachadas sencillas retiradas y comprobadas en la etapa 11 se mantienen tal como estaban; esta etapa no vuelve a introducirlas.

El segundo paso exige que cada definición fuerte anterior siga presente en el MISMO objeto y con el MISMO tipo de símbolo. La auditoría de retención comprobó **27.915 definiciones**:

- **27.104** conservaron el nombre.
- **806** pasaron al prefijo de identificadores explícitos.
- **5** eran identificadores explícitos declarados con enlace C++ y recibieron la correspondiente recodificación del nombre de función libre.

No faltó ninguna de esas definiciones ni apareció un proveedor prefijado inesperado. Este censo cuenta definiciones por objeto, no solamente funciones ni nombres únicos. Retener símbolos no demuestra por sí solo que todas las rutas de ejecución sean correctas.

## Pruebas

Pasaron **95 tests Python**, incluidos 20 nuevos sobre validación del mapa, comandos reproducidos, rechazo de fuentes cambiadas, conservación de proveedores, tipos de símbolos y nombres C++ codificados dos veces.

Las pruebas sintéticas primero exigen que el caso sin separación falle realmente por símbolos duplicados; después comprueban que las dos rutas coexistan y produzcan resultados distintos cuando el puente convierte argumentos o valores devueltos. Cubren llamadas desde C, retornos de estructuras, constructores, destructores y separación de tablas.

Ese conjunto aprobó **7.003 aserciones**, incluidas repeticiones de 1.000 ciclos, con GCC y Clang en Linux. También pasó localmente con AddressSanitizer y UndefinedBehaviorSanitizer. No son 7.003 situaciones diferentes ni una medición de rendimiento.

El mismo conjunto pasó en **ARM y Thumb mediante QEMU sobre Linux**. Además, una prueba separada enlazó las unidades originales de puentes con **cinco funciones recuperadas originales**: `Animation::SetFlags`, `Animation::GetFrameCount`, el constructor de `PathPtr`, la consulta `Player::IsState` y `Sound::Func_02048eb4`.

La prueba de funciones originales aprobó **8.000 aserciones en ARM y 8.000 en Thumb**. El almacenamiento del jugador, el destructor de Animation y la salida inferior de Sound son límites de prueba explícitos. No son objetos de una partida completa, una prueba de sonido audible ni una validación de la destrucción de actores del juego. En esta prueba reducida se descartan secciones sin utilizar; el censo completo del motor NO descarta código para esconder referencias.

Ambos conjuntos también compilaron y enlazaron con Android NDK 28.2.13676358, ARMv7/API 23. Esos ejecutables Android no se ejecutaron en un teléfono. QEMU se usa únicamente en CI, no se incorpora a la aplicación.

## GitHub Actions

Ejecución dedicada: **35529577030**, trabajo **106127675478**.
La validación, la doble compilación con censo de símbolos, la retención de proveedores y las pruebas ARM/Thumb/NDK terminaron correctamente.

**El resultado global de la ejecución es failure.** La comprobación final exige un motor completo compilado y enlazado, y rechaza el estado actual. No se presenta el éxito del diagnóstico como una compilación jugable.

Artefacto: **10611300478**, `native-symbol-isolation-evidence-NOT-GAMEPLAY`.
SHA-256 del ZIP:

```text
adda90ed812b9d6f0efaf85a4d0875de8d3d57ad96a4049eeb4976ebf433cdb2
```

Se verificó el hash del ZIP y la igualdad byte por byte de las 11 fuentes del nuevo módulo incluidas en la evidencia de CI con la entrega local. El workflow es el duodécimo archivo añadido de código/configuración. Este informe es el decimotercer archivo nuevo.

## Qué sigue abierto

La unidad `port/tests/walk_window.cpp` continúa sin compilar: conserva la ventana y el bucle interactivo de Windows. Esta entrega no la sustituye por un `main` vacío y no afirma haber terminado la integración del bucle Android.

Los **21 grupos de símbolos restantes** no son simplemente los mismos identificadores C de antes. Entre ellos hay declaraciones de métodos con igual nombre de enlace pero distinto retorno: `bool`/`int`, `void`/`int`, y variantes de punteros. También hay fachadas repetidas y funciones provisionales antiguas. Hay que resolverlas junto con sus llamadores, sin perder conversiones ni elegir arbitrariamente una definición. El paquete incluye el censo exacto y un informe local de tipos obtenido del AST de Clang.

En esta fase aparecen cero diagnósticos de símbolos indefinidos, pero eso NO prueba que todas las funciones estén resueltas: los duplicados todavía impiden completar el análisis del enlazador.

Se siguen usando tablas sintéticas **LINK-ONLY**, deliberadamente no jugables. Quedan el enlace completo, el reemplazo del bucle principal, la integración de recursos reales y del lanzador, la presentación, el ciclo de vida/audio y las pruebas de escenarios, transiciones y guardado. Las tablas virtuales, estructuras de 32 bits y punteros a miembro del motor completo aún necesitan validación de ejecución.

## Reproducción y contenido

El workflow `.github/workflows/android-symbol-isolation.yml` ejecuta ambas pasadas desde el repositorio completo. Sobre una primera compilación y su censo ya generados:

```sh
python3 android/full-engine/isolate_symbols.py \
  --build build/full-graph --baseline build/full-report \
  --output build/isolated --ndk "$ANDROID_HOME/ndk/28.2.13676358" --jobs 4
```

Devuelve un código distinto de cero mientras el motor siga incompleto. `--audit-only` permite volver a examinar los objetos ya recompilados, verificando el mapa de macros antes del censo y la retención.

La entrega acumulada contiene **129 archivos de módulos, pruebas, configuración y documentación**, además del parche y de los informes. Se aplica sobre el repositorio completo; no incluye el repositorio completo, ROM, SDK propietario, NDK, claves de firma ni un APK nuevo. Las 116 fuentes/configuraciones del paquete anterior permanecen idénticas. Código nuevo MIT; las fuentes originales conservan su licencia.
