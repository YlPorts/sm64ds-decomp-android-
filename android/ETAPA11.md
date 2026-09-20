# Etapa 11 — interfaz vertical, memoria nativa y primeros conflictos de enlace

**No hay todavía un Super Mario 64 DS jugable.** La APK adjunta es el diagnóstico de controles 0.11, sin carga de ROM ni ejecución de escenarios. El motor completo no enlaza.

## Revisiones y ejecuciones

Base de la entrega anterior: `729f79dd4b81a953d74a3f4c21d8fba2f06f7b3e`.
Se conservó el avance de memoria y manejo de fallos publicado durante esta integración, `671a57d91194fcf5b91ef8f01e0274134ab831a2`, sin sobrescribirlo. Encima se publicó la interfaz vertical `fb871ea842ea398bbc6fc4ae1bd47858fc656f46` y la corrección de puentes `3958e444f3efade0d80c6bd8de5b0d698ce4ef04`.

Rama: `android/native-bootstrap`. No se modificaron `main`, `src/`, `port/` ni `include/`. La entrega acumulada necesita el repositorio completo; no sustituye sus fuentes originales.

- Interfaz vertical: Actions **35525221055**, terminada correctamente.
- Motor y pruebas nativas: Actions **35526276643**, terminada con fallo de compilación/enlace. Los trabajos ARM y Thumb pasaron, así como la comprobación de los 64 proveedores originales.
- Referencia del primer censo de enlace: Actions **35524629399**, código `671a57d`.

## Orientación y controles

La interfaz anterior imponía `sensorLandscape` en el manifiesto. No era una exigencia del juego: era una decisión del prototipo. Ahora la Activity abre en **vertical** (`portrait`) y distribuye dos paneles **4:3 apilados**, sin girarlos ni estirarlos. `DsLayout.java` calcula sus dimensiones y reserva una zona inferior independiente para los controles. Las áreas del diagnóstico todavía no presentan imágenes del juego.

El panel inferior conserva la entrada de lápiz. La palanca y los botones quedan debajo de ambos paneles, sin taparlos en el diseño predeterminado comprobado. Continúan la opacidad ajustable, el tamaño limitado al espacio disponible, el editor de posiciones, las pulsaciones simultáneas, la retención de botones breves y la liberación al perder el foco. Se separaron las preferencias verticales de las posiciones guardadas del antiguo diseño horizontal.

La geometría se comprobó en cuatro tamaños verticales y tres escalas. Pasaron **5.001 aserciones** del conjunto Java/JNI, que incluyen las pruebas anteriores y repeticiones; no son 5.001 situaciones distintas. En el emulador Android 10/API 29 x86 pasaron **42 comprobaciones** sobre la View y el backend real: eventos, varios dedos, pulsaciones rápidas, orientación, proporciones y controles debajo de las pantallas.

`controls.png` es un Bitmap dibujado por la View de decoración real dentro del emulador. Se inspeccionó visualmente: aparecen los dos paneles y los nueve controles separados. No es una captura de una partida ni una medición del compositor o de una pantalla física. No se ha probado un teléfono, la sensación háptica, todas las posiciones personalizadas ni todas las interacciones con el diálogo de ajustes.

## Compilación del motor

| Unidades seleccionadas | Etapa 10 | Esta entrega |
|---|---:|---:|
| Compiladas a objetos ARMv7 | 11.310 | 11.314 |
| Con errores | 5 | 1 |
| Bloqueadas antes de compilar | 0 | 0 |
| Total | 11.315 | 11.315 |

El conjunto mantiene las mismas identidades; no se excluyen unidades para mejorar el recuento. Las cuatro unidades que ahora compilan son `oam_lists.cpp`, `func_02043fdc_hostcopy.cpp`, `rollback.cpp` y `scene_boot.cpp`. La compilación final usa NDK **28.2.13676358**, ARMv7, API 23, y conserva las tablas sintéticas **LINK-ONLY**, deliberadamente no jugables.

La adaptación incorporada reemplaza la reserva de memoria de Windows por `mmap`, obtiene diferencias reales de bytes para las páginas lógicas de los registros de restauración y conserva las rutas originales de instantánea/restauración. No es un proveedor ficticio de `GetWriteWatch`; comparar regiones tiene un coste distinto y no se ha medido su rendimiento en el juego.

Los rechazos intencionados de actores pasan por una excepción C++ específica. Los fallos reales de memoria no se convierten en falsos éxitos. Las pruebas verifican destrucción de objetos de prueba al desenrollar, identificación del actor y terminación de procesos separados ante fallos fatales. Eso no prueba todas las rutas entre unidades C/C++ ni la seguridad de toda la gestión de actores. Los experimentos de diagnóstico exclusivos de x86 que no se trasladaron se identifican como no disponibles/no ejecutados.

La unidad restante es **`port/tests/walk_window.cpp`**, con la ventana y el bucle interactivo de Windows. No se ha sustituido por un `main` vacío ni por una lista de servicios que no hacen nada. Sigue siendo trabajo real de integración Android.

## Enlace: error distinto de la compilación individual

El primer intento de enlace con referencias retenidas detectó **874 grupos de símbolos fuertes definidos varias veces**. Una causa concreta es que los puentes del port Windows exportaban nombres C con la forma de los nombres C++ Itanium, mientras que en Android el método C++ original ya exporta precisamente ese nombre.

Esta entrega retira **64 definiciones redundantes** de `method_faces.cpp` únicamente en la copia generada para Android. Son llamadas calificadas con un solo receptor y retorno compatible revisado. Se conserva cada implementación recuperada original, sin crear alias, implementaciones vacías, símbolos débiles o reglas que permitan duplicados. Los puentes con conversión de argumentos o de retorno, destructores, tablas virtuales y puentes inversos quedan fuera de esta lista inicial.

El adaptador exige la identidad del archivo original, el cuerpo esperado, el destino y receptor correctos, y exactamente un proveedor seleccionado para cada símbolo. El censo posterior de **objetos reales del NDK** comprobó **64/64 proveedores originales conservados de forma única**.

Resultado final: **810 grupos de símbolos fuertes duplicados**, 64 menos. El enlazador imprime 801 diagnósticos únicos de duplicados usando nombres descompuestos; ese número no es el censo de 810 símbolos originales. El enlace sigue fallando. Que en esta fase aparezcan cero diagnósticos de símbolos indefinidos **no demuestra que todos estén resueltos**: los duplicados impiden completar el análisis.

Las pruebas nuevas enlazan la unidad completa adaptada de puentes con **11 implementaciones originales** de colisión, flags y temporización, llamadas desde C. Pasaron **145 comprobaciones en ARM y 145 en Thumb**, ejecutadas en ARM Linux bajo QEMU. Incluyen escritura limitada de campos, enlaces de la lista de colisión, preservación de memoria y retornos de 64 bits. El reloj, la cabeza de lista y los bloques de almacenamiento son fixtures explícitos; no se ejecutan actores ni escenarios completos. El enlace reducido de esta prueba descarta código no utilizado; el censo de enlace completo NO lo descarta.

Las mismas pruebas compilaron y enlazaron con Android NDK, pero no se ejecutaron en Android. QEMU es solo una herramienta de CI, no un emulador DS incluido en el port. Pasaron **75 pruebas Python**; las pruebas anteriores de interfaces de llamadas, memoria, audio, red, entrada e inicialización no se sustituyen por este subconjunto. Se repitieron localmente las pruebas Python y las rutas de memoria/fallos con Clang. Una ejecución local de prueba de fallos intencionados bajo UBSan no se cuenta como pasada: el sanitizador intercepta el fallo en vez de producir la señal que espera ese test.

## APK y evidencia

Paquete: `org.ylports.sm64ds.controls`. Versión `0.11-portrait-controls`, código 11. API mínima 23; ABI `armeabi-v7a` y `x86`. Necesita soporte para aplicaciones de **32 bits**. No contiene motor ARM64 ni juego. Sigue siendo una APK de diagnóstico firmada con una identidad de depuración desechable: otra firma anterior puede exigir desinstalar SOLO el diagnóstico anterior, perdiendo sus ajustes.

APK: **1.458.876 bytes**. SHA-256:
`2980d1cbcd3d2cdde6d613fb290457928ef1f6035d7c424a0438f42580d3752e`.
Se comprobaron las firmas v1/v2/v3 según el registro y el hash de la APK extraída.

Artefactos:

- APK vertical **10609955580**, ZIP SHA-256 `6a1e2de561b08b9e984ccb97addb01c946a4504133964cc2371b8f5ab14518b7`.
- Evidencia vertical **10610395066**, ZIP SHA-256 `17a53435d810bd1433e293b384d162c7cf715369c2c379a671a5b1274aaab8d6`.
- Motor final **10609667604**, ZIP SHA-256 `cec582339c6719932e4697bd7fb4c45086c1e047f74bdcd117e32a88e83f3810`.
- Pruebas ARM **10610175974**, ZIP SHA-256 `4abdbccf54d9cf04bc6b22a8f6edb3545a2cdadd1e9a8ca6625bab497e143569`.
- Pruebas Thumb **10610026951**, ZIP SHA-256 `317f94871ea118672954919563483ec145097d6c3cea18877c4fefd13ae1e07e`.

Los hashes de los cinco ZIP se verificaron. Los **115 archivos de fuentes/configuración anteriores a este informe** coinciden byte por byte con la ejecución final, excluyendo caches Python. Este informe es el archivo acumulado 116. El paquete incluye un parche desde la etapa 10 y registros de las comprobaciones.

## Bloqueos que siguen abiertos

Faltan el reemplazo de la ventana/bucle principal, los conflictos restantes de enlace y ABI, la integración del lanzador y sus recursos reales, la presentación de imágenes y el ciclo de vida/audio, además de escenarios, transiciones y guardado probados. Persiste la revisión del bloque de cartucho de `backup.cpp` documentada antes. Los campos de 32 bits, tablas virtuales y punteros a miembro no se vuelven correctos por compilar un objeto. No se afirma que los 810 grupos sean la lista final de problemas ni se da un porcentaje de juego terminado.

Reproducción: `.github/workflows/android-full-engine.yml` y `.github/workflows/android-touch-ui.yml`. Código nuevo MIT; fuentes originales con su licencia. No se incluyen ROM, recursos de Nintendo ni SDK propietario.
