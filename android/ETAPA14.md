# Etapa 14 — las 473 referencias resueltas

**El conjunto completo del motor ya enlaza con NDK ARMv7/API 23. Todavía no es
una APK jugable.** Continúa la etapa 13, commit
`2752179e61ed86bf1b09997b5c5008a628a1d62c`.

| Comprobación | Etapa 13 | Etapa 14 |
|---|---:|---:|
| Unidades originales del inventario | 11.315 | 11.315 |
| Unidades nativas adicionales | 0 | 4 |
| Unidades compiladas | 11.314 | 11.319 |
| Unidades con error | 1 | 0 |
| Grupos de símbolos fuertes duplicados | 0 | 0 |
| Referencias indefinidas al enlazar | 473 | **0** |
| Código de salida del enlace | 1 | **0** |
| Definiciones fuertes originales conservadas | 27.915 | **27.915** |

La auditoría mantiene `--no-undefined` y `--no-gc-sections`. Conserva cada
definición fuerte original en el mismo objeto y con el mismo tipo de símbolo.
No se descartan unidades del motor ni se permiten duplicados. Las bibliotecas
del sistema Android siguen siendo dependencias normales del ejecutable.

## Qué cambió

- **452 alias existentes:** `linkage_aliases.json` traduce las cadenas
  `/alternatename` del port Windows a sus nombres ELF, incluidas las etiquetas
  de retorno de la etapa 13. Las declaraciones se contrastaron con los nombres
  producidos por Clang para MSVC e Itanium. Cada entrada conserva las directivas
  originales y sus archivos de procedencia, comprobados por SHA-256. El proceso
  modifica únicamente referencias indefinidas mediante `llvm-objcopy`; nunca
  renombra un proveedor. El conjunto completo usa las 452 entradas en 1.154
  referencias de objetos.
- **Ocho nombres provisionales de métodos virtuales:** 20 llamadas repartidas
  entre 17 unidades de renderizado se conservan como llamadas virtuales.
  Clang estaba deduciendo el tipo exacto de los subobjetos provisionales y
  llamando directamente a métodos como `Foo::M5`. La adaptación del receptor
  conserva la tabla del objeto, los argumentos y las conversiones del compilador.
- **Seis funciones de fibras:** se incorporan `android/native/src/fiber.cpp`
  y `context.S`, el planificador nativo existente, al enlace completo.
- **Tres referencias de Smartball:** cinco fachadas llaman a los cuerpos C
  originales de la raíz y del tablero. Las definiciones C++ generan también
  el RTTI real de la clase base; no se fabrica un objeto de información de tipo.
- **Una tabla de fundido:** la tabla de `HalFaderWipe` mantiene las diez
  posiciones de la ROM. Se corrige la diferencia entre los destructores de
  MSVC e Itanium, se conecta D1 con el cuerpo original y se exporta el símbolo
  recuperado en la primera función, ocho bytes después de la cabecera ELF.
  D0 continúa llamando al destructor eliminador original.
- **Tres símbolos del frontend:** `main`, `port_frame_ctrl_publish` y
  `port_classname_resolver` tienen proveedores nativos. El registro de clases
  instala el resolvedor; la publicación de Ctrl copia los siete campos a sus
  arreglos separados con el paso original de 24 bytes, hasta 16 jugadores.

`resolve_linkage.py` trabaja sobre copias y objetos de compilación. `src/`,
`include/` y `port/` permanecen intactos.

## Entrada nativa y alcance

`native_scene_main.cpp` sustituye la unidad de interfaz Windows por un ejecutor
finito de escenas: reserva memoria, carga las tablas, inicializa el heap,
ejecuta el arranque y los inicializadores existentes y llama al bucle de escenas
del port. Recibe `--assets`, `--scene` y `--frames`; `--help` describe esa entrada.
No implementa una Activity, presentación en pantalla ni la transición completa
del título a los niveles. La publicación de Ctrl conserva los valores que el
motor ya calculó; la modificación analógica propia de la interfaz Windows no
se incorpora en esta etapa.

**El enlace verificado utiliza todavía las tablas sintéticas LINK-ONLY.**
Su entrada rechaza el arranque con código 3. El código de arranque permanece
enlazado y todas sus dependencias se comprueban. Tener recursos preparados desde
la ROM en la etapa 13 no convierte este inventario en una compilación con esos
recursos. No se distribuye la ROM, un APK ni un ejecutable presentado como juego.

## Verificación ejecutada

- 113 pruebas Python pasaron, incluidas las de rechazo de evidencias alteradas
  y llamadas virtuales que ya no coinciden con las declaraciones revisadas.
- Linux x86-64: pasaron los alias de función/datos y la publicación de Ctrl.
- ARM/Thumb bajo QEMU: pasaron seis conjuntos. Se ejecutaron los lectores
  originales `WithMeshClsn::IsOnGround` y `NestedHeapIterator::Next`, cuatro
  cuerpos originales de `Render`, los cuerpos originales de snapshot/restauración
  de Smartball, las diez entradas del fundido y los límites de Ctrl.
- Los seis conjuntos compilaron y enlazaron además con NDK 28.2.13676358,
  ARMv7/API 23. No se ejecutaron en Android.
- El enlace completo se verificó localmente con el mismo NDK: 11.319 objetos,
  cero errores de compilación, cero duplicados y cero referencias indefinidas.
  El workflow de motor ahora repite las cuatro pasadas y exige ese resultado;
  las pasadas intermedias registran sus fallos conocidos.

Las pruebas de llamadas no demuestran que todos los estados, niveles, tablas,
estructuras y servicios del juego funcionen. Los fallbacks y trampas que ya
existían en el port Windows tampoco desaparecen por traducir sus alias.

## Reproducir

Después de producir `build/signatures` con las tres pasadas anteriores:

```sh
python3 android/full-engine/resolve_linkage.py \
  --baseline build/signatures --output build/linkage \
  --build build/full-graph --ndk "$ANDROID_HOME/ndk/28.2.13676358" --jobs 4
```

Los resultados quedan en `SUMMARY.json`, `provider-retention.json`,
`linkage-evidence.json` y `link-audit/`. El comando falla si falta una unidad,
un proveedor, una evidencia o una referencia de enlace.

Para ejecutar las pruebas de llamadas ARM/Thumb sin ROM:

```sh
python3 android/full-engine/check_native_linkage.py --clang clang++ \
  --cxx arm-linux-gnueabihf-g++ --cc arm-linux-gnueabihf-gcc \
  --objcopy arm-linux-gnueabihf-objcopy --flags='-mthumb' --arm-layout \
  --runner='qemu-arm -L /usr/arm-linux-gnueabihf' --output build/linkage-tests-arm
```

El siguiente bloqueo ya es la integración de recursos reales y ejecución del
motor con el lanzador Android: presentación vertical, entrada, audio, ciclo de
vida, transición a niveles y guardado. Esta etapa no certifica jugabilidad.
