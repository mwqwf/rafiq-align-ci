# صورة فهرسة رفيق على Cloud Run Jobs.
# ⛔ لا تعدّل حرفاً من tools/alignment ولا tools/cloud ولا tools/ci_fleet —
#    تُستهلك كما هي (اتفاق الطبقة الواحدة مع github-3a و github-b9).
FROM python:3.11-slim-bookworm

ARG WHISPER_SHA=eacbd8234c6654cdbf2c377f72b2106875479bdc
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1

RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        git cmake build-essential ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# ── whisper.cpp: مثبَّت على SHA لا فرع (github-3a)، وRelease إلزاماً
#    (درس b9 المقيس: Debug أبطأ ×12). NATIVE=OFF لأن الصورة تُبنى على
#    Cloud Build وتُشغَّل على عتاد Cloud Run قد يختلف طرازه ⇒ SIGILL.
RUN mkdir -p /tmp/w && cd /tmp/w && git init -q \
    && git remote add origin https://github.com/ggml-org/whisper.cpp \
    && git fetch -q --depth 1 origin ${WHISPER_SHA} \
    && git checkout -q FETCH_HEAD \
    && cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF \
             -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON \
    && cmake --build build -j"$(nproc)" --config Release \
    && mkdir -p /opt/whisper && cp build/bin/whisper-cli /opt/whisper/ \
    && rm -rf /tmp/w

ENV ROOT=/root/QuranRafiq
# ⛔ لا استنساخ من GitHub: المستودع **خاصّ** و`gcloud builds submit` بلا اعتماد
#    — فشل البناء الأول بـ`could not read Username for github.com` (exit 128).
#    فيُنقل ما تحتاجه الحاوية من **سياق البناء**، وهو أضمن أيضاً: الصورة تحمل
#    الشجرة التي أُطلقت منها لا فرعاً بعيداً قد يسبقها أو يتخلّف عنها.
COPY tools/alignment/        ${ROOT}/tools/alignment/
COPY tools/alignment_v2/     ${ROOT}/tools/alignment_v2/
COPY tools/cloud/            ${ROOT}/tools/cloud/
COPY tools/ci_fleet/         ${ROOT}/tools/ci_fleet/
COPY core/quran/src/main/assets/quran/ ${ROOT}/core/quran/src/main/assets/quran/

# ── الموضع الذي تتوقعه العدة بالضبط. اللاحقة `.exe` اسمُ ملف لا صيغة،
#    فتعمل common.py على لينكس بلا تعديل حرف (اتفاق github-3a).
RUN mkdir -p ${ROOT}/assets-archive/ggml/bin/Release \
    && cp /opt/whisper/whisper-cli \
          ${ROOT}/assets-archive/ggml/bin/Release/whisper-cli.exe \
    && chmod +x ${ROOT}/assets-archive/ggml/bin/Release/whisper-cli.exe

# ── بيئة بايثون في المسار الذي يثبّته run_fleet.py و run_shard.sh
RUN python -m venv ${ROOT}/.venv \
    && ${ROOT}/.venv/bin/pip install --no-cache-dir -q numpy boto3

# ⛔ فخّ b9 المدفوع ثمنه: `tools/alignment_v2/` لازمة — `pipeline.py` يستورد
#    منها `refine`، وغيابها عن أربعة خوادم أسقط 228 سورة وأخرج فهارس تبدو
#    مكتملة وهي جيلٌ أول. فيُتحقق منها **وقت بناء الصورة** لا وقت التشغيل.
RUN cd ${ROOT} && .venv/bin/python -c     "import sys; sys.path.insert(0,'tools/alignment_v2'); import refine; print('✅ alignment_v2/refine حاضرة')"

# ⛔ المسار من **جذر المستودع العام** لا من مجلد الملف: سياق البناء هنا هو
#    جذر `rafiq-align-ci` (بقية أوامر COPY أعلاه تفترضه أصلاً)، فتوحيدُه
#    يمنع بناءً ينجح محلياً ويفشل في الوظيفة.
COPY tools/cloud_gcp/entrypoint.sh /entrypoint.sh
# ⛔ فخّ b9 الثاني: CRLF من ويندوز يكسر سكربتات bash المنقولة بصمت.
RUN sed -i 's/
$//' /entrypoint.sh && chmod +x /entrypoint.sh     && bash -n /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
