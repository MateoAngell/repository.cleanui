# Validación local de un candidato Max, sin publicación

`validate_max_local.py` comprueba **el ZIP indicado**, no la fuente que pueda
seguir cambiando. Revalida bytes protegidos/AST/XML/Python contra Max 0.3.2.
Toma un registro JSON de pruebas ligado al SHA-256 completo de ese ZIP y genera
un informe JSON fuera del repositorio. Nunca publica, genera índices, modifica
el APK de Kodi, instala nada ni accede a cuentas/userdata.

```sh
python -B tools/validate_max_local.py ../max-candidates/CANDIDATE.zip \
  ../max-candidates/runtime-records.json --report ../max-candidates/local-report.json
```

La salida sin ADB deja `installed_bytes.status=not_checked`. Un informe generado
correctamente no significa que las pruebas hayan pasado: `publication_state`
es `not_publishable_checks_missing_or_failed` mientras falten pruebas o la
comparación instalada. El código de salida 0 indica que el informe se pudo
completar; **no es una aprobación ni una publicación**. El código 1 señala error
de validación o diferencia de bytes instalados.

## Registro de observaciones

Ejemplo mínimo, que permanece incompleto:

```json
{
  "candidate_sha256": "SHA256_COMPLETO_DEL_ZIP",
  "environment": {
    "device": "Waydroid local",
    "android": "13",
    "kodi": "22.0-RC1 ARM, mismo APK respaldado del Chromecast",
    "notes": "Registrar resolución, densidad, fuente, dependencias y configuración usada"
  },
  "checks": [
    {"id": "profiles", "status": "not_run", "evidence": []},
    {"id": "playback_2h", "status": "not_run", "duration_seconds": 0, "evidence": []}
  ]
}
```

Estados admitidos: `passed`, `failed`, `not_run`, `blocked`. Un `passed` requiere
lista no vacía de referencias de evidencia (archivos/logs/capturas con fecha y
resultado observado). El programa no interpreta esas imágenes ni verifica la
veracidad de una observación humana. No rellenar `passed` por inferencia ni por
haber abierto una pantalla. El informe distingue registros declarados de la
comparación de bytes efectuada automáticamente. Para audio/intro sin escucha,
registrar `not_run` o `blocked`; una captura no demuestra audio.

Se necesitan todos estos IDs, sin duplicados:

- `profiles`: selección, foco y cambio de perfil.
- `home_navigation`: portada completa, mando, cargas y regreso.
- `search`: entrada, resultados, vacíos y errores.
- `collections`: carruseles/colecciones y navegación.
- `detail`: películas/series, metadatos, acciones y regreso.
- `seasons`: temporada, episodios, foco y regreso.
- `intro_complete_audio`: intro íntegra visible y audio observado.
- `playback_resume`: reproducir, salir y recuperar progreso.
- `back_home_reopen`: Atrás, Home y reapertura.
- `service_switch`: Disney → Max y Max → Disney.
- `network_recovery`: pérdida/restauración de red, sin cargas huérfanas.
- `process_recovery`: cierre del proceso por Android y recuperación.
- `ten_open_exit_cycles`: diez ciclos, sin acumular sesiones.
- `performance_memory`: tiempos/memoria antes/después, cargas cancelables.
- `playback_2h`: reproducción continua observada ≥7200 segundos, registrar
  `duration_seconds`, contenido/horas y cualquier fallo.

Completar además revisión de todas las pantallas/UI previstas en el plan y
asociar evidencia concreta a esos registros; esta lista no acredita por sí sola
fidelidad visual ni sustituye las 206 pruebas históricas cuyo código falta.
Las comprobaciones físicas de AC3 en el teatro requieren evidencia del equipo;
las pruebas locales no demuestran esa salida de audio.

## Comparación instalada: solo Waydroid y solo lectura

La invocación siguiente la realiza quien controla el dispositivo; esta entrega
no la ha ejecutado. El único serial admitido es `192.168.240.112:5555`:

```sh
python -B tools/validate_max_local.py ../max-candidates/CANDIDATE.zip \
  ../max-candidates/runtime-records.json --report ../max-candidates/local-report.json \
  --verify-waydroid --serial 192.168.240.112:5555
```

El comando remoto fijo lee mediante `exec-out sh -c` un TAR exclusivamente de
`/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/slyguy.max.cleanui`.
No hace `adb connect`, no usa el dispositivo por defecto, no detiene apps y no
lee datos de cuenta. Rechaza cualquier otro serial, incluido el Chromecast.
Apagar Kodi previamente evita que cambien archivos durante la lectura. Compara
la lista y **todos los bytes** de cada archivo con el ZIP; informa faltantes,
extras y cambios. Solo ignora bytecode generado `.pyc/.pyo/__pycache__`, que se
lista en el informe. Rechaza enlaces, nombres inseguros y duplicados. Incluye
hashes instalados por archivo para trazabilidad.

## Preparación/instalación local a cargo del controlador

No hay despliegue automático en esta herramienta. Para el controlador local:

1. Cerrar Kodi y confirmar ausencia de `pidof org.xbmc.kodi` en el serial fijo;
   abortar si sigue vivo. No tocar el Chromecast ni usar un serial implícito.
2. Extraer el ZIP validado a una carpeta temporal privada, conservando la raíz
   `slyguy.max.cleanui`. Crear TAR solo de esa carpeta: directorios modo `0777`,
   archivos `0666`, sin enlaces ni rutas absolutas. Usar Python `tarfile` y
   asignar `TarInfo.mode` explícitamente; no reutilizar permisos del host.
3. Transferir a `/sdcard/cleanui-candidate-<SHA256>.tar`. Respaldar/mover solamente
   el directorio Max instalado antes de extraer en `.kodi/addons/`; no superponer
   archivos viejos que puedan dejar extras. No borrar ni sobrescribir Disney,
   userdata, cuentas, dependencias o el APK de Kodi.
4. Mantener el directorio de paquete
   `/sdcard/Android/data/org.xbmc.kodi` en su propiedad de app/modo `0770`.
   Si hacen falta permisos restaurados, limitarlos estrictamente a los hijos
   instalados de `files/.kodi/addons/slyguy.max.cleanui`: dirs `0777`, archivos
   `0666`. No aplicar `chmod -R` al paquete ni a `files` completo.
5. Ejecutar la comparación de bytes anterior con Kodi cerrado; solo entonces
   abrir el candidato y registrar las pruebas. Conservar backup para reversión.

Waydroid usa Android 13 y el Chromecast Android 14. Se prueba el mismo APK ARM
Kodi 22.0-RC1, con configuración equivalente documentada (pantalla/fuentes y
transcodificación incluidas); no se afirma equivalencia de GPU, mando, DRM,
rendimiento o audio físico. Esta fase hace **cero cambios al TV**.

## Publicación única, al terminar

El usuario ya autorizó publicar cuando esté completo: no hay un permiso nuevo
introducido por esta herramienta. Antes de editar índice deben estar acabadas
la UI y todas las pruebas obligatorias registradas, las dos horas de reproducción
y la comparación exacta del candidato instalado. Un cambio posterior del ZIP
invalida su registro de pruebas: generar otro SHA y reevaluar lo afectado.

Promover solamente los bytes del ZIP probado a
`slyguy.max.cleanui/slyguy.max.cleanui-0.4.0.zip`, crear su SHA-256 y manifiesto
espejo, y entonces preparar `addons.xml` y su MD5 mediante el flujo habitual.
Revisar diferencias: Disney y versiones anteriores intactos, IDs únicos,
versiones/URL/manifest coherentes, MD5 de los bytes finales del índice y SHA del
ZIP iguales al candidato aceptado. Ejecutar las pruebas de integridad/publicación
y comprobar en una instalación local que Kodi ve la actualización. Publicar
fuente/herramientas/manifiesto de protección y artefactos de esa única entrega;
no incluir cuentas, backups privados ni evidencias sensibles. No publicar
candidatos intermedios. Conservar paquete anterior y documentar reversión.

Este script no ejecuta ninguno de esos pasos de publicación.
