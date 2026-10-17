# Disney Clean UI 0.2.4

Publicación solicitada para probar en Chromecast HD. No constituye una validación completa de todas las funciones ni una reproducción idéntica de Disney TV.

## Cambios

- Continuación integrada de títulos y categorías al navegar, sin tarjetas ni botón visible «Ver más».
- Extremo horizontal cerrado; retorno entre rangos de filas conservados con ocho controles reciclados y solapamiento visual.
- Sin aviso «Preparando…» en la esquina de Inicio y fichas. Errores recuperables con Reintentar/Volver conservados.
- No descartar conjuntos por palabras como ESPN, deportes o Premium; conjuntos vacíos no consumen las ocho filas útiles.
- Galería principal resuelta desde su conjunto completo, sin mezclar otros carruseles destacados.
- Cuadrículas: continuación hacia abajo conserva columna; extremo inferior sin volver al principio.

## Verificación y límites

120 pruebas automáticas pasan. En Kodi Windows se comprobaron perfiles, Inicio, 15 destacados, continuación horizontal de 20 a 30 títulos, extremo final, filas de Hulu/ESPN entregadas por el servicio y recorrido 8→9→8→9 sin nueva carga para volver al rango visitado. Los últimos ajustes de cuadrícula tienen regresiones automáticas; falta su recorrido visual y las pruebas generales completas. No se ejecutaron diez ciclos ni una nueva validación de reproducción completa con este paquete.

Código y recursos idénticos a la construcción local instalada, excepto el número de versión en addon.xml. API, autenticación, reproducción, DRM, audio e intro intactos respecto a la base protegida. Los hubs Disney+/Hulu/ESPN completos y más detalles visuales siguen pendientes. Chromecast pendiente de prueba del usuario. Max y versiones anteriores conservados.

ZIP: 927182 bytes, 89 archivos.
SHA-256: `89a3430847c7f190a22f91acf47ff6ce425462252fd4cc60a15ce83bdc4304e6`.
MD5 del índice exacto: `9bfa5c7d3785e0167dfb66deff12baf8`.

No se incluyen APK, fuentes descompiladas, registros privados ni datos de cuenta.
