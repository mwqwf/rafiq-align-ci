// ⚖️ الحكمُ بالتغذية القسريّة (teacher-forced) في whisper — البند (3-أ) من خطّة الحَكَم · قياسٌ فقط، لا يُشحن.
//
// منقّحٌ من النموذج الأوّليّ fscore.cpp. الفكرة: لا ننتظر أن «يكتب» whisper الخطأ؛ نسأله مباشرةً:
// «ما احتمالُ رموزِ الكلمةِ المتوقَّعة هنا، إذا كان ما قبلها هو النصَّ المتوقَّع؟». كلمةٌ لم تُقرأ
// (أو قُرئت غيرَها) احتمالُها منخفض ولو كتب التفريغُ الحرُّ صورتَها الصحيحة.
//
// ما تغيّر عن النموذج الأوّليّ:
//  1) **الترميزُ (BPE) صار في بايثون** بترتيب tiktoken بعينه (تقطيعٌ مسبقٌ بنمط gpt2 ثمّ دمجٌ بالرتبة =
//     رقم الرمز)، وهنا لا يُستقبل إلا أرقامُ رموزٍ جاهزة — فلا BPE مرتجلٌ على الكلمة كلّها.
//  2) **الرجوعُ في KV صريح**: whisper_decode(n_past) يمحو خلايا KV من n_past فصاعداً (whisper.cpp
//     c4ac0012 · whisper_decode_with_state ⇐ whisper_kv_cache_seq_rm)، فتُجرَّب الصورُ من الموضع نفسِه.
//  3) **اللوجتاتُ عند (n-1)*n_vocab**: whisper.cpp لا يحسب إلا لوجتات آخر رمزٍ في الدفعة.
//  4) **إعادةُ المزامنة (--resync TAU)** — علاجُ خطر الموضع +2: إذا كانت درجةُ الكلمة السابقة < TAU
//     تُقاس الكلمةُ الحاليّة في سياقين (بالسابقة · بدونها) ويُلزَم الأفضل؛ فإن غلب «بدونها» سقطت
//     السابقةُ من السياق نهائيّاً — كي لا تُحاكَم الكلماتُ التالية على سياقٍ لم يُقرأ.
//
// الاستعمال:
//   forced_judge MODEL vocab                  ⇒ "id<TAB>hex" لكل رمزٍ نصّيٍّ (id < eot)
//   forced_judge MODEL score [--threads N] [--free LANG] [--resync TAU]
//     stdin: id<TAB>f32path<TAB>lang<TAB>slot0<TAB>slot1…   (slot = صورٌ مفصولةٌ بـ| · الصورة = أرقامٌ مفصولةٌ بفواصل)
//     stdout: {"id":…,"w":[[n,sum,margin,minmargin,rank0,variant,skip]|null …],"eot":…[,"hyp":…,"htok":[…]]}
#include "whisper.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

static std::vector<float> readf32(const std::string &p) {
    std::vector<float> v;
    FILE *f = fopen(p.c_str(), "rb");
    if (!f) return v;
    fseek(f, 0, SEEK_END);
    long n = ftell(f) / 4;
    fseek(f, 0, SEEK_SET);
    v.resize(n);
    if (fread(v.data(), 4, n, f) != (size_t)n) v.clear();
    fclose(f);
    return v;
}

static void esc(std::string &o, const std::string &s) {
    for (char c : s) {
        if (c == '"' || c == '\\') { o += '\\'; o += c; }
        else if (c == '\n' || c == '\r' || c == '\t') o += ' ';
        else o += c;
    }
}

static std::vector<std::string> split(const std::string &s, char d) {
    std::vector<std::string> out;
    std::string cur;
    for (char c : s) {
        if (c == d) { out.push_back(cur); cur.clear(); }
        else cur += c;
    }
    out.push_back(cur);
    return out;
}

struct Best {
    bool ok = false;
    double sum = -1e30, margin = 0;
    float minm = 0;
    int rank0 = 0, vi = -1;
    std::vector<whisper_token> tk;
};

static whisper_context *ctx;
static int nv, eot, th = 4;

// لوغاريتمُ softmax على الرموز النصّيّة + eot (الرموزُ الخاصّة والطوابع تُحجب كما في النموذج الأوّليّ).
static void lsm_from(const float *lg, std::vector<float> &lp) {
    lp.assign(lg, lg + nv);
    for (int k = eot + 1; k < nv; k++) lp[k] = -INFINITY;
    float m = *std::max_element(lp.begin(), lp.end());
    double s = 0;
    for (float x : lp) s += std::exp(x - m);
    float l = m + (float)std::log(s);
    for (auto &x : lp) x -= l;
}

static bool decode(const whisper_token *t, int n, int n_past, std::vector<float> &lp) {
    if (whisper_decode(ctx, t, n, n_past, th) != 0) return false;
    lsm_from(whisper_get_logits(ctx) + (size_t)(n - 1) * nv, lp);
    return true;
}

// يقيس كلَّ صورةٍ من السياق (L0 عند الموضع np0) ويعيد أفضلها بمجموع log p.
// ⚡ مشاركةُ البادئة: تُرتَّب الصورُ معجميّاً، وما اشتركت فيه صورتان متتاليتان من رموزٍ أوّليّةٍ لا يُعاد فكُّه —
// خلايا KV للبادئة ما زالت صحيحةً لأنّ الفكَّ عند الموضع p لا يمحو إلا ما بعده (whisper_kv_cache_seq_rm).
// Ls[j] = توزيعُ الرمز j بعد البادئة tk[0..j-1]؛ صالحٌ لـ j ≤ عددِ ما فُكّ من الصورة السابقة.
static Best score_word(const std::vector<float> &L0, int np0, const std::vector<std::vector<whisper_token>> &vars) {
    Best b;
    std::vector<size_t> order;
    for (size_t v = 0; v < vars.size(); v++) {
        bool bad = vars[v].empty();
        for (auto t : vars[v]) if (t < 0 || t >= eot) bad = true;
        if (!bad) order.push_back(v);
    }
    std::sort(order.begin(), order.end(), [&](size_t a, size_t c) { return vars[a] < vars[c]; });
    std::vector<std::vector<float>> Ls(1, L0);
    std::vector<whisper_token> prev;   // رموزُ الصورة السابقة
    int valid = 0;                     // Ls[0..valid] صالحة
    for (size_t v : order) {
        const auto &tk = vars[v];
        int n = (int)tk.size();
        int c = 0;
        while (c < (int)prev.size() && c < n && prev[c] == tk[c]) c++;
        int keep = std::min(c, valid);
        valid = keep;
        bool bad = false;
        double sum = 0, summ = 0;
        float minm = 0;
        int rk0 = 0;
        for (int j = 0; j < n; j++) {
            if (j > valid) {   // Ls[j] غيرُ صالحة: فكُّ tk[j-1] عند موضعه
                if ((int)Ls.size() <= j) Ls.resize(j + 1);
                if (!decode(&tk[j - 1], 1, np0 + j - 1, Ls[j])) { bad = true; break; }
                valid = j;
            }
            const auto &L = Ls[j];
            float f = L[tk[j]];
            float mx = *std::max_element(L.begin(), L.end());
            if (j == 0) for (int k = 0; k < nv; k++) if (L[k] > f) rk0++;
            sum += f;
            summ += f - mx;
            minm = std::min(minm, f - mx);
        }
        prev = tk;
        if (bad) { valid = 0; continue; }
        if (sum > b.sum) { b.ok = true; b.sum = sum; b.margin = summ; b.minm = minm; b.rank0 = rk0; b.vi = (int)v; b.tk = tk; }
    }
    return b;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: forced_judge MODEL vocab|score [--threads N] [--free LANG] [--resync TAU]\n"); return 2; }
    std::string mode = argv[2], free_lang;
    bool resync = false;
    double tau = 0;
    for (int i = 3; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--threads" && i + 1 < argc) th = atoi(argv[++i]);
        else if (a == "--free" && i + 1 < argc) free_lang = argv[++i];
        else if (a == "--resync" && i + 1 < argc) { resync = true; tau = atof(argv[++i]); }
        else { fprintf(stderr, "معاملٌ غير معروف: %s\n", a.c_str()); return 2; }
    }
    auto cp = whisper_context_default_params();
    cp.use_gpu = false;
    ctx = whisper_init_from_file_with_params(argv[1], cp);
    if (!ctx) { fprintf(stderr, "⛔ تعذّر تحميلُ النموذج %s\n", argv[1]); return 1; }
    nv = whisper_n_vocab(ctx);
    eot = whisper_token_eot(ctx);

    if (mode == "vocab") {
        for (int i = 0; i < eot; i++) {
            const char *s = whisper_token_to_str(ctx, i);
            std::string h;
            char b[4];
            for (const unsigned char *p = (const unsigned char *)s; *p; p++) { snprintf(b, 4, "%02x", *p); h += b; }
            printf("%d\t%s\n", i, h.c_str());
        }
        whisper_free(ctx);
        return 0;
    }

    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        auto f = split(line, '\t');
        if (f.size() < 3) { fprintf(stderr, "سطرٌ ناقص\n"); continue; }
        const std::string id = f[0], wav = f[1], lang = f[2];
        auto pcm = readf32(wav);
        std::string out = "{\"id\":\"";
        esc(out, id);
        out += "\"";
        if (pcm.empty() || whisper_pcm_to_mel(ctx, pcm.data(), (int)pcm.size(), th) || whisper_encode(ctx, 0, th)) {
            out += ",\"error\":\"encode\"}";
            std::cout << out << std::endl;
            continue;
        }
        int lid = whisper_lang_id(lang.c_str());
        std::vector<whisper_token> pr = {whisper_token_sot(ctx), whisper_token_lang(ctx, lid < 0 ? 0 : lid),
                                         whisper_token_transcribe(ctx), whisper_token_not(ctx)};
        std::vector<float> cur;
        if (!decode(pr.data(), (int)pr.size(), 0, cur)) { out += ",\"error\":\"prompt\"}"; std::cout << out << std::endl; continue; }
        int np = (int)pr.size();
        // حالةُ الكلمة السابقة المُلزَمة (لإعادة المزامنة)
        bool have_prev = false, prev_low = false;
        int prev_np = 0;
        std::vector<float> prev_ctx;
        std::vector<whisper_token> prev_tk;
        out += ",\"w\":[";
        bool failed = false;
        for (size_t s = 3; s < f.size(); s++) {
            if (s > 3) out += ",";
            std::vector<std::vector<whisper_token>> vars;
            for (auto &v : split(f[s], '|')) {
                if (v.empty()) continue;
                std::vector<whisper_token> tk;
                for (auto &t : split(v, ',')) if (!t.empty()) tk.push_back(atoi(t.c_str()));
                vars.push_back(tk);
            }
            Best A = score_word(cur, np, vars);
            if (!A.ok) { out += "null"; prev_low = false; continue; }
            int skip = 0;
            Best W = A;
            int np0 = np;
            std::vector<float> ctx0 = cur;
            if (resync && have_prev && prev_low) {
                Best B = score_word(prev_ctx, prev_np, vars);   // يمحو KV السابقة من prev_np فصاعداً
                if (B.ok && B.sum > A.sum) {
                    skip = 1; W = B; np0 = prev_np; ctx0 = prev_ctx;
                } else {
                    // غلب السياقُ الكامل: تُعاد الكلمةُ السابقة إلى KV كما كانت
                    std::vector<float> tmp;
                    if (!decode(prev_tk.data(), (int)prev_tk.size(), prev_np, tmp)) { failed = true; break; }
                }
            }
            if (!decode(W.tk.data(), (int)W.tk.size(), np0, cur)) { failed = true; break; }
            np = np0 + (int)W.tk.size();
            have_prev = true;
            prev_low = W.sum < tau;
            prev_np = np0;
            prev_ctx.swap(ctx0);
            prev_tk = W.tk;
            char b[200];
            snprintf(b, sizeof b, "[%d,%.4f,%.4f,%.4f,%d,%d,%d]", (int)W.tk.size(), W.sum, W.margin, W.minm, W.rank0, W.vi, skip);
            out += b;
        }
        out += "]";
        if (failed) { out += ",\"error\":\"decode\"}"; std::cout << out << std::endl; continue; }
        char b[64];
        snprintf(b, sizeof b, ",\"eot\":%.4f", cur[eot]);
        out += b;
        if (!free_lang.empty()) {
            auto p = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
            p.language = free_lang.c_str();
            p.n_threads = th;
            p.no_context = true;
            p.print_progress = p.print_realtime = p.print_timestamps = false;
            p.print_special = false;
            std::string h, ht;
            if (whisper_full(ctx, p, pcm.data(), (int)pcm.size()) == 0) {
                bool f1 = true;
                for (int i = 0; i < whisper_full_n_segments(ctx); i++) {
                    h += whisper_full_get_segment_text(ctx, i);
                    for (int j = 0; j < whisper_full_n_tokens(ctx, i); j++) {
                        int t = whisper_full_get_token_id(ctx, i, j);
                        if (t < eot) { ht += (f1 ? "" : ",") + std::to_string(t); f1 = false; }
                    }
                }
            }
            out += ",\"hyp\":\"";
            esc(out, h);
            out += "\",\"htok\":[" + ht + "]";
        }
        out += "}";
        std::cout << out << std::endl;
    }
    whisper_free(ctx);
    return 0;
}
