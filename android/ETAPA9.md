# Etapa 9 — entrada Android y ruta táctil original

**Todavía no hay APK jugable, motor completo enlazado ni escenario ejecutado en Android.** Esta etapa integra un backend de entrada nativo y adapta la pantalla inferior a eventos de toque. No incorpora una Activity ni presenta una superficie Android. Los recursos del intento completo siguen en modo LINK-ONLY, con tablas sintéticas deliberadamente no jugables.

## Revisión y resultados comprobados

Base: `6e4a33c19510cb0e5a5c58395e3f30834819d40c`. Código comprobado: `0e658d49fa4ebe6576d3114751cbdf3514ba9c60`. Rama: `android/native-bootstrap`. No se modificaron la rama `main` ni las fuentes originales `src/`, `port/` o `include/`.

Compilación del conjunto completo: GitHub Actions **35520454247**, trabajo NDK **106103505878**. NDK **28.2.13676358**, ARMv7, API 23. Pruebas de entrada: ejecución **35520454313**, trabajos ARM **106103506545**, Thumb **106103506414** y Android **106103506280**.

| Unidades de compilación | Etapa 8 | Etapa 9 |
|---|---:|---:|
| Compiladas | 11.307 | 11.309 |
| Con errores | 8 | 6 |
| Bloqueadas antes de compilar | 0 | 0 |
| Total seleccionado | 11.315 | 11.315 |

Se compararon las identidades de todas las unidades, no solo los totales: **la selección es idéntica**. La sustitución de `pad_backend.cpp` y la adaptación de `sub_screen.cpp` pasan de error a compiladas. Ninguna unidad que compilaba pasó a fallar. Los generadores terminaron sin errores. La compilación completa sigue en rojo por las seis unidades pendientes. Este recuento no es un porcentaje de juego terminado y no demuestra enlace o ejecución de una partida.

## Entrada nativa

`pad_android.cpp` sustituye la implementación Windows en la misma posición del inventario. Conserva las interfaces originales de `hal/pad_backend.h`. El punto de entrada `sm64ds_android_handle_input` consume eventos NDK reales con `AInputEvent`, `AKeyEvent` y `AMotionEvent`: botones de mando, cruceta, sticks, gatillos, teclado y puntero táctil. No carga XInput, DirectInput ni bibliotecas de Windows.

Los eventos publican un estado coherente bajo un mutex corto; el hilo del motor lee copias. Se mantienen separados los botones y ejes de distintos dispositivos. La primera ranura física ocupada es la activa en cada lectura, y existe un publicador virtual independiente para futuros controles en pantalla. Ese publicador **no dibuja botones ni realiza el reconocimiento de sus zonas táctiles**. La combinación usa OR para botones, máximo para gatillos y el eje de mayor magnitud para cada componente.

El mapeo usa los ejes Android normalizados, con el stick derecho en Z/RZ, inversión de Y al convenio del juego y compatibilidad con gatillos analógicos y botones L2/R2. Se limitan valores fuera de rango y no finitos. No se implementó calibración por rango de dispositivo ni el aprendizaje de diseños DirectInput: sus interfaces devuelven explícitamente no disponible, no un éxito ficticio. Tampoco se ha comprobado compatibilidad con mandos físicos específicos.

La pérdida de foco limpia botones, ejes, estado virtual y propiedad del puntero. Mientras no hay foco se rechazan nuevos eventos interactivos. La cancelación o retirada del dispositivo libera el puntero. Android debe conectar estas funciones al ciclo de vida y a las notificaciones de dispositivos; **un receptor de eventos compilado no equivale a una Activity ya conectada**.

El puntero se identifica por el ID Android, no por su índice en el evento. Otro dedo no puede robar un arrastre activo. La entrada se publica como instantánea, no como una cola de todos los eventos: un toque que empieza y termina íntegramente entre dos lecturas del motor puede no ser observado. La futura integración debe considerar ese límite y la distribución de eventos entre botones virtuales y superficie de lápiz.

## Pantalla inferior

La adaptación de `sub_screen.cpp` sustituye la lectura global de ratón de Windows por una única instantánea de toque Android. Conserva literalmente los cuerpos de transformación de coordenadas, presentación, composición, dimensiones y escritura de BMP comprobados por las pruebas Python. La sección que actualiza `TouchInfo`, calcula los flancos y escribe el anillo de muestras también permanece sin cambios.

Se conservan las zonas de pantalla, márgenes, separación entre pantallas, escala y panel insertado. Un toque en la pantalla superior o en los márgenes no se convierte en un toque inferior. Un arrastre iniciado en la zona válida continúa con sus coordenadas limitadas al borde al salir del panel. Un gesto nuevo pierde la propiedad del arrastre anterior; cuando sustituye a otro entre lecturas se publica primero una liberación y después su nueva pulsación, evitando heredar un arrastre tras un ciclo de foco.

No se ha probado la presentación de píxeles en una Surface Android ni una selección táctil dentro de un menú del juego. La prueba integra el archivo adaptado completo, pero el ejecutable de pruebas solo enlaza las rutas alcanzadas y utiliza proveedores de frontera explícitos para el diseño de pantallas y otros servicios.

## Pruebas

**59 pruebas Python aprobadas**, nueve nuevas y las 50 existentes. Verifican fuentes fijadas mediante hash, anclas de transformación, conservación de unidades, ausencia de importaciones Windows en la entrada adaptada, identidad de los cuerpos conservados y separación entre gestos.

En ARM Linux bajo QEMU, tanto en ARM como en Thumb, se ejecutaron y aprobaron:

- **84 comprobaciones del backend de entrada**, incluyendo eventos inválidos, cancelación, foco, teclas modificadoras, varios dedos, dispositivos y mezcla con el publicador virtual. La prueba publica **100.000 actualizaciones** mientras otro hilo lee y comprueba la coherencia; el número de lecturas depende de la planificación y no se contabiliza como 100.000 lecturas distintas.
- **33 comprobaciones de la ruta táctil original adaptada**, incluyendo escritura de TouchInfo y muestras del anillo, flancos, escalado, márgenes, arrastres, retirada, foco y sustitución de gestos. Layout, BSS de prueba y servicios no integrados son fixtures expresos, no proveedores ficticios añadidos al juego.

Los mismos dos ejecutables compilaron y enlazaron con Android NDK y `libandroid`, incluyendo el receptor de eventos NDK y la comprobación de tamaño y offsets de `PortPadState`. **No se ejecutaron en un teléfono.** La ejecución dedicada de entrada terminó con sus tres trabajos aprobados.

Las pruebas anteriores de llamadas, fuentes/servicios, audio, red e inicialización también volvieron a pasar en ARM y Thumb en el workflow completo, junto con la comprobación ARM ELF. La compilación completa de fuentes terminó en fallo, no se ocultaron las seis unidades pendientes.

Localmente se repitieron la entrada y el toque con GCC, Clang y Clang con detección de comportamiento indefinido; las tres pasadas aprobaron. Las pruebas locales de 64 bits verifican lógica de campos, no convierten a 64 bits la disposición binaria del juego. QEMU se usa exclusivamente como herramienta de pruebas de CI, no forma parte del port.

## Seis unidades que todavía no compilan

| Archivo | Integración pendiente |
|---|---|
| `port/hal/oam_lists.cpp` | Memoria y diagnóstico de sprites |
| `port/unmatched/func_02043fdc_hostcopy.cpp` | Tratamiento de fallos de actores |
| `port/hal/asset_root_refuse.cpp` | Presentación de errores de recursos |
| `port/hal/rollback.cpp` | Seguimiento de modificaciones de memoria |
| `port/hal/scene_boot.cpp` | Arranque y servicios del anfitrión |
| `port/tests/walk_window.cpp` | Ventana, bucle interactivo y presentación |

Sus primeros diagnósticos siguen siendo dependencias de Windows. Eliminar una cabecera no implementa el servicio. Estas unidades siguen bloqueando el intento de enlace completo; **no se ha medido todavía el conjunto de errores de enlace**. También quedan las diferencias de ABI, alias y punteros a miembro que ese enlace revele, recursos reales, Activity, presentación, ciclo de vida, guardado y pruebas de una partida. Persiste el desajuste del bloque de cartucho de `backup.cpp` documentado anteriormente. No se garantiza rendimiento, GPU, FPS ni widescreen del juego.

## Evidencia y reproducción

Artefacto de compilación **10608088513**, SHA-256: `142347c29cc11ac17fa856eda5f707fd7be537d062791b15f76288387f6bef77`.

Artefactos de entrada: ARM **10607978959**, SHA-256 `c5afc03039f5c0dcbdb2d78697acad0249ee1d4824ef122d179cc526fe8f5dec`; Thumb **10608225441**, SHA-256 `dbe932edd08d2c036419f4c396ed12d0cfc64135a08553fa52313227ea56bdc1`; NDK **10607413961**, SHA-256 `db7644e3d454ff178cacf46acefcad3db56b1f3cea4b78fdb88efcdf67f74ff5`.

Se verificaron los hashes de los cuatro ZIP descargados. Los **78 archivos de módulos y configuración anteriores a este informe** coinciden byte por byte con los de la ejecución completa. Los cambios de código abarcan nueve rutas; este informe añade el archivo número 79 de la entrega acumulada.

La comprobación dedicada está en `.github/workflows/android-input.yml`. `check_android_input.py --cxx <compilador> --output <directorio>` compila y enlaza. `--android` enlaza los accesores del NDK; sin `--runner` no ejecuta. Para pruebas locales use `--runner native`; para ARM Linux, `--runner="qemu-arm -L /usr/arm-linux-gnueabihf"`. Necesita el repositorio completo.

Código nuevo bajo MIT; las fuentes originales conservan sus licencias. No se añaden ROM, recursos de Nintendo, SDK propietario ni un emulador de CPU de DS.
