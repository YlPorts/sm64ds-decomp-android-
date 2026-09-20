// SPDX-License-Identifier: MIT
#pragma once
// Only the audited NTR globals are enrolled here. This is NOT an implementation
// of the game's save-state system or a claim that all engine globals are hosted.
#if !defined(__GNUC__) && !defined(__clang__)
#error "This adapter requires an ELF compiler with section attributes"
#endif
#define SM64DS_CAPTURED __attribute__((section("sm64ds_state"), used, aligned(4)))
