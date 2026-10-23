#!/usr/bin/env python3
"""Install only SHA-pinned ffmpeg/ffprobe when the standard runner omits them."""
import hashlib,os,pathlib,platform,shutil,subprocess,sys,tarfile,tempfile,urllib.error,urllib.request
URL='https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-10-01-13-06/ffmpeg-n8.1.3-14-g330caae0c1-linux64-lgpl-8.1.tar.xz'
SHA='3c2c4d6066432b2eab54be830d3ce1f5b68a3f34ecaa6d9f2d0230a49e778560'
SIZE=137039192
BIN=pathlib.Path(__file__).resolve().parents[2]/'.qa-tools/bin'
TREE=pathlib.Path(__file__).resolve().parents[2]/'.qa-tools/apt-tree'
def apt_fallback(why):
 # (2026-10-16) BtbN autobuilds rotate: the pinned release returned 404 and every audio_qa salt failed
 # before measuring anything. Ubuntu's signed apt archive is the fallback; the pinned digest still wins when present.
 print('Pinned archive unavailable (%s); installing signed Ubuntu ffmpeg via apt'%why,flush=True)
 # (2026-10-23) مرآةُ apt المعلَّقة كانت تستهلك مهلة الخطوة كلَّها (600ث ثمّ تموت الخطوة) فتسقط بوّابة الإحصاء/المطالع بعطب بنية:
 # كلُّ أمرٍ الآن بمهلة 150ث وثلاث محاولات (المعلَّقة تُقتل وتُعاد، وغالباً تنجح الثانية)، ومهلة اتصال 20ث لكلّ طلب.
 net=['-o','Acquire::Retries=3','-o','Acquire::http::Timeout=20','-o','Acquire::https::Timeout=20']
 for cmd in (['sudo','apt-get','update','-qq']+net,
             ['sudo','apt-get','install','-y','-qq','--no-install-recommends']+net+['ffmpeg']):
  for attempt in (1,2,3):
   r=subprocess.run(['timeout','150']+cmd)
   if r.returncode==0:break
   print('apt step failed rc=%d (attempt %d/3): %s'%(r.returncode,attempt,' '.join(cmd[:3])),flush=True)
  else:raise subprocess.CalledProcessError(r.returncode,cmd)
 if not(shutil.which('ffmpeg') and shutil.which('ffprobe')):raise RuntimeError('apt fallback did not provide ffmpeg/ffprobe')
# (2026-10-23 · تسريع) مرآةُ apt المعلَّقة أسقطت ~59 مهمّةً في اليوم (≈613 دقيقة عدّاد) عند خطوة «أدوات النظام» وكلُّها تُعاد.
# فبعد أوّل تثبيتٍ ناجحٍ بـapt تُنسخ ثنائيّاتُ ffmpeg/ffprobe نفسُها (نسخةُ Ubuntu ذاتُها لا غيرُها) ومكتباتُها المشتركة
# إلى `.qa-tools/apt-tree` ليحفظها `actions/cache`، وتُستعاد في المهامّ التالية بلا شبكة apt. ⛔ لا تغيّرُ النسخةَ ولا الفكَّ:
# هي الثنائيّاتُ ذاتُها، فأحكامُ الصوت لا تتبدّل. وإن تلفت الشجرةُ أو لم تعمل أُهملت وعاد المسارُ العاديّ (apt).
SYS=('libc.so','libm.so','libdl.so','libpthread.so','librt.so','libresolv.so','libgcc_s.so','libstdc++.so','ld-linux')
def _wrap(name):
 BIN.mkdir(parents=True,exist_ok=True)
 w=BIN/name
 w.write_text('#!/bin/sh\nd="${0%%/*}/../apt-tree"\nLD_LIBRARY_PATH="$d/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" exec "$d/bin/%s.real" "$@"\n'%name)
 w.chmod(0o755)
def _add_path():
 pathfile=os.environ.get('GITHUB_PATH')
 if pathfile:
  with open(pathfile,'a') as dst:dst.write(str(BIN)+'\n')
 os.environ['PATH']=str(BIN)+os.pathsep+os.environ.get('PATH','')
def restore_tree():
 if not all((TREE/'bin'/(n+'.real')).is_file() for n in ('ffmpeg','ffprobe')):return False
 for n in ('ffmpeg','ffprobe'):_wrap(n)
 ok=all(subprocess.run([str(BIN/n),'-version'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0 for n in ('ffmpeg','ffprobe'))
 if not ok:
  print('Cached ffmpeg tree is unusable; ignoring it',flush=True)
  for n in ('ffmpeg','ffprobe'):(BIN/n).unlink(missing_ok=True)
  shutil.rmtree(TREE,ignore_errors=True)
  return False
 _add_path()
 print('Using cached ffmpeg tree (no apt)',flush=True)
 return True
def save_tree():
 try:
  if (TREE/'bin'/'ffmpeg.real').is_file():return
  tmp=TREE.with_name('apt-tree.tmp');shutil.rmtree(tmp,ignore_errors=True)
  (tmp/'bin').mkdir(parents=True);(tmp/'lib').mkdir()
  libs=set()
  for n in ('ffmpeg','ffprobe'):
   src=shutil.which(n)
   shutil.copy2(src,tmp/'bin'/(n+'.real'))
   for line in subprocess.run(['ldd',src],capture_output=True,text=True,check=True).stdout.splitlines():
    if '=>' in line and '/' in line.split('=>')[1]:
     lib=line.split('=>')[1].split()[0]
     if not any(pathlib.Path(lib).name.startswith(x) for x in SYS):libs.add(lib)
  for lib in sorted(libs):shutil.copy2(lib,tmp/'lib'/pathlib.Path(lib).name)
  shutil.rmtree(TREE,ignore_errors=True);tmp.rename(TREE)
  print('Saved ffmpeg tree for actions/cache: %d libs'%len(libs),flush=True)
 except Exception as e:print('Could not save ffmpeg tree (ignored): %s'%e,flush=True)
def main():
 if shutil.which('ffmpeg') and shutil.which('ffprobe'):print('Using existing ffmpeg and ffprobe');return
 # QA_FFMPEG_APT_ONLY=1: لسير عملٍ كان يثبّت ffmpeg بـapt حصراً (heard_gate · ctc_splice · diagnosis) فلا يتبدّل فكُّه بأرشيفٍ مثبَّت.
 if os.environ.get('QA_FFMPEG_APT_ONLY')!='1':
  try:pinned();return
  except urllib.error.HTTPError as e:
   if e.code not in (404,410):raise
   why='HTTP %d'%e.code
 else:why='apt-only'
 if restore_tree():return
 apt_fallback(why)
 save_tree()
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
