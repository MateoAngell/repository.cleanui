# Disney 0.2.0 / Max 0.3.0 — candidatas para probar

Publicación solicitada para probar el rediseño en Chromecast. **No es una entrega
estable ni una réplica terminada de las aplicaciones de TV.** Las referencias
visuales son las webs oficiales a 1920 × 1080.

## Cambios incluidos

- Galería destacada independiente, flechas, puntos y avance automático nativo.
- Desplazamiento de página y cabecera fija; Series/Películas con filtros y
  cuadrícula en Disney; menú lateral Explorar en Max.
- Fichas con episodios en línea, selector de temporadas y pestañas. Corrección
  del foco del selector y de la reproducción de la temporada elegida.
- Cargas de metadatos serializadas, resultados cancelados descartables e historial
  por ventana. Fondo propio y recursos nativos de animación/esquinas redondeadas.
- Disney: corrección del tráiler de entidades próximas que no incluyen una acción
  de reproducción de película. No se cambiaron autenticación, resolución, DRM,
  cabeceras de audio ni vídeos de intro con su audio.

## Comprobado

- 283 pruebas automáticas; integridad del ZIP, XML y sintaxis Python 3.8.
- Kodi Windows: intros y perfiles en ambos; galería y fichas; Max Explorar/Series,
  vídeo visible, pausa, detención y regreso. Disney: episodios y selección de
  temporada, reproducción, Mi lista, Series y Detalles; tráileres VisionQuest y
  Doomsday visibles, incluido final natural y retorno del segundo.
- Las últimas variaciones menores tienen pruebas automáticas; no se repitió todo
  el recorrido visual con los bytes finales exactos.

## Pendiente / limitaciones conocidas

- Completar navegación de todas las áreas, filtros, paginación, búsqueda, ajustes,
  extras y cambio de perfil con error de red.
- Diez ciclos por complemento, reanudar/cancelar y reproducción continua de dos
  horas. No se ha demostrado la corrección de los bloqueos intermitentes.
- Una solicitud HTTP ya iniciada puede terminar tras cerrar; su resultado no se
  aplica. Falta comprobar que la reapertura rápida no acumule trabajo.
- Fidelidad visual completa, filas especiales y transiciones sin destellos.
- Rendimiento del Chromecast HD y audio AC3 del teatro en casa sin validar.

Las versiones anteriores Disney 0.1.46 y Max 0.2.26 se conservan sin modificar
para reversión. No hace falta borrar caché ni credenciales para actualizar.

## SHA-256 de los ZIP

- Disney 0.2.0: `480bebc04c07d5de6c93efe201e7377c232053d0bf7d4f875410090666bc7780`
- Max 0.3.0: `56c10b0e5eb4050d4fcb1c988eb02f6d2e652431603dafcad954f9a456c7c7f7`
