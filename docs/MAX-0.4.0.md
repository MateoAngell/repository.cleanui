# HBO Max Clean UI 0.4.0 — versión de prueba

Publicada por solicitud expresa del usuario para actualizar desde CleanUI Repository y probar después en su Chromecast. Esta entrega conserva trabajo en curso; no se presenta como réplica completa ni versión estable validada en el dispositivo.

## Cambios activos

- Perfiles con proporciones 1080p, recorte circular, fondo y foco revisados.
- Sinopsis del destacado, navegación lateral y acceso a Mis cosas.
- Búsqueda con teclado español para TV y resultados reales en cuadrícula; descarte de consultas anteriores.
- Fichas, texto completo, selección de temporadas y episodios; navegación lateral desde la ficha hacia la portada existente.
- Mi lista con cuadrícula de cuatro columnas usando los datos existentes.

La implementación usa la referencia estática de Max TV 7.14.0.69 y recorridos observados en Waydroid a 1920×1080. Las APK oficiales, cuentas y datos privados NO se incluyen en GitHub.

## Integridad y pruebas

90 comprobaciones automáticas aprobadas: 29 de integridad/publicación, 28 de presentación, 6 del prototipo Ajustes y 27 del prototipo de controles de vídeo. Los dos últimos recuentos no prueban funciones activas: el nuevo panel de Ajustes y el overlay de reproducción permanecen sin integrar/habilitar. Los controles de reproducción existentes se conservan.

El constructor verifica 21 archivos byte a byte y 22 métodos del controlador por AST frente al paquete publicado Max 0.3.2. API, plugin, cuentas, DRM, audio, entrada, vídeo de intro y observación de reproducción se preservan. Disney y los accesos/coordinador instalados no se modificaron en esta publicación.

Kodi 22.0-RC1 se instaló localmente en Waydroid y arrancó con configuración copiada. Se observó la versión anterior y se colocó una candidata intermedia comprobando sus bytes. **Los bytes finales de esta publicación no completaron validación visual ni funcional en Kodi.** Las pruebas finales locales se interrumpieron a petición del usuario para publicar lo disponible.

## Pendientes y límites

- Recorridos finales, foco, búsqueda, fichas, temporadas, regresos, diez ciclos, memoria y recuperación de red/proceso.
- Reproducción, reanudación, selección de audio/subtítulos y prueba continua de dos horas pendientes; Waydroid no dispone de Widevine.
- Fidelidad total y rendimiento del Chromecast, intro/audio en esta candidata y salida AC3 del teatro pendientes de prueba física.
- SlyGuy no implementa gestión completa de perfiles ni sincronización de historial remoto; no se añaden acciones falsas ni se cambia el backend. No se afirma equivalencia completa con la app oficial.

## Actualizar y volver atrás

Actualizar HBO Max Clean UI desde CleanUI Repository en Kodi. No hace falta instalar manualmente un ZIP ni borrar cuentas/caché. Si Kodi aún muestra 0.3.2, comprobar actualizaciones del repositorio.

El paquete 0.3.2 y su SHA permanecen en su ruta original para reversión explícita; no se sobrescribieron versiones anteriores. Volver a una versión anterior requiere seleccionar/restaurar ese paquete expresamente: Kodi no hace downgrade automático por cambiar el índice.

SHA-256 del paquete 0.4.0: `0b9e284f6cae41206b446fab3f5ff7fc2d0c562a1978c09971903b7eb21e0338`.
