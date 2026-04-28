(function () {
  const RADAR_LAYER_PREFIX = "rainviewer-radar-layer";

  function getFirstLayerIdByPrefix(map, layerPrefix) {
    const style = map.getStyle();
    const layers = (style && style.layers) || [];
    const layer = layers.find(function (candidateLayer) {
      return candidateLayer.id.indexOf(layerPrefix) === 0;
    });

    return layer && layer.id;
  }

  function getFirstRadarLayerId(map) {
    return getFirstLayerIdByPrefix(map, RADAR_LAYER_PREFIX);
  }

  function addBelowRadar(map, layerDefinition) {
    map.addLayer(layerDefinition, getFirstRadarLayerId(map));
  }

  function moveAboveCountyBoundaries(map, layerId) {
    if (map.getLayer(layerId)) {
      map.moveLayer(layerId);
    }
  }

  window.MOLECAST_LAYER_ORDER = {
    addBelowRadar: addBelowRadar,
    getFirstRadarLayerId: getFirstRadarLayerId,
    moveAboveCountyBoundaries: moveAboveCountyBoundaries,
  };
})();
