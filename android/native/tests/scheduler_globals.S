/* SPDX-License-Identifier: MIT
 * TEST-OWNED storage, not the full engine's globals. Match the original 0x54-byte
 * manager and its interior symbols without relying on linker adjacency. */
.bss
.balign 4
.globl data_020a6134
.type data_020a6134, %object
data_020a6134:
.zero 8
.globl data_020a613c
.type data_020a613c, %object
data_020a613c:
.zero 12
.globl data_020a6148
.type data_020a6148, %object
data_020a6148:
.zero 64
.size data_020a6134, 84
.size data_020a613c, 4
.size data_020a6148, 64
.section .note.GNU-stack,"",%progbits
