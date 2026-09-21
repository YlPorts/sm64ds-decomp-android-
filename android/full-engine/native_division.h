#pragma once
#include <stdint.h>
// A '/' inside __aeabi_*div calls that same helper on ARMv7 without IDIV.
// Restoring division uses only shifts and subtraction, including on Cortex-A9.
static inline uint32_t sm64ds_unsigned_quotient(uint32_t numerator, uint32_t divisor) {
    if (!divisor) return 0;
    uint32_t quotient = 0, remainder = 0;
    for (int bit = 31; bit >= 0; --bit) {
        const bool carry = (remainder >> 31) != 0;
        remainder = (remainder << 1) | ((numerator >> bit) & 1);
        if (carry || remainder >= divisor) {
            remainder -= divisor;
            quotient |= uint32_t(1) << bit;
        }
    }
    return quotient;
}
static inline int32_t sm64ds_signed_quotient(int32_t numerator, int32_t divisor) {
    const uint32_t n = numerator < 0 ? 0u-uint32_t(numerator) : uint32_t(numerator);
    const uint32_t d = divisor < 0 ? 0u-uint32_t(divisor) : uint32_t(divisor);
    const uint32_t q = sm64ds_unsigned_quotient(n, d);
    return int32_t((numerator < 0) != (divisor < 0) ? 0u-q : q);
}
