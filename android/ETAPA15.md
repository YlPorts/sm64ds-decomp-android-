# Etapa 15 — recursos reales y aplicación Android

Se integra el motor de la etapa 14 en una APK ARMv7 con importador de ROM,
lanzador, doble pantalla, controles táctiles y entrada de mando. El ejecutor
nativo completa 120 fotogramas de la pantalla de título: una inicialización,
119 llamadas a Behavior, 120 a Render y cero entradas en las 24 trampas contadas
por el ejecutor durante esa prueba. La imagen muestra la estrella y
«Touch to Start». Esto no demuestra que una partida completa funcione.

## Correcciones comprobadas durante el arranque

- Reserva de memoria antes de los inicializadores ELF que publican NitroFS.
  Solo se reserva: iniciar IPC antes de registrar el modelo ARM7 producía una
  espera indefinida.
- Inicialización explícita del planificador en el hilo que ejecuta el motor,
  después de cargar las tablas y antes del arranque del sistema del juego.
- División entera sin recursión a `__aeabi_idiv` / `__aeabi_uidiv`. Los antiguos
  cuerpos usaban `/`, que en ARMv7 podía llamar otra vez al propio cuerpo.
- Conservación de los espacios entre tablas. Clang eliminaba arreglos internos
  sin uso y alteraba los desplazamientos originales. Se marcan `used` y se
  verifican 9.897 diferencias de direcciones en el ejecutable y en la biblioteca.
- `FS_OpenFileFast` (`func_0205d568`) recibe explícitamente las dos palabras
  de `FSFileID`. Leer más allá de un parámetro local perdía el índice de archivo.
  El archivo de sonido ahora se abre con sus 282 entradas de FAT.
- La biblioteca exporta únicamente sus entradas JNI. Exportar el `_Znwj` del
  juego hacía que inicializadores de bibliotecas Android dependientes usaran
  el heap del juego antes de su arranque. Ambas bibliotecas enlazan su runtime
  C++ estáticamente y se auditan sus dependencias. La cola táctil usa almacenamiento
  fijo para no asignar memoria durante `dlopen`.
- `func_ov007_020c3550` y `func_ov007_020c99d8` devuelven explícitamente el
  descriptor gráfico. Se comprobaron los epílogos de ov007 en los rangos
  `020c3570..020c3594` y `020c9a1c..020c9a28`: conservan el resultado en r0.
  La declaración `void` y la ausencia de `return` lo perdían bajo Clang.

Todo se aplica en `android/` o en copias generadas. `src/`, `include/` y `port/`
permanecen intactos. No se introducen funciones vacías para ocultar errores.

## Aplicación

`android/app/` contiene el importador Java usado también por las pruebas del
host. Verifica el hash de la ROM, extrae NitroFS y overlays, reconstruye el blob
del motor y comprueba cada tramo. La instalación se prepara en una carpeta
temporal y reemplaza la anterior únicamente al terminar correctamente.

Un pequeño bootstrap JNI prepara rutas y registro antes de cargar el motor.
`GameActivity` usa un proceso separado para poder reiniciar sus variables
globales al salir y un solo hilo para inicialización, lógica y renderizado.
La interfaz copia las dos pantallas bajo mutex y entrega los eventos táctiles
mediante una cola; conserva las pulsaciones que llegan entre fotogramas.
Se reutiliza la interfaz de controles de las etapas anteriores.

## Evidencia local

| Comprobación | Resultado |
|---|---|
| Objetos del ejecutor real | 11.320 |
| Referencias indefinidas / símbolos fuertes duplicados | 0 / 0 |
| Entradas de recursos comparadas con la ROM | 12.273 correctas |
| Posiciones de tablas, ejecutable y `.so` | 9.897 correctas en cada uno |
| Archivos importados por Java frente a extracción Python | 2.184 idénticos |
| Importación, reparación, entradas inválidas y limpieza | Correctas |
| División con y sin signo | 20.128 casos correctos en NDK ARMv7/Bionic |
| Pruebas Python del motor | 113 correctas |
| Pantalla de título en el ejecutor NDK | 120 fotogramas, salida 0 |
| Biblioteca de la APK cargada dinámicamente | 3 fotogramas compuestos por las entradas JNI |
| APK de desarrollo | Compilada; firmas v1, v2 y v3 verificadas |
| Partida completa / teléfono físico | No verificados |

La ejecución usa QEMU de usuario para correr el binario NDK contra Bionic API
23 en el entorno de desarrollo. Se detectó que esta combinación de QEMU y
jemalloc reutilizaba páginas sin ponerlas a cero en `calloc`; un interpositor
local de pruebas asegura el borrado. **Ese interpositor y QEMU no se incluyen
en la APK.** Esta limitación del banco de pruebas se conserva en el informe;
no equivale a una validación en un dispositivo Android.

La prueba inicial de 120 fotogramas agotó su límite de 90 segundos. La repetición
con un límite de 180 segundos completó los 120 con salida 0. Las capturas de
30 y 120 muestran animación en la pantalla inferior; la superior muestra solo
el fondo y todavía requiere revisión del renderizado.

Instrucciones de instalación y compilación en [app/README.md](app/README.md).
