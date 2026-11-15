"""Sample actual Sentinel scenes on fixed ~100 m squares around sourced viewing points."""
import concurrent.futures as cf
import calendar
import sys
import json,math,struct,threading
from pathlib import Path
import numpy as np
import requests


ROOT=Path(__file__).resolve().parent
API='https://planetarycomputer.microsoft.com/api'
ARCHIVES=[json.loads((ROOT/n).read_text()) for n in ('wayback-capture-index-2026-11-15.json','wayback-capture-index-2026-11-15-frond.json')]
POINTS={k:tuple(s['centre']) for a in ARCHIVES for k,s in a.items()}
SITES=('village','frond','como','naya','mall')
SCENES=json.loads((ROOT/'optical-village-sampled-2026-11-10.json').read_text())['features']
local=threading.local()

def get(path,params=None):
    if not hasattr(local,'session'):local.session=requests.Session()
    for attempt in range(3):
        try:
            r=local.session.get(API+path,params=params,timeout=23)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt==2:raise

def bands(bbox,collection,item,keys):
    box=','.join(f'{v:.8f}' for v in bbox)
    out=[]
    for key in keys:
        response=get(f'/data/v1/item/bbox/{box}/10x10.tif',{'collection':collection,'item':item,'assets':key})
        blob=response.content
        if blob[:4]!=b"II*\x00":raise ValueError("Expected little-endian TIFF")
        offset=struct.unpack_from('<I',blob,4)[0]
        tag_count=struct.unpack_from('<H',blob,offset)[0]
        tags={tag:(kind,count,value) for tag,kind,count,value in
              (struct.unpack_from('<HHII',blob,offset+2+i*12) for i in range(tag_count))}
        def tag(n,default=0):return tags.get(n,(0,0,default))[2]&65535
        if (tag(256),tag(257),tag(259),tag(284),tag(278))!=(10,10,1,1,10) or tags[273][1]!=1:
            raise ValueError("Unsupported TIFF layout")
        dtype={(8,1):'u1',(16,1):'<u2',(32,3):'<f4'}.get((tag(258),tag(339,1)))
        if not dtype:raise ValueError("Unsupported TIFF sample encoding")
        pixels=np.frombuffer(blob,dtype=dtype,count=100*tag(277),offset=tags[273][2]).reshape(10,10,-1)
        valid=pixels[:,:,1]>0 if pixels.shape[2]==2 else np.ones((10,10),dtype=bool)
        pixels=np.where(valid,pixels[:,:,0],np.nan)
        out.append(pixels)
    return out

def sample(task):
    site,kind,scene=task
    lon,lat=POINTS[site]
    dx=.00045/math.cos(math.radians(lat));dy=.00045
    bbox=(lon-dx,lat-dy,lon+dx,lat+dy)
    period = scene if isinstance(scene, str) else None
    if period:
        year, month = map(int, period.split('-'))
        interval = f'{period}-01T00:00:00Z/{period}-{calendar.monthrange(year, month)[1]}T23:59:59Z'
    if kind=='radar':
        # Search one October window per year and retain one relative orbit throughout.
        found=get('/stac/v1/search',{'collections':'sentinel-1-rtc','bbox':','.join(map(str,bbox)),
            'datetime':interval if period else f'{scene}-10-01T00:00:00Z/{scene}-10-31T23:59:59Z','limit':100}).json()['features']
        candidates=[f for f in found if f['properties'].get('sat:relative_orbit')==166 and f['properties'].get('sat:orbit_state')=='descending' and {'vv','vh'}<=f['assets'].keys()]
        candidates.sort(key=lambda f:abs(int(f['properties']['datetime'][8:10])-19))
        for picked in candidates:
            acquired=picked['properties']['datetime'][:10];item=picked['id'];collection='sentinel-1-rtc'
            vv,vh=bands(bbox,collection,item,['vv','vh'])
            good=np.isfinite(vv)&np.isfinite(vh)&(vv>0)&(vh>0)
            if good.sum()>=30:break
        else:return site,kind,None
        values={k+'_mean':float(np.mean(10*np.log10(v[good]))) for k,v in [('VV',vv),('VH',vh)]}
        values.update(VV_count=int(good.sum()),VH_count=int(good.sum()),orbit=166)
    else:
        collection='sentinel-2-l2a'
        if site=='frond' or period:
            year=period[:4] if period else scene['date'][:4]
            found=get('/stac/v1/search',{'collections':collection,'bbox':','.join(map(str,bbox)),
                 'datetime':interval if period else f'{year}-10-01T00:00:00Z/{year}-10-31T23:59:59Z','limit':100}).json()['features']
            found.sort(key=lambda f:(f['properties'].get('eo:cloud_cover',100),f['id']))
            for picked in found:
                if not {'B04','B08','SCL'} <= picked['assets'].keys():continue
                if picked['properties'].get('s2:nodata_pixel_percentage',0)>=70:continue
                acquired=picked['properties']['datetime'][:10];item=picked['id']
                red,nir,scl=bands(bbox,collection,item,['B04','B08','SCL'])
                if (np.isin(scl,[4,5,6,7])&(red>0)&(nir>0)).sum()>=30:break
            else:return site,kind,None
        else:
            acquired=scene['date'];item=scene['scene']
            red,nir,scl=bands(bbox,collection,item,['B04','B08','SCL'])
        # The Planetary Computer Sentinel-2 L2A COGs retain original processing baselines.
        meta=get(f'/stac/v1/collections/{collection}/items/{item}').json()
        props=meta['properties']
        declared=meta['assets']['B04'].get('raster:bands',[{}])[0].get('offset')
        if declared is not None and declared not in (0,-0.1,-1000):raise ValueError(f'Unexpected reflectance offset {declared}')
        if declared is not None:
            offset=1000 if declared in (-0.1,-1000) else 0
        else:
            offset=1000 if float(props.get('s2:processing_baseline','0'))>=4 else 0
        denom=nir+red-2*offset
        good=np.isin(scl,[4,5,6,7])&(red>0)&(nir>0)&(denom>0)
        if good.sum()<30:return site,kind,None
        ndvi=(nir[good]-red[good])/denom[good]
        ndvi=ndvi[np.isfinite(ndvi)&(np.abs(ndvi)<=1)]
        if ndvi.size<30:return site,kind,None
        values={'NDVI_mean':float(ndvi.mean()),'NDVI_count':int(ndvi.size)}
        if period:
            grid=np.full(red.shape,np.nan)
            grid[good]=(nir[good]-red[good])/denom[good]
            values['NDVI_grid']=[[round(float(v),5) if math.isfinite(v) and abs(v)<=1 else None for v in row] for row in grid]
    values.update(date=acquired,month=acquired[:7],image_count=1,scene=item,source=f'{API}/stac/v1/collections/{collection}/items/{item}',bbox=list(bbox),site_id=site)
    return site,kind,values

if __name__=='__main__':
    tasks=[(site,kind,s) for site in SITES for kind,scenes in [('radar',range(2018,2027)),('optical',[f['properties'] for f in SCENES])] for s in scenes]
    monthly='--village-monthly' in sys.argv
    if monthly:
        periods=[f'{y:04d}-{m:02d}' for y in range(2021,2027) for m in range(1,13)
                 if '2021-11'<=f'{y:04d}-{m:02d}'<='2026-10']
        tasks=[('village',kind,m) for kind in ('radar','optical') for m in periods]
    result={site:{kind:[] for kind in ('radar','optical')} for site in (('village',) if monthly else SITES)}
    failures=[]
    with cf.ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(sample,task):task for task in tasks}
        for future in cf.as_completed(futures):
            try:
                site,kind,row=future.result()
                if row is not None:result[site][kind].append(row)
            except Exception as e:
                site,kind,scene=futures[future]
                failures.append({'site':site,'kind':kind,'period':str(scene if isinstance(scene,(int,str)) else scene['date']),'error':str(e)[:240]})
    for site,kinds in result.items():
        for values in kinds.values():values.sort(key=lambda v:v['date'])
        print(site,{k:len(v) for k,v in kinds.items()},flush=True)
    out=ROOT/('sentinel-village-monthly-2026-11-16.json' if monthly else 'sentinel-panel-sampled-2026-11-16.json')
    out.write_text(json.dumps({'sites':result,'errors':failures},indent=2))
    print('Errors',len(failures),flush=True)
