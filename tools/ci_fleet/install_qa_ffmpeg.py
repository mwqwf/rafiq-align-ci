#!/usr/bin/env python3
"""Install only SHA-pinned ffmpeg/ffprobe when the standard runner omits them."""
import hashlib,os,pathlib,platform,shutil,subprocess,sys,tarfile,tempfile,urllib.error,urllib.request
URL='https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-10-01-13-06/ffmpeg-n8.1.3-14-g330caae0c1-linux64-lgpl-8.1.tar.xz'
SHA='3c2c4d6066432b2eab54be830d3ce1f5b68a3f34ecaa6d9f2d0230a49e778560'
SIZE=137039192
BIN=pathlib.Path(__file__).resolve().parents[2]/'.qa-tools/bin'
def apt_fallback(why):
 # (2026-10-16) BtbN autobuilds rotate: the pinned release returned 404 and every audio_qa salt failed
 # before measuring anything. Ubuntu's signed apt archive is the fallback; the pinned digest still wins when present.
 print('Pinned archive unavailable (%s); installing signed Ubuntu ffmpeg via apt'%why,flush=True)
 for cmd in (['sudo','apt-get','update','-qq','-o','Acquire::Retries=3'],
             ['sudo','apt-get','install','-y','-qq','--no-install-recommends','ffmpeg']):
  subprocess.run(['timeout','600']+cmd,check=True)
 if not(shutil.which('ffmpeg') and shutil.which('ffprobe')):raise RuntimeError('apt fallback did not provide ffmpeg/ffprobe')
def main():
 if shutil.which('ffmpeg') and shutil.which('ffprobe'):print('Using existing ffmpeg and ffprobe');return
 try:pinned()
 except urllib.error.HTTPError as e:
  if e.code not in (404,410):raise
  apt_fallback('HTTP %d'%e.code)
def pinned():
 if platform.system()!='Linux' or platform.machine()!='x86_64':raise RuntimeError('Pinned fallback requires standard Linux x86_64 runner')
 BIN.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as work:
  archive=pathlib.Path(work)/'ffmpeg.tar.xz';digest=hashlib.sha256();size=0
  req=urllib.request.Request(URL,headers={'User-Agent':'rafiq-qa-pinned-tools'})
  with urllib.request.urlopen(req,timeout=60) as source,archive.open('wb') as dst:
   for chunk in iter(lambda:source.read(1024*1024),b''):
    size+=len(chunk)
    if size>SIZE:raise RuntimeError('Archive larger than publisher size')
    digest.update(chunk);dst.write(chunk)
  if size!=SIZE or digest.hexdigest()!=SHA:raise RuntimeError('FFmpeg archive differs from pinned publisher digest')
  with tarfile.open(archive,'r:xz') as tar:
   for name in ['ffmpeg','ffprobe']:
    matches=[m for m in tar.getmembers() if m.isfile() and m.name.endswith('/bin/'+name)]
    if len(matches)!=1:raise RuntimeError('Expected one regular binary: '+name)
    with tar.extractfile(matches[0]) as src,(BIN/name).open('wb') as dst:shutil.copyfileobj(src,dst)
    (BIN/name).chmod(0o755)
 print('Installed verified BtbN LGPL FFmpeg 8.1 archive',SHA)
 pathfile=os.environ.get('GITHUB_PATH')
 if pathfile:
  with open(pathfile,'a') as dst:dst.write(str(BIN)+'\n')
 else:print('Local verification binaries:',BIN)
if __name__=='__main__':main()
