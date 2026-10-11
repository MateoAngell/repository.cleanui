# Diagnóstico privado de Disney y Max

Un solo servicio Kodi sirve a ambos add-ons. Arranca con Kodi, termina con él y
no bloquea la reproducción. Registra muestras cada 5 s durante uso y cada 15 s
en reposo, eventos del reproductor, contadores de la interfaz, configuración
técnica de audio/búfer/decodificación y señales saneadas de kodi.log/kodi.old.log.
No modifica esos ajustes. No activa el registro de depuración global.

No recoge cuentas, PIN, cookies, claves, URLs de reproducción, DRM, títulos,
nombres de perfiles ni textos libres de errores. Lo desconocido se descarta.
No descarga contenido, mide velocidad por Internet ni recopila otras apps.
Los datos no disponibles son null: no significan cero ni ausencia de fallos.

En Chromecast guarda cuatro segmentos rotatorios, hasta 16 MiB en total.
Exportaciones opcionales acotadas y archivos de estado mantienen el presupuesto
por debajo de 20 MiB. No borra credenciales, caché global ni registros de Kodi.
Un inicio después de una sesión no finalizada se marca como recuperación,
no como prueba de crash: también puede deberse a cortar la electricidad.

## Laptop

collector.py usa ADB previamente emparejado, solo con el identificador confirmado.
Descubre su puerto actual por mDNS, verifica la identidad y hace lecturas acotadas
cada 60 s. No abre un servidor ni sube información a Internet.
Guarda registros saneados en la carpeta privada elegida: retención de 14 días,
límite de 256 MiB. La retención elimina únicamente sus propios registros fechados.
La laptop necesita estar encendida, con sesión iniciada y en la misma red.
Si se pierde la conexión, queda esperando; la captura Kodi sigue localmente.

ADB puede aportar memoria del proceso/sistema, contadores CPU/hilos y motivos
numéricos de salida de org.xbmc.kodi (ApplicationExitInfo), si Android permite
esas lecturas. Acceso denegado se registra como no disponible, sin intentar root.
La velocidad de red, señal Wi-Fi y temperatura no se infieren del búfer.
Si Android impide leer el almacenamiento de la app, la recogida de diarios Kodi
queda pendiente; no se cambian permisos ni seguridad para sortearlo.

## Detener

En Kodi: Programas → Clean UI Diagnóstico → Desactivar registro automático,
o desmarca su ajuste Registro automático. Los add-ons siguen funcionando.
La laptop dejará de recoger Android cuando vea el estado desactivado.
En Windows: deshabilita la tarea CleanUIChromecastDiagnostics, o cambia
enabled a false en la configuración privada. La depuración inalámbrica puede
desactivarse manualmente en Chromecast. No se publican informes en GitHub.

Para investigar: anota hora aproximada, add-on, vídeo/intro o navegación,
y si saliste a Google TV o cerraste Kodi. Los datos permiten correlacionar;
no demuestran por sí solos que la caché o el add-on sea la causa.
