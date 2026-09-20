/* Native compiler bridge, not a Windows implementation or an ABI conversion.
 * Only these MSVC storage annotations have explicit ELF equivalents here.
 * Unrecognised annotations intentionally fail compilation.
 */
#ifndef SM64DS_ELF_COMPAT_H
#define SM64DS_ELF_COMPAT_H
#include <stddef.h>
#include <stdint.h>
#if !defined(__clang__) || !defined(__ELF__)
#error "This bridge requires Clang targeting ELF"
#endif
#ifdef _WIN32
#error "Do not impersonate Windows when compiling the Android engine"
#endif
#ifdef __cplusplus
static_assert(sizeof(void*) == 4, "The game layout remains 32-bit");
#else
_Static_assert(sizeof(void*) == 4, "The game layout remains 32-bit");
#endif
#define SM64DS_DECLSPEC_align(n) __attribute__((aligned(n)))
#define SM64DS_DECLSPEC_allocate(s) __attribute__((section(s)))
#define SM64DS_DECLSPEC_selectany __attribute__((weak))
#define __declspec(x) SM64DS_DECLSPEC_##x
/* The original guard prevents the Windows-only macro definitions being read.
 * Both classes remain explicitly enrolled, in separate ELF input sections.
 * They require a future complete-engine linker script and runtime validation.
 * These declarations alone DO NOT implement savestates or packed data aliases.
 */
#define PORT_HAL_DSSTATE_SEG_H
#define DSSTATE_BEGIN _Pragma("clang section bss=\".sm64ds_state_bss\" data=\".sm64ds_state_data\"")
#define DSSTATE_END _Pragma("clang section bss=\"\" data=\"\"")
#endif
