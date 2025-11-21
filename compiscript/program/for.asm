.text
.globl main

main:
  addi $sp, $sp, -12
  sw $ra, 8($sp)
  # local a -> 0($sp)
  # local t0 -> 4($sp)
main_entry:
  li $t0, 1
  sw $t0, 0($sp)
  j for_cond_1
for_cond_1:
  lw $t0, 0($sp)
  li $t1, 5
  slt $t2, $t0, $t1
  sw $t2, 4($sp)
  lw $t0, 4($sp)
  bne $t0, $zero, for_body_2
  j for_end_4
for_body_2:
  lw $a0, 0($sp)
  li $v0, 1
  syscall
  j for_step_3
for_step_3:
  lw $t0, 0($sp)
  li $t1, 1
  add $t2, $t0, $t1
  sw $t2, 4($sp)
  lw $t0, 4($sp)
  sw $t0, 0($sp)
  j for_cond_1
for_end_4:
  lw $ra, 8($sp)
  addi $sp, $sp, 12
  jr $ra