# Etapa 13 — firmas C++ y recursos reales

**El motor sigue sin enlazar y todavía no hay una APK jugable.** Esta etapa
continúa `android/native-bootstrap` desde `768c7b3811e86ca1d0182bca6cdebdc0457601e0`.

## Resultado

| Comprobación del conjunto completo | Etapa 12 | Etapa 13 |
|---|---:|---:|
| Unidades seleccionadas | 11.315 | 11.315 |
| Unidades compiladas con NDK ARMv7/API 23 | 11.314 | 11.314 |
| Unidades con error | 1 | 1 |
| Grupos de símbolos fuertes duplicados | 21 | 0 |
| Referencias indefinidas detectadas al enlazar | No concluyente | 473 |

Los duplicados impedían al enlazador mostrar el siguiente conjunto de errores.
Las 473 referencias son diagnósticos de enlace, no un recuento de funciones que
haya que reescribir. Incluyen adaptaciones de nombres/calling conventions,
declaraciones provisionales y símbolos del frontend de Windows.

## Adaptación

MSVC diferencia firmas que Itanium fusiona: retornos `bool`/`int`, `void`/`int`,
distintos punteros, métodos estáticos frente a métodos con receptor, clases
frente a namespaces y ciertas declaraciones de destructores o parámetros.

`native_signatures.py` aplica etiquetas ABI sobre ubicaciones del AST de Clang.
`isolate_signatures.py` localiza tanto proveedores como llamadores en los objetos
reales, preprocesa las 312 unidades afectadas y adapta sus declaraciones y
definiciones. Conserva las conversiones y los cuerpos originales. No modifica
`src/`, `include/` ni `port/`, no tolera duplicados y no agrega funciones vacías.
Las unidades restantes se conservan. La auditoría verifica cada definición
fuerte anterior en el mismo objeto y con el mismo tipo de símbolo.

La separación no implementa las variantes que ya carecían de proveedor ni
convierte todas las directivas `/alternatename` del port Windows. El informe
de enlace conserva esos errores, incluida la variante `void` de NewSimple y
la variante que devuelve `HeapAllocator*` de Next.

## ROM y pruebas

`prepare_rom.py` prepara los recursos locales de una ROM europea ASMP revisión 0.
Rechaza rutas de extracción inseguras y estructuras de overlays incompatibles.
Corrige la falta de `overlays.yaml` en la ruta de extracción con ndspy: sus datos
se obtienen de la tabla real del cartucho. La ROM de prueba produjo 103 overlays,
2.072 archivos NitroFS, 2.058 handles y un `romdata.bin` de 946.194 bytes.
Estos archivos permanecen en directorios ignorados por Git. La herramienta es
para desarrollo; **no es todavía un importador de ROM dentro de Android**.

- 106 pruebas Python pasaron.
- 14 comprobaciones de enrutamiento pasaron en Linux x86-64 y ARM/Thumb con QEMU.
  Incluyen el lector original `WithMeshClsn::IsOnGround`: el retorno entero 16
  se conserva, mientras la fachada booleana devuelve 1.
- El mismo conjunto pasó con AddressSanitizer y UndefinedBehaviorSanitizer.
  LeakSanitizer se desactivó en la prueba local porque el entorno usa ptrace.
- El conjunto compiló y enlazó con NDK 28.2.13676358 para ARMv7/API 23.
  No se ejecutó en Android ni en un teléfono físico.
- La compilación completa y su auditoría se ejecutaron localmente con ese NDK.
  El enlace retorna error y se informa como tal.

## Reproducir

Después de las dos pasadas descritas en ETAPA12:

```sh
python3 android/full-engine/isolate_signatures.py \
  --baseline build/isolated --output build/signatures \
  --build build/full-graph --ndk "$ANDROID_HOME/ndk/28.2.13676358" --jobs 4
```

El código de salida sigue siendo distinto de cero mientras el enlace falle.
`SUMMARY.json`, `signature-retention.json`, `signatures/` y `link-audit/` conservan
los resultados. El workflow `android-signature-tests.yml` verifica las rutas de
llamada; no compila ni certifica un juego completo.

Preparación de recursos desde un `.nds` extraído del archivo adjunto:

```sh
python3 -m pip install ndspy
python3 android/full-engine/prepare_rom.py /ruta/al/juego.nds
```

## Pendientes

Resolver las referencias restantes y sustituir el frontend/bucle
`port/tests/walk_window.cpp`; integrar recursos reales con el motor enlazado y
el lanzador; comprobar presentación, audio, ciclo de vida, niveles y guardado.
La interfaz vertical anterior se conserva. Los recursos preparados no equivalen
a un arranque validado y las pruebas de firmas no validan las estructuras y
tablas virtuales de todos los actores del juego.
