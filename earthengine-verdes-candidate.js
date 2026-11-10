// Milestone exploratory AOI. Point sourced from the Google Maps Verdes by Haven Aldar place result on 28 Oct 2026.
// This circle is NOT a verified cadastral parcel or DLD project match.
var cfg={lon:55.3758125,lat:25.0798125,radius:60,start:'2018-01-01',end:'2026-10-28'};
var site=ee.Geometry.Point([cfg.lon,cfg.lat]).buffer(cfg.radius).buffer(-10);
var s1=ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(site)
 .filterDate(cfg.start,cfg.end).filter(ee.Filter.eq('instrumentMode','IW'))
 .filter(ee.Filter.eq('orbitProperties_pass','DESCENDING'))
 .filter(ee.Filter.listContains('transmitterReceiverPolarisation','VV'))
 .filter(ee.Filter.listContains('transmitterReceiverPolarisation','VH'));
Map.clear();Map.setOptions('SATELLITE');Map.centerObject(site,14);
Map.addLayer(site,{color:'ffcc33'},'Exploratory 50 m AOI');
print('AOI area m2',site.area());print('Nominal 10 m cells (not actual valid pixel count)',site.area().divide(100));
print('S1 scene count before relative-orbit restriction',s1.size());
print('Relative-orbit availability',s1.aggregate_histogram('relativeOrbitNumber_start'));
var panel=ui.Panel({style:{width:'390px',position:'top-left',padding:'12px'}});
panel.add(ui.Label('Milestone | Verdes by Haven map candidate',{fontSize:'20px',fontWeight:'bold'}));
panel.add(ui.Label('Google Maps candidate point. Specific Verdes building and DLD identity NOT spatially verified. Yellow circle is an analysis AOI, not a legal plot.'));
panel.add(ui.Label('Move the year slider to inspect real Sentinel-2 composites. A composite is not a single dated photograph.'));
var dateLabel=ui.Label('');panel.add(dateLabel);
var quality=ui.Label('Loading optical coverage...');panel.add(quality);
var opticalRequest=0;
function optical(year){var request=++opticalRequest;
 var start=ee.Date.fromYMD(year,1,1);var end=year===2026?ee.Date(cfg.end):start.advance(1,'year');
 var raw=ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(site).filterDate(start,end)
 .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',40));
 var images=raw.map(function(im){var scl=im.select('SCL');var mask=scl.neq(0).and(scl.neq(1)).and(scl.neq(3)).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));return im.updateMask(mask).select(['B4','B3','B2']);});
 dateLabel.setValue(year+' optical composite'+(year===2026?' through 27 October (end exclusive)':''));
 raw.size().evaluate(function(n){if(request!==opticalRequest)return;quality.setValue(n+' candidate optical scenes; cloud masking can leave gaps.');if(n>0){var image=images.median();Map.layers().set(0,ui.Map.Layer(image,{bands:['B4','B3','B2'],min:0,max:3000},'Sentinel-2 '+year));Map.layers().set(1,ui.Map.Layer(site,{color:'ffcc33'},'Exploratory AOI'));}else{Map.layers().reset();Map.addLayer(site,{color:'ffcc33'},'No imagery for selected year');}});
}
var slider=ui.Slider({min:2018,max:2026,value:2026,step:1,onChange:optical,style:{stretch:'horizontal'}});panel.add(slider);
panel.add(ui.Label('Interpretation: radar change can reflect structures, clearing or viewing effects. It does not measure interior work, certified completion or handover.'));
Map.add(panel);optical(2026);
s1.aggregate_histogram('relativeOrbitNumber_start').evaluate(function(hist,error){
 if(error){print('ERROR fetching orbit histogram',error);return;}
 var orbits=Object.keys(hist||{}).sort(function(a,b){return hist[b]-hist[a];});
 if(!orbits.length){print('ERROR: no usable radar scenes. Stop.');return;}
 var orbit=Number(orbits[0]);var images=s1.filter(ee.Filter.eq('relativeOrbitNumber_start',orbit)).select(['VV','VH']);
 print('Selected relative orbit (largest scene count)',orbit);print('Filtered scene count',images.size());
 var first=ee.Date(cfg.start),last=ee.Date(cfg.end);var months=ee.List.sequence(0,last.difference(first,'month').floor());
 var observations=ee.FeatureCollection(months.map(function(m){
  var start=first.advance(m,'month');var stop=ee.Date(ee.Number(start.advance(1,'month').millis()).min(last.millis()));
  var subset=images.filterDate(start,stop);var n=subset.size();
  var blank=ee.Image.constant([0,0]).rename(['VV','VH']).updateMask(ee.Image(0));
  var median=ee.Image(ee.Algorithms.If(n.gt(0),subset.median(),blank));
  var stats=median.reduceRegion({reducer:ee.Reducer.mean().combine({reducer2:ee.Reducer.count(),sharedInputs:true}),geometry:site,scale:10,maxPixels:1e6});
  return ee.Feature(null,stats).set({month:start.format('YYYY-MM'),time:start.millis(),image_count:n,orbit:orbit,site_id:'verdes-map-candidate',boundary_verified:false});
 }));
 print('Monthly radar observations, including missing months',observations);
 print(ui.Chart.feature.byFeature(observations,'time',['VV_mean','VH_mean']).setOptions({title:'Monthly temporal median, spatial mean | fixed descending orbit '+orbit,hAxis:{title:'UTC milliseconds since epoch'},vAxis:{title:'Backscatter dB'},pointSize:2,interpolateNulls:false}));
 print(ui.Chart.feature.byFeature(observations,'month',['image_count']).setOptions({title:'Radar scenes per month | missing months remain explicit',vAxis:{title:'Scene count'}}));
 observations.evaluate(function(fc,error){if(error){print('EXPORT_ERROR',error);}else{print('MILESTONE_OBSERVATIONS_JSON='+JSON.stringify(fc));}});
 observations.getDownloadURL('CSV',['site_id','month','VV_mean','VH_mean','VV_count','VH_count','image_count','orbit','boundary_verified'],'milestone-exploratory-monthly',function(url,error){if(error){print('ERROR creating CSV download',error);}else{print(ui.Label('Download real monthly observations CSV',{color:'blue'},url));}});
});