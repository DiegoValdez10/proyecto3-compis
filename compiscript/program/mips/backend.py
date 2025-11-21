from __future__ import annotations

from typing import Dict, List, Optional

from program.tac.tac_model import (
    Value,
    TacInstruction,
    Assign,
    BinaryOp,
    UnaryOp,
    ArrayNew,
    ArrayStore,
    ArrayIndex,
    ArrayLength,
    FieldLoad,
    FieldStore,
    Call,
    Branch,
    Jump,
    Print,
    Return,
    BeginTry,
    EndTry,
    BeginCatch,
    EndCatch,
    TacFunction,
    TacProgram,
)


class MipsBackend:
    def __init__(self) -> None:
        self.text_lines: List[str] = []
        self.data_lines: List[str] = []
        self.slot_map: Dict[str, int] = {}
        self._param_types: Dict[str, str] = {}
        self._string_counter: int = 0
        self._field_offsets: Dict[str, Dict[str, int]] = {}
        self._field_types: Dict[str, str] = {}
        self._in_constructor: bool = False
        
    def emit(self, line: str) -> None:
        self.text_lines.append(line)

    def _fresh_string_label(self) -> str:
        self._string_counter += 1
        return f"str_{self._string_counter}"

    def emit_program(self, program: TacProgram) -> str:
        return self.generate_program(program)

    def generate_program(self, program: TacProgram) -> str:
        self.text_lines = []
        self.data_lines = []
        
        if "main" in program.functions:
            self._generate_function(program.functions["main"])
        
        for func_name, func in program.functions.items():
            if func_name != "main":
                self._generate_function(func)
        
        lines: List[str] = []
        if self.data_lines:
            lines.append(".data")
            lines.extend(self.data_lines)
            lines.append("")
        lines.append(".text")
        if "main" in program.functions:
            lines.append(".globl main")
        lines.append("")
        lines.extend(self.text_lines)
        return "\n".join(lines)

    def _collect_locals(self, func: TacFunction) -> List[str]:
        locals_order: List[str] = []

        def add_local(name: str) -> None:
            if name and name != "_" and name != "this" and name not in locals_order:
                locals_order.append(name)

        for block in func.blocks:
            for instr in block.instructions:
                if isinstance(instr, (Assign, BinaryOp, UnaryOp, ArrayNew, ArrayIndex, ArrayLength, FieldLoad)):
                    add_local(instr.dest)
                elif isinstance(instr, Call) and instr.dest:
                    add_local(instr.dest)
                elif isinstance(instr, BeginCatch) and instr.dest:
                    add_local(instr.dest)
                    
        return locals_order

    def _allocate_frame(self, func: TacFunction) -> tuple[int, int]:
        self.slot_map = {}
        self._param_types = {}
        offset = 0
        
        param_count = len(func.params)
        for i, param in enumerate(func.params):
            self.slot_map[param] = offset
            if param != 'this' and not param.isdigit():
                self._param_types[param] = 'string'
            offset += 4
        
        locals_order = self._collect_locals(func)
        for name in locals_order:
            if name not in self.slot_map:
                self.slot_map[name] = offset
                offset += 4
        
        ra_offset = offset
        frame_size = offset + 4
        
        return frame_size, ra_offset

    def _generate_function(self, func: TacFunction) -> None:
        frame_size, ra_offset = self._allocate_frame(func)
        
        self._in_constructor = ".constructor" in func.name or "init" in func.name
        
        self.emit(f"{func.name}:")
        self.emit(f"  addi $sp, $sp, -{frame_size}")
        self.emit(f"  sw $ra, {ra_offset}($sp)")
        
        for i, param in enumerate(func.params[:4]):
            offset = self.slot_map[param]
            self.emit(f"  sw $a{i}, {offset}($sp)")
        
        for block in func.blocks:
            self.emit(f"{block.label}:")
            for instr in block.instructions:
                self._emit_instr(instr, frame_size, ra_offset)
        
        self._in_constructor = False

    def _emit_load_value(self, dst_reg: str, val: Value) -> None:
        kind = val.kind
        text = val.text
        
        if kind == "int" or (kind == "unknown" and text.isdigit()):
            self.emit(f"  li {dst_reg}, {text}")
            return
        
        if kind == "bool":
            v = 1 if text == "true" else 0
            self.emit(f"  li {dst_reg}, {v}")
            return
        
        if kind == "string" or (kind == "unknown" and text.startswith('"')):
            label = self._fresh_string_label()
            self.data_lines.append(f"{label}: .asciiz {text}")
            self.emit(f"  la {dst_reg}, {label}")
            return
        
        if kind == "null":
            self.emit(f"  li {dst_reg}, 0")
            return
        
        if kind == "identifier":
            if text in self.slot_map:
                off = self.slot_map[text]
                self.emit(f"  lw {dst_reg}, {off}($sp)")
            else:
                self.emit(f"  li {dst_reg}, 0")
            return
        
        self.emit(f"  li {dst_reg}, 0")

    def _emit_instr(self, instr: TacInstruction, frame_size: int, ra_offset: int) -> None:
        
        if isinstance(instr, Assign):
            if instr.dest in self.slot_map:
                self._emit_load_value("$t0", instr.value)
                off = self.slot_map[instr.dest]
                self.emit(f"  sw $t0, {off}($sp)")
            return
        
        if isinstance(instr, BinaryOp):
            self._emit_load_value("$t0", instr.left)
            self._emit_load_value("$t1", instr.right)
            
            op = instr.op
            if op in ("+", "add"):
                self.emit("  add $t2, $t0, $t1")
            elif op in ("-", "sub"):
                self.emit("  sub $t2, $t0, $t1")
            elif op in ("*", "mul"):
                self.emit("  mul $t2, $t0, $t1")
            elif op in ("/", "div"):
                self.emit("  div $t0, $t1")
                self.emit("  mflo $t2")
            elif op in ("%", "mod"):
                self.emit("  div $t0, $t1")
                self.emit("  mfhi $t2")
            elif op in ("<", "lt"):
                self.emit("  slt $t2, $t0, $t1")
            elif op in (">", "gt"):
                self.emit("  slt $t2, $t1, $t0")
            elif op in ("<=", "le"):
                self.emit("  slt $t2, $t1, $t0")
                self.emit("  xori $t2, $t2, 1")
            elif op in (">=", "ge"):
                self.emit("  slt $t2, $t0, $t1")
                self.emit("  xori $t2, $t2, 1")
            elif op in ("==", "eq"):
                self.emit("  sub $t2, $t0, $t1")
                self.emit("  sltiu $t2, $t2, 1")
            elif op in ("!=", "ne"):
                self.emit("  sub $t2, $t0, $t1")
                self.emit("  sltu $t2, $zero, $t2")
            elif op in ("&&", "and"):
                self.emit("  and $t2, $t0, $t1")
            elif op in ("||", "or"):
                self.emit("  or $t2, $t0, $t1")
            else:
                self.emit(f"  li $t2, 0")
            
            if instr.dest in self.slot_map:
                off = self.slot_map[instr.dest]
                self.emit(f"  sw $t2, {off}($sp)")
            return
        
        if isinstance(instr, UnaryOp):
            self._emit_load_value("$t0", instr.operand)
            
            if instr.op in ("neg", "-"):
                self.emit("  neg $t1, $t0")
            elif instr.op in ("not", "!"):
                self.emit("  xori $t1, $t0, 1")
            else:
                self.emit(f"  move $t1, $t0")
            
            if instr.dest in self.slot_map:
                off = self.slot_map[instr.dest]
                self.emit(f"  sw $t1, {off}($sp)")
            return
        
        if isinstance(instr, ArrayNew):
            self._emit_load_value("$a1", instr.size)
            self.emit("  move $t9, $a1")
            self.emit("  li $a0, 4")
            self.emit("  mul $a0, $a0, $a1")
            self.emit("  addi $a0, $a0, 4")
            self.emit("  li $v0, 9")
            self.emit("  syscall")
            self.emit("  sw $t9, 0($v0)")
            self.emit("  addi $v0, $v0, 4")
            
            if instr.dest in self.slot_map:
                off = self.slot_map[instr.dest]
                self.emit(f"  sw $v0, {off}($sp)")
            return
        
        if isinstance(instr, ArrayStore):
            if instr.array in self.slot_map:
                off = self.slot_map[instr.array]
                self.emit(f"  lw $t0, {off}($sp)")
            else:
                self.emit("  li $t0, 0")
            
            self._emit_load_value("$t1", instr.index)
            self.emit("  sll $t1, $t1, 2")
            self.emit("  add $t0, $t0, $t1")
            
            self._emit_load_value("$t2", instr.value)
            self.emit("  sw $t2, 0($t0)")
            return
        
        if isinstance(instr, ArrayIndex):
            if instr.array in self.slot_map:
                off = self.slot_map[instr.array]
                self.emit(f"  lw $t0, {off}($sp)")
            else:
                self.emit("  li $t0, 0")
            
            self._emit_load_value("$t1", instr.index)
            self.emit("  sll $t1, $t1, 2")
            self.emit("  add $t0, $t0, $t1")
            self.emit("  lw $t2, 0($t0)")
            
            if instr.dest in self.slot_map:
                off = self.slot_map[instr.dest]
                self.emit(f"  sw $t2, {off}($sp)")
            return
        
        if isinstance(instr, ArrayLength):
            if instr.array in self.slot_map:
                obj_off = self.slot_map[instr.array]
                self.emit(f"  lw $t0, {obj_off}($sp)")
            else:
                self.emit("  li $t0, 0")
            
            self.emit("  lw $t1, -4($t0)")
            
            if instr.dest in self.slot_map:
                off = self.slot_map[instr.dest]
                self.emit(f"  sw $t1, {off}($sp)")
            return
        
        if isinstance(instr, FieldLoad):
            if instr.object in self.slot_map:
                obj_off = self.slot_map[instr.object]
                self.emit(f"  lw $t0, {obj_off}($sp)")
            else:
                self.emit("  li $t0, 0")
            
            field_name = instr.field.text.strip('"')
            field_offset = self._get_field_offset(field_name)
            
            self.emit(f"  lw $t1, {field_offset}($t0)")
            
            if field_name in ("name", "nombre"):
                self._field_types[instr.dest] = "string"
            
            if instr.dest in self.slot_map:
                off = self.slot_map[instr.dest]
                self.emit(f"  sw $t1, {off}($sp)")
            return
        
        if isinstance(instr, FieldStore):
            if instr.object in self.slot_map:
                obj_off = self.slot_map[instr.object]
                self.emit(f"  lw $t0, {obj_off}($sp)")
            else:
                self.emit("  li $t0, 0")
            
            field_name = instr.field.text.strip('"')
            field_offset = self._get_field_offset(field_name)
            
            self._emit_load_value("$t1", instr.value)
            self.emit(f"  sw $t1, {field_offset}($t0)")
            return
        
        if isinstance(instr, Call):
            if ".constructor" in instr.function or "init" in instr.function:
                if not self._in_constructor:
                    self.emit("  li $a0, 12")
                    self.emit("  li $v0, 9")
                    self.emit("  syscall")
                    self.emit("  move $a0, $v0")
                    
                    for i, arg in enumerate(instr.args):
                        if i < 3:
                            self._emit_load_value(f"$a{i+1}", arg)
                else:
                    for i, arg in enumerate(instr.args[:4]):
                        self._emit_load_value(f"$a{i}", arg)
            else:
                for i, arg in enumerate(instr.args[:4]):
                    self._emit_load_value(f"$a{i}", arg)
            
            self.emit(f"  jal {instr.function}")
            
            if instr.dest and instr.dest in self.slot_map:
                off = self.slot_map[instr.dest]
                self.emit(f"  sw $v0, {off}($sp)")
            return
        
        if isinstance(instr, Branch):
            self._emit_load_value("$t0", instr.condition)
            self.emit(f"  bne $t0, $zero, {instr.true_label}")
            self.emit(f"  j {instr.false_label}")
            return
        
        if isinstance(instr, Jump):
            self.emit(f"  j {instr.target}")
            return
        
        if isinstance(instr, Print):
            val = instr.value
            
            if val.kind == "identifier" and val.text in self._field_types:
                if self._field_types[val.text] == "string":
                    self._emit_load_value("$a0", val)
                    self.emit("  li $v0, 4")
                    self.emit("  syscall")
                    return
            
            if val.kind == "identifier" and val.text in self._param_types:
                if self._param_types[val.text] == "string":
                    self._emit_load_value("$a0", val)
                    self.emit("  li $v0, 4")
                    self.emit("  syscall")
                    return
            
            if val.kind == "string":
                self._emit_load_value("$a0", val)
                self.emit("  li $v0, 4")
                self.emit("  syscall")
            elif val.kind in ("int", "bool"):
                self._emit_load_value("$a0", val)
                self.emit("  li $v0, 1")
                self.emit("  syscall")
            elif val.kind == "identifier":
                self._emit_load_value("$a0", val)
                self.emit("  li $v0, 1")
                self.emit("  syscall")
            return
        
        if isinstance(instr, Return):
            if instr.value:
                self._emit_load_value("$v0", instr.value)
            self.emit(f"  lw $ra, {ra_offset}($sp)")
            self.emit(f"  addi $sp, $sp, {frame_size}")
            self.emit("  jr $ra")
            return
        
        if isinstance(instr, BeginTry):
            self.emit(f"  # begin_try {instr.handler_label}")
            return
        
        if isinstance(instr, EndTry):
            self.emit("  # end_try")
            return
        
        if isinstance(instr, BeginCatch):
            self.emit("  # begin_catch")
            if instr.dest and instr.dest in self.slot_map:
                self.emit("  li $t0, 0")
                off = self.slot_map[instr.dest]
                self.emit(f"  sw $t0, {off}($sp)")
            return
        
        if isinstance(instr, EndCatch):
            self.emit("  # end_catch")
            return
        
        self.emit("  nop")

    def _get_field_offset(self, field_name: str) -> int:
        common_fields = {
            "x": 0,
            "y": 4,
            "z": 8,
            "name": 0,
            "nombre": 0,
            "age": 4,
            "edad": 4,
            "value": 0,
            "next": 4,
        }
        
        return common_fields.get(field_name, 0)