# Disney Clean UI 0.2.5

## Cambios

- Barra lateral contraída sólida, sin arte desplazándose detrás de los iconos.
- Destinos reales de Para ti, Disney+, Hulu y ESPN desde GlobalNav de la cuenta; las marcas abren sus propias páginas.
- Filas de marcas con cinco, seis o siete elementos según el estilo del servicio, sin el título añadido «Marcas».
- Arte panorámico nativo 3:1 para destacados; las alternativas se encajan sin ampliar y recortar otra vez. Logo y metadatos unidos a la misma tarjeta.
- Año/rango, géneros y liga deportiva desde los datos del servicio, incluyendo el contenedor de detalles disponible. No se inventan fechas ni géneros ausentes.
- Filtros de Series/Películas de ancho automático, foco y selección persistentes.
- Fondos y logos propios para páginas high_emphasis/medium_emphasis; desplazamiento de fichas con degradado y encabezado compacto.
- Los destacados interiores conservan su posición: no se ascienden al inicio de la página.
- Reutilización de vistas previas ya recibidas, sin volver a solicitar el mismo set; se conserva la actualización de Continuar viendo y la continuación del resto de filas/títulos.
- Cambio de hub sin crecimiento del historial ni copias repetidas del catálogo; modelos visitados reutilizables durante la ventana.

## Verificación

139 comprobaciones automáticas. Python, XML y recursos construidos desde una sola fuente; autenticación, API pública, DRM, selección de audio, reproductor e intro con audio conservados byte a byte frente a 0.2.1.

Pruebas interactivas en Kodi Windows durante esta revisión: perfiles, los cuatro hubs y sus catálogos distintos, Películas/filtros, ficha de serie, cambio de temporada y episodios, regreso; comparación del banner Mandalorian/Grogu con la foto del usuario. La versión final se instala y comprueba además antes de publicar.

No se han completado diez ciclos con reproducción por hub, una sesión larga ni la prueba del mismo paquete en Chromecast. No se ha controlado el Chromecast durante esta revisión.

## Límites

No se afirma identidad completa con Disney TV. Faltan adaptaciones específicas de algunas filas inmersivas, numeradas y deportivas, y comparación visual de todos sus estados. La reproducción conserva Kodi/SlyGuy y solo están disponibles acciones que entregue el servicio y admita esa integración. Este paquete no acredita la solución del bloqueo intermitente de Kodi Android.

0.2.4 y paquetes anteriores se conservan para reversión. Max no cambia.
