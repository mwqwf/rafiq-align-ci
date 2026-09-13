# 🧱 بناءُ مجموعات القياس · الشوط 34757386934

- التاريخ: 2026-09-13T12:35:16Z · الزناد: `push` · رمزُ الخروج: `1`
- ⛔ هذا تحقّقُ **بناءٍ** لا قياسٌ: لا رقمَ منه يدخل اللوحة.

```
عيّنةٌ: 271 بنداً
  آيات مفردة 20/211
  آيات مفردة 40/211
  آيات مفردة 60/211
  آيات مفردة 80/211
  آيات مفردة 100/211
  آيات مفردة 120/211
  آيات مفردة 140/211
  آيات مفردة 160/211
  آيات مفردة 180/211
  آيات مفردة 200/211
Traceback (most recent call last):
  File "/home/runner/work/rafiq-align-ci/rafiq-align-ci/tools/tasmi_bench/fetch_audio.py", line 96, in <module>
    main()
  File "/home/runner/work/rafiq-align-ci/rafiq-align-ci/tools/tasmi_bench/fetch_audio.py", line 74, in main
    s3, bucket = r2_client()
                 ^^^^^^^^^^^
  File "/home/runner/work/rafiq-align-ci/rafiq-align-ci/tools/tasmi_bench/fetch_audio.py", line 32, in r2_client
    c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/rafiq-align-ci/rafiq-align-ci/secure/r2_credentials.json'
```
