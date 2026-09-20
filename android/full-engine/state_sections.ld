/* The original sentinels must bound ALL DS state families, not just $mmm.
 * Lexical order also preserves the original card and OAM interior aliases.
 */
SECTIONS
{
  .sm64ds_state : ALIGN(16)
  {
    KEEP(*(.dsstate$aaa))
    *(.sm64ds_state_data)
    *(.sm64ds_state_bss)
    *(sm64ds_state)
    KEEP(*(SORT_BY_NAME(.dsstate$*)))
  }
  ASSERT(dsstate_lo == ADDR(.sm64ds_state), "DS state start sentinel is missing or misplaced")
  ASSERT(dsstate_hi + 1 == ADDR(.sm64ds_state) + SIZEOF(.sm64ds_state), "DS state end sentinel does not cover all families")
}
INSERT AFTER .data;
