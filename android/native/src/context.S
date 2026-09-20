/* SPDX-License-Identifier: MIT
 * ABI-preserving stack switch. Saves only the registers an ordinary function
 * call must preserve, plus floating-point control state. No JIT or CPU emulation.
 */
#if defined(__arm__)
.syntax unified
.arch armv7-a
.fpu vfpv3-d16
.thumb
.text
.p2align 2
.global sm64ds_context_swap
.hidden sm64ds_context_swap
.type sm64ds_context_swap,%function
.thumb_func
sm64ds_context_swap:
    push {r4-r11, lr}
    sub sp, sp, #4
    vpush {d8-d15}
    vmrs r2, fpscr
    sub sp, sp, #8
    str r2, [sp]
    str sp, [r0]
    mov sp, r1
    ldr r2, [sp]
    add sp, sp, #8
    vmsr fpscr, r2
    vpop {d8-d15}
    add sp, sp, #4
    pop {r4-r11, lr}
    bx lr
.size sm64ds_context_swap, .-sm64ds_context_swap
#elif defined(__aarch64__)
.text
.p2align 2
.global sm64ds_context_swap
.hidden sm64ds_context_swap
.type sm64ds_context_swap,%function
sm64ds_context_swap:
    stp x19, x20, [sp, #-176]!
    stp x21, x22, [sp, #16]
    stp x23, x24, [sp, #32]
    stp x25, x26, [sp, #48]
    stp x27, x28, [sp, #64]
    stp x29, x30, [sp, #80]
    stp d8, d9, [sp, #96]
    stp d10, d11, [sp, #112]
    stp d12, d13, [sp, #128]
    stp d14, d15, [sp, #144]
    mrs x2, fpcr
    mrs x3, fpsr
    stp x2, x3, [sp, #160]
    mov x2, sp
    str x2, [x0]
    mov sp, x1
    ldp x2, x3, [sp, #160]
    msr fpcr, x2
    msr fpsr, x3
    ldp d8, d9, [sp, #96]
    ldp d10, d11, [sp, #112]
    ldp d12, d13, [sp, #128]
    ldp d14, d15, [sp, #144]
    ldp x19, x20, [sp]
    ldp x21, x22, [sp, #16]
    ldp x23, x24, [sp, #32]
    ldp x25, x26, [sp, #48]
    ldp x27, x28, [sp, #64]
    ldp x29, x30, [sp, #80]
    add sp, sp, #176
    ret
.size sm64ds_context_swap, .-sm64ds_context_swap
#elif defined(__x86_64__)
.text
.p2align 4
.global sm64ds_context_swap
.hidden sm64ds_context_swap
.type sm64ds_context_swap,@function
sm64ds_context_swap:
    pushq %rbp
    pushq %rbx
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    subq $24, %rsp
    stmxcsr (%rsp)
    fnstcw 4(%rsp)
    movq %rsp, (%rdi)
    movq %rsi, %rsp
    ldmxcsr (%rsp)
    fldcw 4(%rsp)
    addq $24, %rsp
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %rbx
    popq %rbp
    ret
.size sm64ds_context_swap, .-sm64ds_context_swap
#else
#error Unsupported architecture
#endif
#if defined(__linux__) || defined(__ANDROID__)
.section .note.GNU-stack,"",%progbits
#endif
