// 🎯 المحاذاةُ القسريّة بالاحتمالات — أداةُ قياسٍ لا تُشحن (خطوة 2-ب من خطة المستشار 2026-10-05).
//
// الفكرة: يُرمَّز الصوتُ مرّةً (whisper_encode)، ثمّ يُفكّ **قسراً** تسلسلُ رموز النصّ المتوقَّع
// (whisper_decode برمزٍ معلومٍ في كلّ خطوة)، فيُسجَّل لكلّ رمزٍ:
//   lp  = لوغاريتمُ احتمال الرمز المتوقَّع (من softmax على كلّ اللوغيتات)
//   alt = أفضلُ لوغاريتمٍ بين الرموز النصّيّة **غيرِ** المتوقَّع (البديلُ الأقوى)
//   top = أفضلُ لوغاريتمٍ بين الرموز النصّيّة كلّها (= lp إن كان المتوقَّعُ هو الأقوى)
// وبهذا تُبنى في بايثون درجةُ كلّ كلمة: متوسّطُ lp، أو هامشُ (lp − alt)، أو الفجوةُ (lp − top).
// ⛔ لا يولّد نصَّ قرآنٍ ولا يحكم: يقيس فقط احتمالَ ما قُصد عند الصوت المسموع.
//
// الاستعمال:
//   rafiq_forced -m model.bin -f audio.wav -w v1.txt [-w v2.txt ...] [-t N] [--ts] [--free]
//     v*.txt : كلمةٌ في كلّ سطر (‏UTF-8)، تُرمَّز كلٌّ منها " كلمة"؛ وكلُّ ملفٍّ صورةٌ نصّيّةٌ تُفكّ قسراً بعد الترميز الواحد.
//     --ts      : يبدأ المطالعُ برمز الزمن <|0.00|> بدل <|notimestamps|> (‏مرآةُ whisper-cli الافتراضيّ).
//     --free    : يشغّل أيضاً whisper_full بالراياتِ المشحونة (‏-l en -bs 1 -et 2.40) لقياس زمن الفكّ الحرّ.
// المخرَج: JSON في stdout (سطرٌ واحد).
#include "whisper.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

using clk = std::chrono::steady_clock;
static double ms_since(clk::time_point t0) {
    return std::chrono::duration<double, std::milli>(clk::now() - t0).count();
}

// قارئُ WAV صغيرٌ: PCM16 أو float32، أحاديّ أو متعدّد القنوات (‏يؤخذ الأوّل)، ويُشترط 16 كيلوهرتز.
static bool read_wav(const char * path, std::vector<float> & out) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    char riff[12];
    f.read(riff, 12);
    if (f.gcount() != 12 || memcmp(riff, "RIFF", 4) != 0 || memcmp(riff + 8, "WAVE", 4) != 0) return false;
    uint16_t fmt = 0, ch = 1, bits = 16;
    uint32_t sr = 16000;
    while (f) {
        char id[4];
        uint32_t sz;
        f.read(id, 4);
        f.read(reinterpret_cast<char *>(&sz), 4);
        if (!f) break;
        if (memcmp(id, "fmt ", 4) == 0) {
            std::vector<char> b(sz);
            f.read(b.data(), sz);
            memcpy(&fmt, b.data(), 2);
            memcpy(&ch, b.data() + 2, 2);
            memcpy(&sr, b.data() + 4, 4);
            memcpy(&bits, b.data() + 14, 2);
            if (fmt == 0xFFFE && sz >= 26) memcpy(&fmt, b.data() + 24, 2);   // WAVE_FORMAT_EXTENSIBLE
        } else if (memcmp(id, "data", 4) == 0) {
            if (sr != 16000 || ch < 1) { fprintf(stderr, "wav: need 16 kHz (got %u)\n", sr); return false; }
            std::vector<char> b(sz);
            f.read(b.data(), sz);
            size_t got = f.gcount();
            size_t bytes = bits / 8;
            size_t n = got / (bytes * ch);
            out.resize(n);
            for (size_t i = 0; i < n; i++) {
                const char * p = b.data() + i * bytes * ch;
                if (fmt == 3 && bits == 32) { float v; memcpy(&v, p, 4); out[i] = v; }
                else if (bits == 16) { int16_t v; memcpy(&v, p, 2); out[i] = v / 32768.0f; }
                else return false;
            }
            return true;
        } else {
            f.seekg(sz + (sz & 1), std::ios::cur);
        }
    }
    return false;
}

int main(int argc, char ** argv) {
    std::string model, wav;
    std::vector<std::string> wordsfs;   // كلُّ ملفٍّ = صورةٌ نصّيّةٌ للتسلسل نفسِه (‏يُفكّ قسراً بعد ترميزٍ واحد)
    int threads = 1;
    bool ts = false, free_run = false;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a == "-m" && i + 1 < argc) model = argv[++i];
        else if (a == "-f" && i + 1 < argc) wav = argv[++i];
        else if (a == "-w" && i + 1 < argc) wordsfs.push_back(argv[++i]);
        else if (a == "-t" && i + 1 < argc) threads = atoi(argv[++i]);
        else if (a == "--ts") ts = true;
        else if (a == "--free") free_run = true;
    }
    if (model.empty() || wav.empty() || wordsfs.empty()) { fprintf(stderr, "usage: -m model -f wav -w words [-w words2 ...] [-t N] [--ts] [--free]\n"); return 2; }

    std::vector<float> pcm;
    if (!read_wav(wav.c_str(), pcm)) { fprintf(stderr, "cannot read wav %s\n", wav.c_str()); return 3; }

    whisper_log_set([](enum ggml_log_level, const char *, void *) {}, nullptr);
    whisper_context_params cp = whisper_context_default_params();
    cp.use_gpu = false;
    whisper_context * ctx = whisper_init_from_file_with_params(model.c_str(), cp);
    if (!ctx) { fprintf(stderr, "cannot load model\n"); return 4; }

    const int nv = whisper_n_vocab(ctx);
    const int eot = whisper_token_eot(ctx);

    // ترميزٌ واحد
    auto t0 = clk::now();
    if (whisper_pcm_to_mel(ctx, pcm.data(), (int) pcm.size(), threads) != 0) { fprintf(stderr, "mel failed\n"); return 5; }
    double t_mel = ms_since(t0);
    t0 = clk::now();
    if (whisper_encode(ctx, 0, threads) != 0) { fprintf(stderr, "encode failed\n"); return 5; }
    double t_enc = ms_since(t0);

    std::vector<whisper_token> prompt = {whisper_token_sot(ctx), whisper_token_lang(ctx, whisper_lang_id("en")),
                                         whisper_token_transcribe(ctx), ts ? whisper_token_beg(ctx) : whisper_token_not(ctx)};
    std::string vout;   // مصفوفةُ الصور بصيغة JSON
    double t_forced_total = 0;
    for (size_t vi = 0; vi < wordsfs.size(); vi++) {
        std::vector<std::string> words;
        {
            std::ifstream wf(wordsfs[vi]);
            std::string line;
            while (std::getline(wf, line)) {
                while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) line.pop_back();
                if (!line.empty()) words.push_back(line);
            }
        }
        // رموزُ كلّ كلمةٍ منفصلةً (‏كلمةٌ ⇒ نطاقٌ من الرموز)
        std::vector<whisper_token> toks;
        std::vector<int> wstart, wend;
        for (const auto & w : words) {
            std::string t = " " + w;
            std::vector<whisper_token> tmp(t.size() + 8);
            int n = whisper_tokenize(ctx, t.c_str(), tmp.data(), (int) tmp.size());
            if (n < 0) { tmp.resize(-n); n = whisper_tokenize(ctx, t.c_str(), tmp.data(), (int) tmp.size()); }
            wstart.push_back((int) toks.size());
            for (int k = 0; k < n; k++) toks.push_back(tmp[k]);
            wend.push_back((int) toks.size());
        }
        // الفكُّ القسريّ: خطوةٌ لكلّ رمز (‏ذاكرةُ KV تتراكم عبر n_past)
        std::vector<double> lp(toks.size()), alt(toks.size()), top(toks.size());
        auto tf = clk::now();
        if (whisper_decode(ctx, prompt.data(), (int) prompt.size(), 0, threads) != 0) { fprintf(stderr, "decode failed\n"); return 6; }
        int n_past = (int) prompt.size();
        for (size_t i = 0; i < toks.size(); i++) {
            const float * lg = whisper_get_logits(ctx);
            // log-softmax على كلّ المفردات، والبدائلُ من الرموز النصّيّة فقط (< eot)
            float mx = -INFINITY;
            for (int j = 0; j < nv; j++) mx = std::max(mx, lg[j]);
            double z = 0;
            for (int j = 0; j < nv; j++) z += std::exp((double) lg[j] - mx);
            const double lz = mx + std::log(z);
            float best_alt = -INFINITY, best_all = -INFINITY;
            for (int j = 0; j < eot && j < nv; j++) {
                best_all = std::max(best_all, lg[j]);
                if (j != toks[i]) best_alt = std::max(best_alt, lg[j]);
            }
            lp[i] = (double) lg[toks[i]] - lz;
            alt[i] = (double) best_alt - lz;
            top[i] = (double) best_all - lz;
            if (whisper_decode(ctx, &toks[i], 1, n_past, threads) != 0) { fprintf(stderr, "decode failed\n"); return 6; }
            n_past++;
        }
        double t_forced = ms_since(tf);
        t_forced_total += t_forced;
        char buf[160];
        snprintf(buf, sizeof buf, "%s{\"forced_ms\":%.1f,\"n_tokens\":%zu,\"words\":[", vi ? "," : "", t_forced, toks.size());
        vout += buf;
        auto arr = [&](const std::vector<double> & v, int a, int b) {
            std::string r = "[";
            for (int k = a; k < b; k++) { snprintf(buf, sizeof buf, "%s%.4f", k > a ? "," : "", v[k]); r += buf; }
            return r + "]";
        };
        for (size_t w = 0; w < words.size(); w++) {
            snprintf(buf, sizeof buf, "%s{\"n\":%d,\"lp\":", w ? "," : "", wend[w] - wstart[w]);
            vout += buf;
            vout += arr(lp, wstart[w], wend[w]) + ",\"alt\":" + arr(alt, wstart[w], wend[w]) + ",\"top\":" + arr(top, wstart[w], wend[w]) + "}";
        }
        vout += "]}";
    }

    // الفكُّ الحرّ بالراياتِ المشحونة (‏لقياس الزمن فقط)
    double t_free = -1;
    std::string free_text;
    if (free_run) {
        whisper_full_params wp = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
        wp.language = "en";
        wp.entropy_thold = 2.40f;
        wp.n_threads = threads;
        wp.print_progress = wp.print_realtime = wp.print_timestamps = wp.print_special = false;
        t0 = clk::now();
        if (whisper_full(ctx, wp, pcm.data(), (int) pcm.size()) == 0) {
            t_free = ms_since(t0);
            for (int s = 0; s < whisper_full_n_segments(ctx); s++) free_text += whisper_full_get_segment_text(ctx, s);
        }
    }

    printf("{\"n_samples\":%zu,\"mel_ms\":%.1f,\"enc_ms\":%.1f,\"forced_ms\":%.1f,\"free_ms\":%.1f,\"variants\":[%s],\"free_text\":\"",
           pcm.size(), t_mel, t_enc, t_forced_total, t_free, vout.c_str());
    for (char c : free_text) { if (c == '"' || c == '\\') putchar('\\'); if (c == '\n') c = ' '; putchar(c); }
    printf("\"}\n");
    whisper_free(ctx);
    return 0;
}
