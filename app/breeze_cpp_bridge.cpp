// Private in-process ABI for Jinx. No HTTP listener; upstream stays unmodified.
#include "breeze/generation.h"
#include "breeze/audio.h"
#include "breeze/voice.h"
#include <memory>
#include <stdexcept>
#include <cstdlib>
#if defined(_WIN32)
#define JINX_EXPORT __declspec(dllexport)
#else
#define JINX_EXPORT
#endif
using namespace breeze;
struct JinxBreeze {
    BreezeModel model;
    MimiCodec codec;
    Voice voice;
    ~JinxBreeze() { model.free(); }
};
static thread_local std::string error;
extern "C" {
JINX_EXPORT const char * jinx_breeze_error() { return error.c_str(); }
JINX_EXPORT void * jinx_breeze_init(const char * model, const char * reference,
                       const char * transcript, const char * cached) {
    try {
        auto c = std::make_unique<JinxBreeze>();
        // Upstream requests discrete GPU only; Strix Halo is GGML's IGPU type.
        auto & m = c->model;
        m.backend.backend = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_IGPU, nullptr);
        if (!m.backend.backend)
            m.backend.backend = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_GPU, nullptr);
        m.backend.is_gpu = m.backend.backend != nullptr;
        if (!m.backend.backend && std::getenv("JINX_BREEZE_ALLOW_CPU"))
            m.backend.backend = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_CPU, nullptr);
        if (!m.backend.backend) throw std::runtime_error("Breeze Vulkan GPU is unavailable");
        m.backend.alloc = ggml_gallocr_new(ggml_backend_get_default_buffer_type(m.backend.backend));
        if (!m.gg.load(model,m.backend)) throw std::runtime_error("Breeze weights could not be loaded");
        m.cfg = parse_config(m.gg);
        if (!m.tok.load(m.gg)) throw std::runtime_error("Breeze tokenizer could not be loaded");
        c->codec.init(c->model);
        if (!load_voice(cached, c->voice) || c->voice.text != transcript ||
            c->voice.n_codebooks != c->model.cfg.num_codebooks) {
            std::vector<float> samples;
            if (!read_wav(reference, c->model.cfg.sample_rate, samples))
                throw std::runtime_error("Jinx reference recording is unavailable");
            c->voice.name = "jinx";
            c->voice.text = transcript;
            c->voice.codes = c->codec.encode(samples, c->voice.frames);
            c->voice.n_codebooks = c->model.cfg.num_codebooks;
            c->voice.sample_rate = c->model.cfg.sample_rate;
            if (!save_voice(cached, c->voice))
                throw std::runtime_error("Could not save Jinx reference cache");
        }
        return c.release();
    } catch (const std::exception & e) { error = e.what(); return nullptr; }
}
JINX_EXPORT void jinx_breeze_free(void * ctx) { delete static_cast<JinxBreeze *>(ctx); }
JINX_EXPORT int jinx_breeze_generate(void * ctx, const char * text, int chunk_first, int chunk_max,
                        int (*callback)(const float *, int)) {
    try {
        auto & c = *static_cast<JinxBreeze *>(ctx);
        GenRequest r;
        r.text = text;
        r.ref_text = c.voice.text;
        r.ref_codes = c.voice.codes;
        r.ref_frames = c.voice.frames;
        r.seed = 42;
        r.repetition_penalty = 1.1f;
        r.max_new_tokens = 800;
        r.chunk_first = chunk_first;
        r.chunk_max = chunk_max;
        generate(c.model, c.codec, r, [&](const float * p, int n) { return callback(p,n) == 0; });
        return 0;
    } catch (const std::exception & e) { error = e.what(); return 1; }
}
}
