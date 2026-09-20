// Real NTR memory/geometry/raster pipeline with synthetic input. NOT GAMEPLAY.
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include "ntr/mmio.h"
#include "ntr/gx.h"
#include "ntr/ppu.h"

static void require(bool ok, const char *message) {
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", message); std::exit(1); }
    std::printf("PASS: %s\n", message);
}
static void command(unsigned cmd, uint32_t param) {
    ntr::io_write(0x04000400u + 4u * cmd, param, 4);
}
static void vertex(int16_t x, int16_t y, int16_t z) {
    command(0x23, uint16_t(x) | (uint32_t(uint16_t(y)) << 16));
    command(0x23, uint16_t(z));
}
int main() {
    require(ntr::io_init(), "real NTR memory initialization");
    require(ntr::io_init(), "repeated memory initialization");
    ntr::io_write(0x04000280, 0, 2);
    ntr::io_write(0x04000290, 123456, 8);
    ntr::io_write(0x04000298, 97, 8);
    require(ntr::io_read(0x040002A0, 8) == 1272 &&
            ntr::io_read(0x040002A8, 8) == 72, "real MMIO division and remainder");
    ntr::io_write(0x040002B0, 0, 2);
    ntr::io_write(0x040002B8, 15241578750190521ULL, 8);
    // Mode 0 uses only the low 32 bits; use a small exact square for this case.
    ntr::io_write(0x040002B8, 144, 8);
    require(ntr::io_read(0x040002B4, 4) == 12, "real MMIO square root");
    ntr::gx_reset();
    ntr::io_write(0x04000600, 0, 4);
    require((ntr::io_read(0x04000600, 4) & 0x06000000u) == 0x06000000u,
            "GX FIFO readiness survives register reset");
    command(0x10, 0); command(0x15, 0); // projection identity
    command(0x10, 2); command(0x15, 0); // position/vector identity
    command(0x60, (191u << 24) | (255u << 16));
    command(0x29, (31u << 16) | 0xC0u);
    static uint32_t texture[64];
    for (unsigned i = 0; i < 64; ++i)
        texture[i] = ((i ^ (i >> 3)) & 1) ? 0xFFFFFFFFu : 0xFF00FF00u;
    ntr::gx_bind_texture(texture, 8, 8);
    command(0x20, 0x7FFF); // white material colour
    command(0x40, 0);      // triangle
    command(0x22, 0); vertex(-2048, -2048, 0);
    command(0x22, 7u * 16u); vertex(2048, -2048, 0);
    command(0x22, (7u * 16u) << 16); vertex(0, 2048, 0);
    command(0x41, 0);
    size_t polygons = 0;
    const auto *tri = ntr::gx_polygons(polygons);
    require(tri != nullptr && polygons == 1, "MMIO commands produce one real geometry triangle");
    static ntr::Framebuffer fb;
    for (auto &row : fb.px) for (auto &px : row) px = 0xFF000000u;
    ntr::gx_render(fb);
    unsigned covered = 0, white = 0, green = 0;
    const auto *mask = ntr::gx_coverage();
    for (int y = 0; y < ntr::SCREEN_H; ++y) {
        for (int x = 0; x < ntr::SCREEN_W; ++x) {
            const auto px = fb.px[y][x];
            covered += mask[y * ntr::SCREEN_W + x] != 0;
            white += (px & 0xFFFFFFu) == 0xFFFFFFu;
            green += (px & 0xFFFFFFu) == 0x00FF00u;
        }
    }
    std::printf("RASTER: polygons=%zu coverage=%u white=%u green=%u\n", polygons, covered, white, green);
    require(covered > 100 && white > 10 && green > 10, "real textured raster and coverage mask");
    require(ntr::ppu_write_bmp("platform-probe.bmp", fb), "framebuffer written for inspection");
    std::puts("RESULT: real platform path passed; synthetic display list, no assets, no level, no Android device execution");
    return 0;
}
