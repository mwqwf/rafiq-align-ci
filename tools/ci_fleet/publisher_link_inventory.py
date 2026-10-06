"""Bounded public HTML link discovery only; no audio, credentials, or R2 writes."""
import datetime
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import time
import urllib.parse
import source_metadata_probe as M

PAGES = (
    'https://way2quran.com/en/reciters/marwan-alakri',
    'https://www.zekr.online/mushaf/6100/mhmd-alayraoy',
    'https://www.zekr.online/dev',
)
RECOVERY_PAGES = [
  "https://way2quran.com/ar/reciters/muhammad-mahmoud-al-tablawi/hafs-an-asim",
  "https://mazameer.com/vb/threads/160994/page-3",
  "https://www.aitmaen.com/saad/",
  "https://tilawa.org/القرآن-الكريم-ورش-يوسف-بن-نوح-أحمد/"
]
DYNAMIC_PAGES = [
 'https://alkabbah.com/recitations/playlist/500375/mshf-mroan-alaakry-broay-kalon-114-sor-almshf-almrtl-kaml-bgod-aaaly-192-k-b-mroan-alaakry',
 'https://quranpedia.net/listen?recitation=356&surah=79'
]
QALUN_WARSH_PAGES = ['https://midad.com/recitation/149104', 'https://tilawa.org/' + urllib.parse.quote('القرآن-الكريم-ورش-يوسف-بن-نوح-أحمد', safe='') + '/']
DETAIL_PAGES = ['https://quranpedia.net/listen?recitation=356&surah=79']
LIMIT = 2_500_000
IRAOUI_PAGES = (
    'https://way2quran.com/en/reciters/muhammad-al-ayrawy/warsh-an-nafi-min-traiq-al-azraq',
    'https://way2quran.com/en/reciters/muhammad-al-ayrawy?recitationSlug=warsh-an-nafi',
    'https://midad.com/recitation/123515',
)


def extract(body, url):
    text = html.unescape(body.decode('utf-8', 'replace').replace('\\/', '/'))
    links = set()
    for raw in re.findall(r'''(?:https?://[^\s<>"'\\]+|(?:href|src)=["']([^"']+)["'])''', text):
        if raw:
            links.add(urllib.parse.urljoin(url, raw))
    links.update(re.findall(r'''https://[^\s<>"'\\]+''', text))
    relevant = []
    for link in sorted(links):
        parsed = urllib.parse.urlsplit(link)
        if parsed.scheme != 'https' or parsed.username or parsed.password:
            continue
        if any(word in parsed.path.lower() for word in ('.mp3', '.m4a', '/api', '6100', '.js', '/dev')):
            relevant.append(M.safe_url(link))
    scripts = re.findall(r'''<script\b[^>]*src=["']([^"']+)["']''', text, re.I)
    recitation_details = []
    for match in re.finditer(r'"recitations":(\[\{"id":356\b)', text):
        parsed, _ = json.JSONDecoder().raw_decode(text[match.start(1):])
        recitation_details.extend(r for r in parsed if r.get('id') == 356)
    return {'recitationDetails': recitation_details, 'candidateLinks': sorted(set(relevant))[:250],
            'candidateLinkCount': len(set(relevant)),
            'publicScriptUrls': [M.safe_url(urllib.parse.urljoin(url, s)) for s in scripts][:40],
            'contextLinks': [{'url': M.safe_url(urllib.parse.urljoin(url, href)), 'text': re.sub('<[^>]+>', '', label)[:240]} for href, label in re.findall(r'''<a\\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>''', text, re.I|re.S) if any(w in re.sub('<[^>]+>', '', label) for w in ('عسيري', 'العسيري', 'ابراهيم', 'إبراهيم', '054', 'القمر'))][:60],
            'dynamicAttributes': re.findall(r'''data-(?:url|src|playlist|audio|endpoint)[\\w-]*=["']([^"']+)["']''', text)[:40],
            'apiHints': [text[max(0,m.start()-80):m.end()+160] for m in re.finditer(r'''(?:500375|recitation.{0,12}356|/api/|playlist_id|audio_url)''', text)][:30],
            'title': html.unescape((re.search(r'<title>(.*?)</title>', text, re.S|re.I) or ['', ''])[1])[:300]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('original', 'iraoui', 'recovery-20261006', 'dynamic-recovery', 'quranpedia-details', 'qalun-warsh-missing'), default='original')
    args = parser.parse_args(argv)
    rows = []
    for url in (PAGES if args.profile == 'original' else IRAOUI_PAGES if args.profile == 'iraoui' else DYNAMIC_PAGES if args.profile == 'dynamic-recovery' else DETAIL_PAGES if args.profile == 'quranpedia-details' else QALUN_WARSH_PAGES if args.profile == 'qalun-warsh-missing' else RECOVERY_PAGES):
        row = {'publisherUrl': url, 'candidateOnly': True}
        try:
            deadline = time.monotonic() + 45
            with M.download_deadline(deadline):
                with M.open_response(url, deadline=deadline, opener=M.public_opener()) as response:
                    if response.status != 200 or response.headers.get('Content-Range'):
                        raise ValueError('incomplete publisher response')
                    if not any(t in response.headers.get('Content-Type', '') for t in ('text/', 'json')):
                        raise ValueError('non-text content refused')
                    data = bytearray()
                    while True:
                        block = response.read1(min(65536, LIMIT + 1 - len(data)))
                        if not block:
                            break
                        data.extend(block)
                        if len(data) > LIMIT:
                            raise ValueError('publisher page exceeds bounded size')
                    row.update(status=200, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                               **extract(bytes(data), response.geturl()))
        except Exception as exc:
            row['errorType'] = type(exc).__name__
        rows.append(row)
    report = {'atUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'audioDownloaded': False, 'productionChanged': False, 'coverageClaim': False,
              'pages': rows}
    name = ('codex-publisher-link-inventory-20261005.json' if args.profile == 'original'
            else 'codex-iraoui-publisher-links-20261005.json' if args.profile == 'iraoui'
            else 'codex-dynamic-publisher-links-20261006.json' if args.profile == 'dynamic-recovery'
            else 'codex-quranpedia-source-details-20261006.json' if args.profile == 'quranpedia-details'
            else 'codex-qalun-warsh-publisher-links-20261006.json' if args.profile == 'qalun-warsh-missing'
            else 'codex-recovery-publisher-links-20261006.json')
    dest = Path('ops/out') / name
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
