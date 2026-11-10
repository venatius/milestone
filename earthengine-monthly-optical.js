// Milestone: measured monthly optical features, 20 m processing grid.
// Candidate AOIs remain unverified circles, not cadastral boundaries.
var sites=[{id:'exploratory',lon:55.14615,lat:25.033904},{id:'verdes',lon:55.3758125,lat:25.0798125},{id:'orchid',lon:55.1495641,lat:25.0318869}];
var start=ee.Date('2018-01-01'),end=ee.Date('2026-10-28');
sites.forEach(function(s){
 var g=ee.Geometry.Point([s.lon,s.lat]).buffer(60).buffer(-10);
 var raw=ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(g).filterDate(start,end).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',40));
 function features(im){
  var scl=im.select('SCL');var mask=scl.neq(0).and(scl.neq(1)).and(scl.neq(3)).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
  im=im.updateMask(mask);var red=im.select('B4'),nir=im.select('B8'),blue=im.select('B2'),swir=im.select('B11');
  var ndvi=nir.subtract(red).divide(nir.add(red)).updateMask(nir.add(red).neq(0)).rename('NDVI');
  var num=swir.add(red).subtract(nir.add(blue));var den=swir.add(red).add(nir).add(blue);
  var bsi=num.divide(den).updateMask(den.neq(0)).rename('BSI');
  var brightness=im.select(['B2','B3','B4']).reduce(ee.Reducer.mean()).divide(10000).rename('brightness');
  return ndvi.addBands(bsi).addBands(brightness).copyProperties(im,['system:time_start']);
 }
 var months=ee.List.sequence(0,end.difference(start,'month').floor());
 var fc=ee.FeatureCollection(months.map(function(m){
  var first=start.advance(m,'month'),last=ee.Date(ee.Number(first.advance(1,'month').millis()).min(end.millis()));
  var sub=raw.filterDate(first,last),n=sub.size();
  var blank=ee.Image.constant([0,0,0]).rename(['NDVI','BSI','brightness']).updateMask(ee.Image(0));
  var composite=ee.Image(ee.Algorithms.If(n.gt(0),sub.map(features).median(),blank));
  var stats=composite.reduceRegion({reducer:ee.Reducer.mean().combine({reducer2:ee.Reducer.count(),sharedInputs:true}),geometry:g,scale:20,maxPixels:1e6});
  return ee.Feature(null,stats).set({site_id:s.id,month:first.format('YYYY-MM'),image_count:n,scale_m:20,boundary_verified:false});
 }));
 print(s.id+' candidate optical scenes',raw.size());
 fc.evaluate(function(data,error){if(error){print('OPTICAL_ERROR_'+s.id,error);}else{print('MILESTONE_OPTICAL_'+s.id+'='+JSON.stringify(data));}});
});