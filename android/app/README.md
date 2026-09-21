# APK del motor nativo — versión de desarrollo

El juego se compila con Clang/NDK para ARMv7. La APK no incluye un emulador
de CPU Nintendo DS ni una ROM: importa los recursos de una ROM local ASMP,
Europa, revisión 0. El port conserva las capas de hardware y los cuerpos
descompilados de `port/` y `src/`, compilados como código nativo.

**Estado:** el ejecutor del motor ha completado 120 fotogramas de la pantalla
de título con recursos reales. Sus bibliotecas también se cargan dinámicamente
y componen tres fotogramas por las entradas JNI. La APK compila y verifica su firma. Aún no se
ha validado una partida completa ni su funcionamiento en un teléfono.

## Usar la APK de prueba

1. Instalar `SM64DS-Motor-Prueba.apk` en Android con soporte para aplicaciones
   ARM de 32 bits. Android 6 es el mínimo; el audio nativo requiere Android 8.
2. Descomprimir el `.7z` y seleccionar el `.nds` europeo, revisión 0.
3. Esperar a la verificación e importación y pulsar **Iniciar motor**.
4. **Ajustar** permite modificar tamaño, opacidad y posición de los controles.
   **Salir** regresa al lanzador. El registro está en **Ver registro de arranque**.

Un teléfono que solo admite aplicaciones ARM64 no puede instalar esta versión.
La disposición de punteros del motor sigue siendo de 32 bits.

## Compilar

Requisitos: inventario completo de la [etapa 14](../ETAPA14.md), Python 3.10+,
`ndspy`, JDK 17, Android NDK 28.2.13676358, plataforma y Build Tools 35.0.0,
`rg` y `zip`. Ejecutar desde la raíz del repositorio.

```sh
python3 android/full-engine/prepare_rom.py /ruta/al/juego.nds
python3 android/full-engine/build_runtime.py \
  --baseline build/linkage --output build/runtime --build build/full-graph \
  --ndk "$ANDROID_HOME/ndk/28.2.13676358" --jobs 4
python3 android/app/build_native.py \
  --runtime build/runtime --build build/full-graph \
  --ndk "$ANDROID_HOME/ndk/28.2.13676358" --output build/app-native
bash android/app/build_apk.sh "$PWD/build/app-native" "$PWD/build/engine-apk"
```

`--baseline` identifica la salida de `resolve_linkage.py`; no debe ser la
misma carpeta que `--output`. El inventario contiene rutas absolutas a sus
fuentes y debe haberse generado en el entorno de compilación actual.

La compilación real sustituye las tablas de LINK-ONLY por tablas inicializadas
a cero, sus reubicaciones y una receta de reconstrucción. Comprueba las 12.273
entradas de recursos y las 9.897 posiciones de tablas empaquetadas en el ELF.
Las fuentes originales no se modifican. Las correcciones de ABI se aplican a
copias generadas bajo `build/runtime/sources`.

La APK lleva dos bibliotecas nativas, las clases Java y tres archivos de
metadatos: receta, manifiesto y hash de ROM admitida. El empaquetado usa una
carpeta temporal nueva y exige esa lista de recursos. No empaqueta `romdata.bin`,
los archivos extraídos ni el `.nds`. La clave de desarrollo permanece en la
carpeta de salida para permitir reinstalar compilaciones de la misma máquina.

## Validar la importación sin Android

El mismo `RomImporter.java` de la aplicación puede ejecutarse en el host:

```sh
mkdir -p build/import-tests
javac --release 8 -d build/import-tests \
  android/app/java/org/ylports/sm64ds/nativeport/RomImporter.java \
  android/app/tests/ImportProbe.java android/app/tests/RomImporterChecks.java
java -cp build/import-tests org.ylports.sm64ds.nativeport.RomImporterChecks \
  /ruta/al/juego.nds build/assets/romdata.recipe.tsv build/assets/romdata.manifest \
  ce5829aaa79f06c67140ed1f45cbca738b0a9d0180538c8c1498472d859db032 \
  build/import-test-output
```

Usar una carpeta de salida vacía para esta prueba. Comprueba importación,
reparación al reimportar, rechazo de otra ROM, conservación de la instalación
si falla la receta, limpieza de temporales y límites de lectura/descompresión.

El ejecutor `build/runtime/link-audit/engine-link-diagnostic` permite probar
escenas con `--assets`, `--scene` y `--frames`. Definir también
`SM64DS_ASSET_ROOT` antes de iniciar el proceso, pues los inicializadores del
filesystem se ejecutan antes de `main`. La biblioteca JNI prepara ese entorno
antes de cargar el motor y mantiene su ejecución en un único hilo dedicado.

## Límites de esta entrega

- La prueba del motor usa un entorno de pruebas ARM/Bionic; no mide rendimiento
  de un móvil ni valida el audio AAudio del dispositivo.
- El cierre del lanzador, pausa, mandos y controles están conectados al motor,
  pero la interacción completa de la APK requiere validación en Android.
- No se han comprobado las transiciones del título a todos los niveles,
  guardado, multijugador ni las rutas de código pendientes heredadas del port.
