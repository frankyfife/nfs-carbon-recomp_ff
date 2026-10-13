// Globals the SDK sources compiled into the game for the native renderer
// refer to, but that live in the GPU plugin's sources (not compiled in here).
#include <cstdint>

namespace rex::graphics {

// util/draw.cpp (patches/rexglue-android.patch): the single-pass window of the
// Xenos command processor. The native renderer has none.
uint32_t nfsmw_una_pasada_ventana = 0;

}  // namespace rex::graphics
