#!/usr/bin/env bash
# 🧩 **شِبْهُ ترويسات أندرويد لفحص `jni.c` نحواً** — بلا NDK وبلا gradle، في ثوانٍ.
#
# ⛔ **لِمَ وُجد** (‏2026-09-14 · دورةُ :50): `jni.c` كان **يُودَع بلا ترجمةٍ أصلاً** —
# `engine-test` يبني كوتلن وحدَها ⇒ حرفٌ مخطوءٌ في اسم حقلٍ من `whisper_full_params`
# يمرّ أخضرَ حتى أوّل بناءِ APK. وهذه الترويساتُ تُكمل ما تحتاجه الترجمةُ **النحويّة**.
#
# ⚠️ **وحدُّها يُقال:** هذه **مُشابَهةٌ** لا ترويسات NDK. الهدفُ: **النحوُ والأنواعُ وحقولُ
# `whisper`**. ⇒ **ولا يُبنى منها شيءٌ يُشحن**، ولا تُقرأ شهادتُها «بناءً كاملاً».
# ⭐ **والاتّجاهُ آمن:** رمزٌ أندرويديٌّ يستعمله الجسرُ وليس هنا ⇒ **يسقط الفحصُ** (يصرخ ولا يسكت)،
# وعلاجُه أن يُضاف هنا بنصِّ تعريفه من مستند NDK لا أن يُخفَّف الفحص.
#
# الاستعمال: bash tools/tasmi_bench/jni_stubs.sh <مجلدُ android/>
set -euo pipefail
DIR="${1:?⛔ مجلدُ الوجهة (مثل ck/inc/android) مطلوب}"
mkdir -p "$DIR"

cat > "$DIR/log.h" <<'H'
#ifndef ANDROID_LOG_STUB_H
#define ANDROID_LOG_STUB_H
enum {
    ANDROID_LOG_UNKNOWN = 0, ANDROID_LOG_DEFAULT, ANDROID_LOG_VERBOSE,
    ANDROID_LOG_DEBUG, ANDROID_LOG_INFO, ANDROID_LOG_WARN,
    ANDROID_LOG_ERROR, ANDROID_LOG_FATAL, ANDROID_LOG_SILENT
};
int __android_log_print(int prio, const char *tag, const char *fmt, ...);
#endif
H

cat > "$DIR/asset_manager.h" <<'H'
#ifndef ANDROID_ASSET_MANAGER_STUB_H
#define ANDROID_ASSET_MANAGER_STUB_H
#include <stddef.h>
#include <sys/types.h>
typedef struct AAssetManager AAssetManager;
typedef struct AAssetDir AAssetDir;
typedef struct AAsset AAsset;
enum {
    AASSET_MODE_UNKNOWN = 0, AASSET_MODE_RANDOM = 1,
    AASSET_MODE_STREAMING = 2, AASSET_MODE_BUFFER = 3
};
AAsset *AAssetManager_open(AAssetManager *mgr, const char *filename, int mode);
int AAsset_read(AAsset *asset, void *buf, size_t count);
off_t AAsset_seek(AAsset *asset, off_t offset, int whence);
long long AAsset_seek64(AAsset *asset, long long offset, int whence);
void AAsset_close(AAsset *asset);
off_t AAsset_getLength(AAsset *asset);
long long AAsset_getLength64(AAsset *asset);
off_t AAsset_getRemainingLength(AAsset *asset);
long long AAsset_getRemainingLength64(AAsset *asset);
const void *AAsset_getBuffer(AAsset *asset);
int AAsset_isAllocated(AAsset *asset);
#endif
H

cat > "$DIR/asset_manager_jni.h" <<'H'
#ifndef ANDROID_ASSET_MANAGER_JNI_STUB_H
#define ANDROID_ASSET_MANAGER_JNI_STUB_H
#include <jni.h>
#include <android/asset_manager.h>
AAssetManager *AAssetManager_fromJava(JNIEnv *env, jobject assetManager);
#endif
H

echo "🧩 شِبْهُ ترويسات أندرويد في $DIR: $(ls -1 "$DIR" | tr '\n' ' ')"
