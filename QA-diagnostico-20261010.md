# Diagnóstico automático: alcance y pruebas del 10 de octubre de 2026

Versiones: Max 0.2.26, Disney 0.1.46, Clean UI Diagnóstico 0.2.0.
Entrega de instrumentación, no una corrección demostrada del bloqueo Android.

## Verificado

- 175 pruebas automáticas ejecutadas: 174 aprobadas y una omitida.
  Incluyen 15 nuevas de saneamiento, datos malformados, sesión interrumpida,
  cierre, captura desactivada, disco lleno, rotación, transferencias parciales,
  deduplicación, exclusión de dispositivos y retención sin tocar archivos ajenos.
- Construcción desde los ZIP previos, comprobación de sintaxis Python 3.8/XML,
  CRC y correspondencia byte a byte con la instalación Windows.
- Autenticación, API, catálogo, DRM, resolución de vídeo, ajustes de audio y
  recursos visuales/intros quedan byte a byte iguales a las versiones anteriores.
- Kodi Windows controlado visualmente: inicio del servicio, intro/perfiles de
  Disney, Inicio, ficha y episodios; vídeo visible, pausa/reanudación, detener,
  regresar a ficha e Inicio, salir y cerrar/reabrir Kodi.
- Max: Inicio, ficha, solicitud de película y vídeo visible. Los eventos y
  muestras entraron al diario con atribución correcta de los eventos de UI.
- El servicio registró finished al cerrar Kodi, liberó la propiedad de sesión
  y reinició sin ZIP automático, consultas finales ni hilo retenido.
- Las primeras muestras Windows costaron entre 0 y 78 ms (granularidad de reloj
  Windows); esto es tiempo de muestreo, no comparación de rendimiento Android.
  No hubo descargas de diagnóstico ni de imágenes adicionales.
- Recolector Windows instalado como una tarea privada sin ventana, con cuenta
  actual y permisos limitados. Reconecta únicamente al Chromecast emparejado;
  configuración e informes no forman parte del código publicado.

## Pendiente / limitaciones

- El emparejamiento ADB y una conexión real funcionaron; después el usuario apagó
  Chromecast para dejar las pruebas para mañana. No se ha probado la transferencia
  de diarios del nuevo servicio desde Android ni sus permisos de almacenamiento.
- No se reprodujo ni se diagnosticó aún el bloqueo/negro de Kodi en Chromecast.
  Las sesiones no finalizadas no prueban por sí solas un crash o una caché dañada.
- No se ejecutaron hoy pruebas de dos horas, diez ciclos por add-on, ni una
  validación exhaustiva de cada sección. La reproducción Windows fue breve.
- No se cambiaron búferes, cachés, decodificación, transcodificación ni AC3.
  Las muestras incluyen datos no disponibles como null.
- Android puede restringir /proc, logcat o archivos de la app: se informa de
  ausencia sin intentar root ni alterar permisos de seguridad.

## Uso

Actualizar ambos add-ons desde el repositorio; la dependencia de diagnóstico
se instala/actualiza junto con ellos. Reiniciar Kodi una vez tras actualizar.
La captura local funciona con Kodi abierto. La recogida a laptop necesita
sesión Windows iniciada, laptop encendida y misma red. Datos privados en
outputs/chromecast-diagnostics; 14 días / 256 MiB, sin nube ni servidor.
Desactivar en Programas → Clean UI Diagnóstico o en su ajuste Registro automático.
Anotar la hora del próximo fallo para correlacionarlo con los registros.
