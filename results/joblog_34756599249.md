# 🪵 قراءةُ سجلِّ الشوط 34756599249 (‏بالوكالة)

- سُحب في: 2026-09-13T13:25:18Z · بالشوط 34759781198 · رمزُ الخروج: `0`
- ⛔ أثرٌ تشخيصيٌّ لا قياس: لا رقمَ منه يدخل اللوحة.

## أثرُ السحب
```
+ API=https://api.github.com/repos/mwqwf/rafiq-align-ci/actions/runs/34756599249
+ curl -sS -H 'Authorization: Bearer ghs_15368_eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRobmQiLCJjdHgiOiJXeGM4UTZxdmlDTE9vbWQ4U1QweWYzREQ1dlBrVXR1UndfQnB2UzdEVWtySmtFR2NtOHlHUk40IiwiZXhwIjoxNzg5MzA5NTA1LCJpYXQiOjE3ODkzMDU5MDUsImlzcyI6ImdpdGh1YiIsImp0aSI6IjcxZjIwNjBjLWNiYTgtNDYwNC1hNTgzLWY5N2M0YmRhYWUyOCIsInZlciI6M30.yLnwyzn1ZVrFLXoAq7qFYbJFkRIrWhgtFZF8yqKPMXG8oLoDLssv246UQ2ozC7bHtvmu6v6w2aJRfMb3zmPNFw' https://api.github.com/repos/mwqwf/rafiq-align-ci/actions/runs/34756599249 -o run.json -w 'الحالة=%{http_code}\n'
الحالة=200
+ head -c 300 run.json
{
  "id": 34756599249,
  "name": "sets-build",
  "node_id": "WFR_kwLOULeDOc8AAAAIF6ed0Q",
  "head_branch": "main",
  "head_sha": "6c54068fda66a1b83c8d383e89b75e8b2063532c",
  "path": ".github/workflows/sets-build.yml",
  "display_title": "ci(sets-build): 🧱 تحقّقُ بناء مجموعات ا�+ echo

++ curl -sS -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer ghs_15368_eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRobmQiLCJjdHgiOiJXeGM4UTZxdmlDTE9vbWQ4U1QweWYzREQ1dlBrVXR1UndfQnB2UzdEVWtySmtFR2NtOHlHUk40IiwiZXhwIjoxNzg5MzA5NTA1LCJpYXQiOjE3ODkzMDU5MDUsImlzcyI6ImdpdGh1YiIsImp0aSI6IjcxZjIwNjBjLWNiYTgtNDYwNC1hNTgzLWY5N2M0YmRhYWUyOCIsInZlciI6M30.yLnwyzn1ZVrFLXoAq7qFYbJFkRIrWhgtFZF8yqKPMXG8oLoDLssv246UQ2ozC7bHtvmu6v6w2aJRfMb3zmPNFw' https://api.github.com/repos/mwqwf/rafiq-align-ci/actions/runs/34756599249/logs
+ CODE=302
++ curl -sS -o /dev/null -w '%{redirect_url}' -H 'Authorization: Bearer ghs_15368_eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRobmQiLCJjdHgiOiJXeGM4UTZxdmlDTE9vbWQ4U1QweWYzREQ1dlBrVXR1UndfQnB2UzdEVWtySmtFR2NtOHlHUk40IiwiZXhwIjoxNzg5MzA5NTA1LCJpYXQiOjE3ODkzMDU5MDUsImlzcyI6ImdpdGh1YiIsImp0aSI6IjcxZjIwNjBjLWNiYTgtNDYwNC1hNTgzLWY5N2M0YmRhYWUyOCIsInZlciI6M30.yLnwyzn1ZVrFLXoAq7qFYbJFkRIrWhgtFZF8yqKPMXG8oLoDLssv246UQ2ozC7bHtvmu6v6w2aJRfMb3zmPNFw' https://api.github.com/repos/mwqwf/rafiq-align-ci/actions/runs/34756599249/logs
+ URL='https://results-receiver.actions.githubusercontent.com/rest/runs/9f6a3120-bf97-464d-98e5-c13067950acc/logs?filename=logs_94133016222.zip&signature=1789305917.765b50759fac1b0c8a2a3fc6b4b0260ac45f299a40b173e5bab2435aa7fbaad6'
+ echo 'نقطةُ السجلّ: 302 · طولُ عنوان التحويل: 222'
نقطةُ السجلّ: 302 · طولُ عنوان التحويل: 222
+ '[' -n 'https://results-receiver.actions.githubusercontent.com/rest/runs/9f6a3120-bf97-464d-98e5-c13067950acc/logs?filename=logs_94133016222.zip&signature=1789305917.765b50759fac1b0c8a2a3fc6b4b0260ac45f299a40b173e5bab2435aa7fbaad6' ']'
+ curl -sS -o logs.zip -w 'تنزيلُ الأرشيف=%{http_code} حجمٌ=%{size_download}\n' 'https://results-receiver.actions.githubusercontent.com/rest/runs/9f6a3120-bf97-464d-98e5-c13067950acc/logs?filename=logs_94133016222.zip&signature=1789305917.765b50759fac1b0c8a2a3fc6b4b0260ac45f299a40b173e5bab2435aa7fbaad6'
تنزيلُ الأرشيف=200 حجمٌ=7344
+ ls -l logs.zip
-rw-r--r-- 1 runner runner 7344 Sep 13 13:25 logs.zip
+ mkdir -p logdir
+ cd logdir
+ unzip -o -q ../logs.zip
++ find logdir -name '*.txt'
++ wc -l
+ echo 'فُكّ 2 ملفّاً'
فُكّ 2 ملفّاً
```
## `0_build.txt`
```
2026-09-13T12:16:13.7455360Z [36;1m  echo[0m
2026-09-13T12:16:13.7455603Z [36;1m  echo '```'[0m
2026-09-13T12:16:13.7455833Z [36;1m  tail -60 "$M"[0m
2026-09-13T12:16:13.7456056Z [36;1m  echo '```'[0m
2026-09-13T12:16:13.7456262Z [36;1m} > "$OUT"[0m
2026-09-13T12:16:13.7456503Z [36;1mcp "$OUT" results/LATEST_sets_build.md[0m
2026-09-13T12:16:13.7456819Z [36;1mgit config user.name "rafiq-ci"[0m
2026-09-13T12:16:13.7457181Z [36;1mgit config user.email "ci@users.noreply.github.com"[0m
2026-09-13T12:16:13.7457578Z [36;1mgit add "$OUT" results/LATEST_sets_build.md[0m
2026-09-13T12:16:13.7458088Z [36;1mgit commit -q -m "results(sets-build): الشوط 34756599249 · rc=$R" || { echo "لا تغيير"; exit 0; }[0m
2026-09-13T12:16:13.7458550Z [36;1mfor i in 1 2 3; do[0m
2026-09-13T12:16:13.7459087Z [36;1m  git fetch -q origin main && git merge -q --no-edit origin/main && git push -q origin HEAD:main && { echo "✅ أُودع $OUT"; exit 0; }[0m
2026-09-13T12:16:13.7459673Z [36;1m  echo "↻ محاولةٌ $i"; sleep 5[0m
2026-09-13T12:16:13.7459937Z [36;1mdone[0m
2026-09-13T12:16:13.7460158Z [36;1mecho "⛔ تعذّر الدفع"; exit 1[0m
2026-09-13T12:16:13.7495372Z shell: /usr/bin/bash -e {0}
2026-09-13T12:16:13.7495643Z env:
2026-09-13T12:16:13.7495927Z   pythonLocation: /opt/hostedtoolcache/Python/3.11.16/x64
2026-09-13T12:16:13.7496381Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.11.16/x64/lib/pkgconfig
2026-09-13T12:16:13.7496826Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.11.16/x64
2026-09-13T12:16:13.7497387Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.11.16/x64
2026-09-13T12:16:13.7497784Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.11.16/x64
2026-09-13T12:16:13.7498180Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.11.16/x64/lib
2026-09-13T12:16:13.7498546Z   SETS: wav g2/noise-fan-5 g3r/clean g3r/noisy
2026-09-13T12:16:13.7498832Z ##[endgroup]
2026-09-13T12:16:13.7570368Z ⛔ لا أثرَ
2026-09-13T12:16:13.7573657Z ##[error]Process completed with exit code 1.
2026-09-13T12:16:13.7604041Z ##[group]Run R=$(cat tools/tasmi_bench/work_sets/rc.txt 2>/dev/null || echo 1)
2026-09-13T12:16:13.7604622Z [36;1mR=$(cat tools/tasmi_bench/work_sets/rc.txt 2>/dev/null || echo 1)[0m
2026-09-13T12:16:13.7605136Z [36;1m[ "$R" = "0" ] || { echo "⛔ سقط البناءُ برمزٍ $R — والأثرُ مودَعٌ في results/"; exit 1; }[0m
2026-09-13T12:16:13.7605558Z [36;1mecho "✅ المجموعاتُ تُبنى كاملةً"[0m
2026-09-13T12:16:13.7640844Z shell: /usr/bin/bash -e {0}
2026-09-13T12:16:13.7641111Z env:
2026-09-13T12:16:13.7641391Z   pythonLocation: /opt/hostedtoolcache/Python/3.11.16/x64
2026-09-13T12:16:13.7641848Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.11.16/x64/lib/pkgconfig
2026-09-13T12:16:13.7642314Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.11.16/x64
2026-09-13T12:16:13.7642700Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.11.16/x64
2026-09-13T12:16:13.7643087Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.11.16/x64
2026-09-13T12:16:13.7643735Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.11.16/x64/lib
2026-09-13T12:16:13.7644094Z   SETS: wav g2/noise-fan-5 g3r/clean g3r/noisy
2026-09-13T12:16:13.7644386Z ##[endgroup]
2026-09-13T12:16:13.7715902Z ⛔ سقط البناءُ برمزٍ 1 — والأثرُ مودَعٌ في results/
2026-09-13T12:16:13.7718753Z ##[error]Process completed with exit code 1.
2026-09-13T12:16:13.7849124Z Node 20 is being deprecated. This workflow is running with Node 24 by default. If you need to temporarily use Node 20, you can set the ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true environment variable. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
2026-09-13T12:16:13.7850427Z Post job cleanup.
2026-09-13T12:16:13.8732185Z [command]/usr/bin/git version
2026-09-13T12:16:13.8777395Z git version 2.55.0
2026-09-13T12:16:13.8876569Z Temporarily overriding HOME='/home/runner/work/_temp/b5292697-b04f-46c5-be20-4f076785d46e' before making global git config changes
2026-09-13T12:16:13.8878073Z Adding repository directory to the temporary git global config as a safe directory
2026-09-13T12:16:13.8881201Z [command]/usr/bin/git config --global --add safe.directory /home/runner/work/rafiq-align-ci/rafiq-align-ci
2026-09-13T12:16:13.8900140Z [command]/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
2026-09-13T12:16:13.8943642Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
2026-09-13T12:16:13.9211583Z [command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
2026-09-13T12:16:13.9245639Z http.https://github.com/.extraheader
2026-09-13T12:16:13.9258730Z [command]/usr/bin/git config --local --unset-all http.https://github.com/.extraheader
2026-09-13T12:16:13.9299688Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
2026-09-13T12:16:13.9582597Z [command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
2026-09-13T12:16:13.9624283Z [command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
2026-09-13T12:16:14.0025088Z Cleaning up orphan processes
2026-09-13T12:16:14.0393648Z ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/checkout@v4, actions/setup-python@v5. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
```

## `build/system.txt`
```
2026-09-13T12:15:32.3420000Z Job is waiting for a hosted runner to come online.
2026-09-13T12:15:32.3420000Z Job is about to start running on the hosted runner: GitHub Actions 1000010361
2026-09-13T12:15:32.3320000Z Evaluating build.if
2026-09-13T12:15:32.3320000Z Evaluating: success()
2026-09-13T12:15:32.3320000Z Result: true
2026-09-13T12:15:32.3360000Z Requested labels: ubuntu-latest
2026-09-13T12:15:32.3360000Z Job defined at: mwqwf/rafiq-align-ci/.github/workflows/sets-build.yml@refs/heads/main
2026-09-13T12:15:32.3360000Z Waiting for a runner to pick up this job...```

