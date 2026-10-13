// NFS Carbon at 60 fps (experimental, off by default; docs/60fps.md).
//
// Carbon's simulation steps at a fixed 1/60 s (as in the NFS Most Wanted
// decomp: Scheduler::Init(1/60), MaxTicksPerTimestep 4), but the game shows a
// frame only every 1/30 s: on the console every frame runs two steps. A
// faster guest vblank does not help (measured: the game thread still idles
// ~31 ms a frame), so the cap is the engine's own frame time limiter
// (SetFPSLimiter / LimitMinimumVideoTimeElapsed in the decomp), not the D3D
// swap throttle. Its addresses in this XEX are not known yet;
// tools/find_60fps.py lists the candidates in a guest_image.bin.
//
// Code patches like Xenia's do nothing in a static recompilation (the guest
// code is compiled C++), so there are two ways in:
//
// - carbon_60fps_patches: guest data words kept patched while the game runs,
//   "ADDRESS:FROM:TO" (hex address in the XEX image; values as floats when
//   they have a '.', otherwise hex words), comma-separated. A word is only
//   written while it holds FROM (a float FROM to 1e-4 relative), so a wrong
//   address that holds something else stays untouched;
//   the game setting it again (SetFPSLimiter(30) at the start of a race) is
//   undone within a millisecond. Example for the limiter global (address to
//   be found): "82XXXXXX:0.033333:3C888889" (TO as the exact 1/60).
// - NFSCARBON_FPS_LIMITER_FUNC (CMake cache variable, the function's address
//   as 8 hex digits, e.g. 8236ABCD): hooks the SetFPSLimiter(float fps)-shaped
//   function find_60fps.py reports; with carbon_60fps an fps below 60 becomes
//   60 before the original runs.

#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

#include <rex/cvar.h>
#include <rex/logging.h>
#include <rex/ppc/context.h>
#include <rex/ppc/func.h>
#include <rex/runtime.h>

REXCVAR_DEFINE_BOOL(carbon_60fps, false, "Carbon",
                    "Experimental: lift the game's 30 fps frame limiter (needs "
                    "carbon_60fps_patches or a build with NFSCARBON_FPS_LIMITER_FUNC; "
                    "docs/60fps.md)");
REXCVAR_DEFINE_STRING(carbon_60fps_patches, "", "Carbon",
                      "With carbon_60fps: guest data kept patched, ADDRESS:FROM:TO,... (hex "
                      "address; values as floats with a '.', else hex words); only written "
                      "while the word holds FROM");

namespace {

// The loaded XEX image (its globals are what the patches are for).
constexpr uint32_t kImageBegin = 0x82000000, kImageEnd = 0x830D0000;

struct DataPatch {
  uint32_t address, from, to;
  bool from_float = false;
  std::atomic<uint64_t> writes{0};

  bool Holds(uint32_t value) const {
    if (!from_float) {
      return value == from;
    }
    float a, b;
    std::memcpy(&a, &value, 4);
    std::memcpy(&b, &from, 4);
    return std::fabs(a - b) <= 1e-4f * std::fabs(b);
  }
};

bool IsFloat(const std::string& text) { return text.find('.') != std::string::npos; }

uint32_t ParseValue(const std::string& text, bool& ok) {
  char* end = nullptr;
  if (IsFloat(text)) {
    const float value = std::strtof(text.c_str(), &end);
    uint32_t bits;
    std::memcpy(&bits, &value, 4);
    ok = end && *end == '\0';
    return bits;
  }
  const unsigned long value = std::strtoul(text.c_str(), &end, 16);
  ok = end && *end == '\0' && !text.empty();
  return uint32_t(value);
}

std::vector<DataPatch*> ParsePatches(const std::string& list) {
  std::vector<DataPatch*> patches;
  size_t begin = 0;
  while (begin < list.size()) {
    size_t end = list.find(',', begin);
    if (end == std::string::npos) {
      end = list.size();
    }
    const std::string entry = list.substr(begin, end - begin);
    begin = end + 1;
    const size_t c1 = entry.find(':'), c2 = entry.find(':', c1 + 1);
    bool ok_address = false, ok_from = false, ok_to = false;
    if (c1 != std::string::npos && c2 != std::string::npos) {
      auto* p = new DataPatch;
      p->address = ParseValue(entry.substr(0, c1), ok_address);
      p->from = ParseValue(entry.substr(c1 + 1, c2 - c1 - 1), ok_from);
      p->from_float = IsFloat(entry.substr(c1 + 1, c2 - c1 - 1));
      p->to = ParseValue(entry.substr(c2 + 1), ok_to);
      if (ok_address && ok_from && ok_to && !(p->address & 3) && p->address >= kImageBegin &&
          p->address < kImageEnd) {
        patches.push_back(p);
        continue;
      }
      delete p;
    }
    REXLOG_WARN("[60fps] carbon_60fps_patches: ignoring '{}' (ADDRESS:FROM:TO, an aligned "
                "address in the XEX image)",
                entry);
  }
  return patches;
}

// Started at load like REX_DUMP_GUEST_IMAGE (dispatch_tolerance.cpp); the cvars
// are read once the runtime exists.
const bool g_patcher_started = [] {
  std::thread([] {
    rex::Runtime* runtime = nullptr;
    for (;; std::this_thread::sleep_for(std::chrono::milliseconds(100))) {
      runtime = rex::Runtime::instance();
      if (runtime && runtime->virtual_membase()) {
        break;
      }
    }
    if (!REXCVAR_GET(carbon_60fps)) {
      return;
    }
    const std::vector<DataPatch*> patches = ParsePatches(REXCVAR_GET(carbon_60fps_patches));
#ifndef NFSCARBON_FPS_LIMITER_FUNC
    if (patches.empty()) {
      REXLOG_WARN("[60fps] carbon_60fps is on, but neither carbon_60fps_patches nor a "
                  "limiter hook is set: nothing changes (docs/60fps.md)");
      return;
    }
#endif
    if (patches.empty()) {
      return;
    }
    REXLOG_INFO("[60fps] keeping {} guest words patched", patches.size());
    uint8_t* const memory = runtime->virtual_membase();
    auto last_log = std::chrono::steady_clock::now();
    for (;;) {
      for (DataPatch* p : patches) {
        auto* word = reinterpret_cast<volatile uint32_t*>(memory + p->address);
        if (p->Holds(__builtin_bswap32(*word))) {
          *word = __builtin_bswap32(p->to);
          if (p->writes++ == 0) {
            REXLOG_INFO("[60fps] {:08X}: {:08X} -> {:08X} (first time)", p->address, p->from,
                        p->to);
          }
        }
      }
      const auto now = std::chrono::steady_clock::now();
      if (now - last_log > std::chrono::seconds(30)) {
        last_log = now;
        for (DataPatch* p : patches) {
          REXLOG_INFO("[60fps] {:08X}: written {} times, now {:08X}", p->address,
                      p->writes.load(),
                      __builtin_bswap32(*reinterpret_cast<volatile uint32_t*>(memory + p->address)));
        }
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  }).detach();
  return true;
}();

}  // namespace

#ifdef NFSCARBON_FPS_LIMITER_FUNC
#define CARBON_CAT2(a, b) a##b
#define CARBON_CAT(a, b) CARBON_CAT2(a, b)
#define CARBON_LIMITER CARBON_CAT(sub_, NFSCARBON_FPS_LIMITER_FUNC)
#define CARBON_LIMITER_ORIGINAL CARBON_CAT(__imp__sub_, NFSCARBON_FPS_LIMITER_FUNC)

extern "C" void CARBON_LIMITER_ORIGINAL(PPCContext& __restrict ctx, uint8_t* base);

// SetFPSLimiter(float fps): the limiter's minimum frame time becomes 1 / fps.
extern "C" REX_FUNC(CARBON_LIMITER) {
  if (REXCVAR_GET(carbon_60fps) && ctx.f1.f64 > 0.0 && ctx.f1.f64 < 60.0) {
    static std::atomic<uint32_t> logged{0};
    if (logged++ < 8) {
      REXLOG_INFO("[60fps] frame limiter {:.1f} fps -> 60 fps", ctx.f1.f64);
    }
    ctx.f1.f64 = 60.0;
  }
  CARBON_LIMITER_ORIGINAL(ctx, base);
}
#endif
