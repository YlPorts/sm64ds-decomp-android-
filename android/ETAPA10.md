# Etapa 10 — controles táctiles y APK de prueba

**Esta entrega incorpora una APK instalable de CONTROLES, no un Super Mario 64 DS jugable.** El motor completo todavía no está enlazado. La aplicación de prueba no solicita ROM, no carga escenarios y no contiene recursos de Nintendo.

## Qué se puede probar

La Activity `org.ylports.sm64ds.controls.ControlsActivity` muestra la palanca, los botones y un panel táctil de diagnóstico. El dibujo es una View Android reutilizable, separado del panel de diagnóstico, y las pulsaciones atraviesan Java → JNI → el mismo backend C++ `pad_android.cpp` utilizado por el port. El marcador y el indicador PAD son diagnósticos: no representan un personaje ni la ejecución del juego.

Los botones usan un relleno tenue y un contorno claro, sin cuadros negros opacos. La pulsación cambia su intensidad. La palanca limita la magnitud en diagonal y permite combinar movimiento con varios botones. Hay vibración opcional mediante la respuesta háptica de Android; no se midió su sensación en un dispositivo físico.

En **Ajustar** se puede cambiar la opacidad entre 15 y 85 %, solicitar un tamaño entre 80 y 140 %, entrar en **Mover**, arrastrar los controles y pulsar **Guardar**, o restablecer el diseño. El tamaño efectivo se limita al espacio disponible. Las posiciones se guardan como fracciones del área utilizable, junto con la opacidad y la vibración, en preferencias privadas de esta aplicación. Al soltar un control en el editor se rechaza la superposición con otro control o el panel de lápiz. Un diseño personalizado puede necesitar reajustes después de cambiar el tamaño o la geometría de la pantalla; no se garantiza separación perfecta de todas las configuraciones personalizadas.

El esquema publicado conserva las máscaras predeterminadas del port: A para salto, B para ataque, X para carrera y ZR como gatillo derecho para agacharse; L/R se reservan a la cámara y START a la pausa. Y es un control auxiliar, sin promesa de una acción predeterminada. En la APK solo se verifican los estados enviados, no esas acciones dentro del juego.

## Pulsaciones y varios dedos

Cada dedo conserva su función durante el gesto: palanca, grupo de botones o lápiz. Se utilizan los identificadores de puntero y no sus posiciones cambiantes dentro del evento Android. Un dedo de los botones no se convierte en lápiz al pasar por el panel; otro dedo no puede robar un arrastre activo. Soltar un dedo no cancela los demás. Cambiar de aplicación, perder el foco o recibir CANCEL libera los controles.

Las pulsaciones virtuales breves se conservan hasta la lectura del consumidor nativo, incluso cuando DOWN y UP ocurren entre lecturas. Se corrigió también el caso de dos gestos completos consecutivos que borraban una pulsación pendiente. Las pulsaciones repetidas del mismo botón antes de una lectura se agrupan, no forman una cola ilimitada. El consumidor de producción debe ser el motor; la View de controles solo publica. El Monitor de esta APK es el consumidor de diagnóstico y no debe añadirse como segundo consumidor al juego.

La retención nueva afecta a botones y gatillos virtuales. El lápiz sigue utilizando la instantánea de la etapa 9: no se ha añadido una cola de toques breves de lápiz ni probado la selección de un menú real.

## Validación

Base: `2a2d2c7723668c6c0ebb7d56a232a3d7a65f0ab5`. Código final de la APK: `9350dc597579245906e3215cb40d860e5ecdac59`. Rama `android/native-bootstrap`; `main`, `src/`, `port/` e `include/` permanecen sin cambios.

La compilación del conjunto de fuentes se comprobó en `8083d5d0eb5cf5efd875f5882710e5dd5b226cf1`, ejecución **35522615197**. Las revisiones posteriores modifican únicamente la interfaz de diagnóstico, su compilación y sus pruebas.

| Conjunto del motor | Etapa 9 | Etapa 10 |
|---|---:|---:|
| Unidades compiladas | 11.309 | 11.310 |
| Unidades con errores | 6 | 5 |
| Bloqueadas antes de compilar | 0 | 0 |
| Total seleccionado | 11.315 | 11.315 |

Se compararon las identidades de las unidades: el conjunto es idéntico, hay una unidad nueva que compila y ninguna regresión. El trabajo completo sigue en rojo. Es compilación de unidades con recursos LINK-ONLY sintéticos, no un porcentaje de juego terminado ni una partida.

La unidad resuelta es `asset_root_refuse.cpp`: el reemplazo nativo conserva la salida fatal con código 2 y registra errores de recursos sin una ventana de Windows. Solo escribe un informe cuando el lanzador proporciona un directorio absoluto mediante `SM64DS_ERROR_DIR`. Se comprobaron ambos mensajes, el código de salida, el rechazo de un enlace simbólico en el destino y la ausencia de escritura en una carpeta no indicada. El futuro lanzador aún debe conectar esa presentación de errores; la APK de controles no es ese lanzador.

Las pruebas del núcleo Java/JNI pasaron con GCC, Clang y GCC con detección de comportamiento indefinido: **4.345 comprobaciones**, incluidas las aserciones repetidas de **1.000 ciclos de pulsación rápida**. No son 4.345 situaciones diferentes ni una prueba de rendimiento. Las 59 pruebas Python existentes también pasaron.

La ejecución de entrada **35522615171** pasó en ARM, Thumb y compilación Android NDK. Conserva las pruebas de la pantalla inferior y amplía las del backend a 90 comprobaciones. ARM/Thumb se ejecutan bajo QEMU en Linux; no son pruebas físicas Android.

La ejecución final de controles **35523647766**, trabajo **106111940751**, terminó correctamente. Se compiló y firmó la APK con NDK **28.2.13676358**, se instaló en el emulador **Android 10 / API 29 x86** y pasaron **31 comprobaciones de eventos framework → View → JNI → backend nativo**. Incluyen varios dedos, movimiento y salto simultáneos, independencia del lápiz, cancelación y dos pulsaciones completas consecutivas. Son eventos sintéticos entregados a la View real dentro de Android; no mediciones de una pantalla física ni una prueba de partida.

La imagen `controls.png` se obtuvo dibujando la View de decoración real, ya distribuida por Android en horizontal, en un Bitmap dentro del emulador. No es un montaje gráfico ni una captura del compositor físico. Se inspeccionó visualmente: las etiquetas, palanca, botones y panel están visibles y separados en la configuración probada. La captura anterior del dispositivo completo mostraba una superposición de arranque y se descartó.

No se han automatizado todas las interacciones con el diálogo de ajustes ni comprobado la persistencia tras matar y relanzar el proceso. La normalización y recuperación de posiciones se comprueban en las pruebas del núcleo y el guardado mediante SharedPreferences está implementado; la comodidad, vibración y compatibilidad con mandos específicos necesitan pruebas físicas.

## APK, compatibilidad y reproducción

Paquete independiente: `org.ylports.sm64ds.controls`, versión `0.10-controls`, código 10. Compila para `armeabi-v7a` y `x86`, API mínima 23. **Necesita soporte de aplicaciones de 32 bits; no incluye ARM64 y no convierte el motor a 64 bits.** La prueba de emulador utiliza x86. No se ha instalado en un teléfono ARM físico.

APK final: **1.454.780 bytes**. SHA-256:

```text
4dcedfaf4e01caf6168a024a99fa8ace2306f90147f3f6c4d385e2e781f647ba
```

Artefacto de APK **10608622976**; SHA-256 de su ZIP:
`d0f46d8d96e5eefbe03648483d8d83fff9de50920a56733624fe07a77cb25abc`.
Artefacto final de evidencia **10609336948**; SHA-256 de su ZIP:
`e13a329f1f600cb1093fbf618cf258d50b3d18b84770e8330062ace9ad42e691`.
Artefacto del intento completo del motor **10608257629**; SHA-256 de su ZIP:
`cb48024b13a1ade19a630646b99bb86fdfcf09b5d826d348e93d73a0829eff5a`.

Se verificaron los tres ZIP y el hash de la APK extraída. Las 17 fuentes incluidas en la evidencia final de interfaz coinciden byte por byte con la entrega local. La entrega acumulada contiene **98 archivos de módulos, documentación y configuración**, incluido este informe; no es el repositorio completo.

La APK se firma con una identidad de depuración desechable; se verifican las firmas v1, v2 y v3. No se distribuye la clave. Otra compilación de diagnóstico puede requerir desinstalar la anterior por su firma diferente; esto borra sus ajustes de controles, no una partida del juego ni otra aplicación.

Para compilar, se necesita el repositorio completo, JDK, SDK con plataforma 35, build-tools 35.0.0 y NDK 28.2.13676358. No se usa Gradle:

```sh
export ANDROID_HOME=/ruta/al/android-sdk
bash android/touch-ui/build_apk.sh "$PWD/build/controls-apk"
```

`test_local.sh` comprueba Java/JNI y el backend en una máquina Linux con JDK y C++. El workflow `.github/workflows/android-touch-ui.yml` compila y firma el diagnóstico e invoca su instrumentación Android. La salida de los comandos de compilación se conserva sin ocultar fallos mediante `tee`.

Quedan sin compilar `oam_lists.cpp`, `func_02043fdc_hostcopy.cpp`, `rollback.cpp`, `scene_boot.cpp` y `walk_window.cpp`. Después faltan el enlace completo, recursos reales, el lanzador del juego, la superficie de presentación, integración de audio/ciclo de vida y pruebas de escenarios y guardado. Esta entrega no garantiza FPS, GPU, widescreen, latencia física ni jugabilidad.

Código nuevo bajo MIT; las fuentes originales conservan su licencia. No se incluyen ROM, recursos de Nintendo ni emulador de CPU DS en la APK.
