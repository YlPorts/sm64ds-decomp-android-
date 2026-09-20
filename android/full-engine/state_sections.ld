/* Preserve the existing supplied sentinels; this is not a save-state API.
 * Packed $mmm suffixes must remain in lexical order, not input-file order.
 */
SECTIONS
{
  .sm64ds_state : ALIGN(16)
  {
    KEEP(*(.dsstate$aaa))
    *(.sm64ds_state_data)
    *(.sm64ds_state_bss)
    *(sm64ds_state)
    KEEP(*(SORT_BY_NAME(.dsstate$mmm*)))
    KEEP(*(.dsstate$zzz))
  }
}
INSERT AFTER .data;
