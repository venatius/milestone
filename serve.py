"""Serve only Milestone demo deliverables on loopback."""
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import unquote,urlsplit
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parent
ALLOWED={'google-earth-before-2022-02-25.png','google-earth-after-2026-06-07.png','google-earth-history-provenance.json','community-context-2018.png','community-context-2022.png','community-context-2026.png','demo.html','weekly-report-2026-10-28.html','registry-evidence.json','earthengine-demo.js','earthengine-exploratory.js','earthengine-verdes-candidate.js','earthengine-orchid-control-candidate.js','radar-exploratory-2026-10-28.json','radar-verdes-candidate-2026-10-28.json','radar-orchid-control-candidate-2026-10-28.json','optical-2018.png','optical-2022.png','optical-2026.png','verdes-candidate-2026.png','orchid-candidate-2026.png','demo-preview.png'}
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
 def send_head(self):
  name=unquote(urlsplit(self.path).path).lstrip('/') or 'demo.html'
  report=name.startswith('Milestone_Weekly_Progress_') and name.endswith('.pdf') and '/' not in name and '\\' not in name
  if name not in ALLOWED and not report:
   self.send_error(404);return None
  self.path='/'+name
  return super().send_head()
 def end_headers(self):
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Cache-Control','no-store')
  super().end_headers()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=4861);a=p.parse_args()
 ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
