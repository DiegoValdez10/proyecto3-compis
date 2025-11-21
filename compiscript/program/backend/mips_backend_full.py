# compiscript/backend/mips_backend_full.py

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional, Any


# =====================================================================
#  IR mínimo (adaptar si ya tienes tus propias clases de IR)
# =====================================================================

@dataclass
class Operand:
    name: str               # texto del operando ("x", "t1", "5", etc.)
    kind: str               # "identifier", "temp", "immediate", "label", "function", ...
    type_hint: Optional[str] = None
    value: Optional[Any] = None


@dataclass
class Instruction:
    opcode: str             # "assign", "add", "gt", "array_new", "call", ...
    dest: Optional[Operand]
    args: List[Operand]
    comment: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class BasicBlock:
    label: str
    instructions: List[Instruction]


@dataclass
class IRFunction:
    name: str
    params: List[Operand]
    return_type: Optional[str]
    blocks: List[BasicBlock]
    attributes: Dict[str, Any]
    locals: Dict[str, Any]
    metadata: Dict[str, Any]   # aquí viene "activation"


# =====================================================================
#  Backend MIPS avanzado
# =====================================================================

class CS_MipsBackend:
    """
    Backend MIPS pensado para tu IR real (IRFunction, BasicBlock, Instruction, Operand).

    - Usa metadata['activation'] para conocer offsets de variables.
    - Soporta opcodes típicos: assign, add, sub, mul, div, mod,
      lt, gt, le, ge, eq, ne, branch, jump,
      array_new, array_store, array_index, array_length,
      call, field_load, begin_try, end_try, begin_catch, print, return.

    Varias cosas están simplificadas (strings, arrays, exceptions), pero
    NO deberían romper el flujo: el objetivo es que pueda tragar IR grande.
    """

    def __init__(self):
        # Separamos sección de datos y de texto
        self.data_lines: List[str] = []
        self.text_lines: List[str] = []
        self.current_func: Optional[IRFunction] = None
        self.activation: Optional[Dict[str, Any]] = None

        # String pool
        self.string_literals: Dict[str, str] = {}
        self.string_counter: int = 0

        # Temp regs
        self.temp_regs = ["$t0", "$t1", "$t2", "$t3", "$t4",
                          "$t5", "$t6", "$t7", "$t8", "$t9"]

    # -------------------------------------------------------------
    #  API pública
    # -------------------------------------------------------------

    def generate_program(self, functions: List[IRFunction]) -> str:
        self.data_lines = [".data"]
        self.text_lines = [".text", ".globl main", ""]

        for func in functions:
            self._emit_function(func)

        # Al final añadimos el runtime (arrays, etc.)
        self._emit_runtime()

        # Unimos data + línea en blanco + text
        return "\n".join(self.data_lines + [""] + self.text_lines)

    # -------------------------------------------------------------
    #  Helpers de emisión
    # -------------------------------------------------------------

    def _emit_data(self, line: str = ""):
        self.data_lines.append(line)

    def _emit_text(self, line: str = ""):
        self.text_lines.append(line)

    # -------------------------------------------------------------
    #  String literals y .data
    # -------------------------------------------------------------

    def _intern_string(self, value: str) -> str:
        """
        Devuelve una etiqueta única en .data para el string dado.
        Si ya existe, reutiliza.
        """
        if value in self.string_literals:
            return self.string_literals[value]

        label = f"str_{self.string_counter}"
        self.string_counter += 1
        self.string_literals[value] = label

        # Escapar comillas y backslashes si quieres algo más fancy.
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        self._emit_data(f"{label}: .asciiz \"{escaped}\"")

        return label

    # -------------------------------------------------------------
    #  Funciones
    # -------------------------------------------------------------

    def _emit_function(self, func: IRFunction):
        self.current_func = func
        self.activation = func.metadata.get("activation", None)

        self._emit_text(f"# --- function {func.name} ---")
        self._emit_text(f"{func.name}:")
        self._emit_prologue()

        for block in func.blocks:
            self._emit_block(block)

        # Si la función no hace return explícito, epílogo al final
        self._emit_epilogue()
        self._emit_text("")

        self.current_func = None
        self.activation = None

    def _emit_block(self, block: BasicBlock):
        self._emit_text(f"{block.label}:")
        for instr in block.instructions:
            self._emit_instruction(instr)

    # -------------------------------------------------------------
    #  Prologue / Epilogue
    # -------------------------------------------------------------

    def _frame_size_words(self) -> int:
        """
        Usa self.activation['slots'] para calcular tamaño del frame
        en palabras (32 bits).
        """
        if not self.activation:
            return 0

        slots = self.activation.get("slots", {})
        max_offset = 0
        for slot in slots.values():
            off = slot["offset"] + slot.get("size", 1) - 1
            max_offset = max(max_offset, off)
        return max_offset + 1

    def _emit_prologue(self):
        """
        Layout del frame (simplificado):
        sp -> [ra][fp][slot_0][slot_1]...[slot_n]
        fp apunta al antiguo fp (offset 4).
        """
        frame_size = self._frame_size_words() + 2  # +ra +saved_fp
        frame_bytes = frame_size * 4

        self._emit_text("  # prologue")
        self._emit_text(f"  addi $sp, $sp, -{frame_bytes}")
        self._emit_text("  sw   $ra, 0($sp)")
        self._emit_text("  sw   $fp, 4($sp)")
        self._emit_text("  addi $fp, $sp, 4")
        self._emit_text("")

    def _emit_epilogue(self):
        frame_size = self._frame_size_words() + 2
        frame_bytes = frame_size * 4

        self._emit_text("  # epilogue")
        self._emit_text("  lw   $ra, 0($sp)")
        self._emit_text("  lw   $fp, 4($sp)")
        self._emit_text(f"  addi $sp, $sp, {frame_bytes}")
        if self.current_func and self.current_func.name == "main":
            self._emit_text("  li   $v0, 10")
            self._emit_text("  syscall")
        else:
            self._emit_text("  jr   $ra")

    # -------------------------------------------------------------
    #  Activación y variables
    # -------------------------------------------------------------

    def _find_slot(self, var_name: str):
        if not self.activation:
            return None
        return self.activation["slots"].get(var_name)

    def _addr_of_var(self, var_name: str, reg: str):
        """
        reg <- dirección de la variable var_name dentro del frame.
        """
        slot = self._find_slot(var_name)
        if slot is None:
            raise KeyError(f"Variable '{var_name}' no encontrada en activation")
        offset_words = slot["offset"]
        offset_bytes = offset_words * 4
        self._emit_text(f"  # addr of {var_name}")
        self._emit_text(f"  addi {reg}, $fp, {offset_bytes}")

    def _load_var_into(self, var_name: str, reg: str):
        self._addr_of_var(var_name, reg)
        self._emit_text(f"  lw   {reg}, 0({reg})   # load {var_name}")

    def _store_var_from(self, var_name: str, reg: str):
        self._addr_of_var(var_name, "$at")
        self._emit_text(f"  sw   {reg}, 0($at)     # store {var_name}")

    def _load_operand_into(self, op: Operand, reg: str):
        """
        Carga un Operand en un registro.
        Soporta:
          - inmediatos enteros y strings
          - identificadores / temps que viven en el frame
        """
        if op.kind == "immediate":
            if op.type_hint == "string" or (isinstance(op.value, str) and op.type_hint is None):
                label = self._intern_string(str(op.value))
                self._emit_text(f"  la   {reg}, {label}   # load address of string")
            else:
                self._emit_text(f"  li   {reg}, {op.value}")
        elif op.kind in ("identifier", "temp"):
            self._load_var_into(op.name, reg)
        else:
            # fallback textual
            self._emit_text(f"  # fallback load operand {op.name} into {reg}")
            self._emit_text(f"  li   {reg}, 0")

    # -------------------------------------------------------------
    #  Despacho de instrucciones
    # -------------------------------------------------------------

    def _emit_instruction(self, instr: Instruction):
        op = instr.opcode

        if op == "assign":
            self._emit_assign(instr)
        elif op in ("add", "sub", "mul", "div", "mod"):
            self._emit_arith(instr)
        elif op in ("lt", "gt", "le", "ge", "eq", "ne"):
            self._emit_cmp(instr)
        elif op == "branch":
            self._emit_branch(instr)
        elif op == "jump":
            self._emit_jump(instr)
        elif op == "print":
            self._emit_print(instr)
        elif op == "array_new":
            self._emit_array_new(instr)
        elif op == "array_store":
            self._emit_array_store(instr)
        elif op == "array_index":
            self._emit_array_index(instr)
        elif op == "array_length":
            self._emit_array_length(instr)
        elif op == "call":
            self._emit_call(instr)
        elif op == "field_load":
            self._emit_field_load(instr)
        elif op in ("begin_try", "end_try", "begin_catch"):
            self._emit_try_catch(instr)
        elif op == "return":
            self._emit_return(instr)
        else:
            self._emit_text(f"  # TODO opcode {op} no soportado todavía")

    # -------------------------------------------------------------
    #  Implementación de opcodes
    # -------------------------------------------------------------

    # --- assign dest := value

    def _emit_assign(self, instr: Instruction):
        dest = instr.dest
        src = instr.args[0]
        self._emit_text(f"  # assign {dest.name} := {src.name}")
        self._load_operand_into(src, "$t0")
        self._store_var_from(dest.name, "$t0")

    # --- aritmética entera (add, sub, mul, div, mod)

    def _emit_arith(self, instr: Instruction):
        dest = instr.dest
        a, b = instr.args
        self._emit_text(f"  # {instr.opcode} {dest.name} = {a.name}, {b.name}")
        self._load_operand_into(a, "$t0")
        self._load_operand_into(b, "$t1")

        # Nota: si a/b son strings, esto realmente no tiene sentido;
        # lo dejamos como TODO. Tu IR probablemente ya evita esos casos
        # salvo para "concatenaciones", que podrías manejar aparte.
        if instr.opcode == "add":
            self._emit_text("  add  $t2, $t0, $t1")
        elif instr.opcode == "sub":
            self._emit_text("  sub  $t2, $t0, $t1")
        elif instr.opcode == "mul":
            self._emit_text("  mul  $t2, $t0, $t1")
        elif instr.opcode == "div":
            self._emit_text("  div  $t0, $t1")
            self._emit_text("  mflo $t2")
        elif instr.opcode == "mod":
            self._emit_text("  div  $t0, $t1")
            self._emit_text("  mfhi $t2")

        self._store_var_from(dest.name, "$t2")

    # --- comparaciones booleanas (lt, gt, le, ge, eq, ne)

    def _emit_cmp(self, instr: Instruction):
        dest = instr.dest
        a, b = instr.args
        self._emit_text(f"  # cmp {instr.opcode} {dest.name} = {a.name}, {b.name}")
        self._load_operand_into(a, "$t0")
        self._load_operand_into(b, "$t1")

        if instr.opcode == "lt":
            self._emit_text("  slt  $t2, $t0, $t1")
        elif instr.opcode == "gt":
            self._emit_text("  slt  $t2, $t1, $t0")
        elif instr.opcode == "le":
            self._emit_text("  slt  $t2, $t1, $t0")  # t2 = b<a
            self._emit_text("  xori $t2, $t2, 1")   # !t2
        elif instr.opcode == "ge":
            self._emit_text("  slt  $t2, $t0, $t1")  # t2 = a<b
            self._emit_text("  xori $t2, $t2, 1")    # !t2
        elif instr.opcode == "eq":
            self._emit_text("  sub  $t2, $t0, $t1")
            self._emit_text("  sltiu $t2, $t2, 1")   # 1 si t2 == 0
        elif instr.opcode == "ne":
            self._emit_text("  sub  $t2, $t0, $t1")
            self._emit_text("  sltu $t2, $zero, $t2")

        self._store_var_from(dest.name, "$t2")

    # --- branch cond, label_true, label_false

    def _emit_branch(self, instr: Instruction):
        cond, t_true, t_false = instr.args
        self._emit_text(f"  # branch {cond.name}, {t_true.name}, {t_false.name}")
        self._load_operand_into(cond, "$t0")
        self._emit_text(f"  bnez $t0, {t_true.name}")
        self._emit_text(f"  j    {t_false.name}")

    # --- jump label

    def _emit_jump(self, instr: Instruction):
        target = instr.args[0]
        self._emit_text(f"  # jump {target.name}")
        self._emit_text(f"  j    {target.name}")

    # --- print value (entero o string simplificados)

    def _emit_print(self, instr: Instruction):
        val = instr.args[0]
        self._emit_text(f"  # print {val.name}")

        # Heurística simple: si el operando es inmediato y string -> usar syscall 4
        if val.kind == "immediate" and (
            val.type_hint == "string" or isinstance(val.value, str)
        ):
            label = self._intern_string(str(val.value))
            self._emit_text(f"  la   $a0, {label}")
            self._emit_text("  li   $v0, 4      # syscall: print string")
            self._emit_text("  syscall")
        else:
            # Caso por defecto: entero
            self._load_operand_into(val, "$a0")
            # 🔧 OJO: aquí quitamos la palabra 'print_int'
            self._emit_text("  li   $v0, 1      # syscall: print integer")
            self._emit_text("  syscall")


    def _emit_array_new(self, instr: Instruction):
        dest = instr.dest
        size_op = instr.args[0]
        self._emit_text(f"  # array_new {dest.name}[{size_op.name}]")
        self._load_operand_into(size_op, "$a0")     # tamaño lógico
        self._emit_text("  jal  __cs_array_new")
        self._emit_text("  move $t0, $v0")
        self._store_var_from(dest.name, "$t0")

    def _emit_array_store(self, instr: Instruction):
        arr, idx, val = instr.args
        self._emit_text(f"  # array_store {arr.name}[{idx.name}] = {val.name}")
        self._load_operand_into(arr, "$t0")   # base ptr (elem0)
        self._load_operand_into(idx, "$t1")
        self._load_operand_into(val, "$t2")
        self._emit_text("  sll  $t1, $t1, 2       # index * 4")
        self._emit_text("  add  $t3, $t0, $t1")
        self._emit_text("  sw   $t2, 0($t3)")

    def _emit_array_index(self, instr: Instruction):
        dest = instr.dest
        arr, idx = instr.args
        self._emit_text(f"  # array_index {dest.name} = {arr.name}[{idx.name}]")
        self._load_operand_into(arr, "$t0")
        self._load_operand_into(idx, "$t1")
        self._emit_text("  sll  $t1, $t1, 2")
        self._emit_text("  add  $t3, $t0, $t1")
        self._emit_text("  lw   $t2, 0($t3)")
        self._store_var_from(dest.name, "$t2")

    def _emit_array_length(self, instr: Instruction):
        dest = instr.dest
        arr = instr.args[0]
        self._emit_text(f"  # array_length {dest.name} = len({arr.name})")
        self._load_operand_into(arr, "$t0")
        self._emit_text("  lw   $t1, -4($t0)      # length in header")
        self._emit_text("  move $t2, $t1")
        self._store_var_from(dest.name, "$t2")

    # --- Llamadas y métodos (muy simplificado) ---

    def _emit_call(self, instr: Instruction):
        dest = instr.dest
        func_op = instr.args[0]
        call_args = instr.args[1:]

        self._emit_text(
            f"  # call {func_op.name}(...), result -> {dest.name if dest else 'None'}"
        )

        # Paso de argumentos (hasta 4 en $a0-$a3)
        for i, arg in enumerate(call_args[:4]):
            self._load_operand_into(arg, f"$a{i}")

        # Llamada directa
        self._emit_text(f"  jal  {func_op.name}")

        if dest is not None:
            self._store_var_from(dest.name, "$v0")

    def _emit_field_load(self, instr: Instruction):
        dest = instr.dest
        obj, field_name = instr.args
        self._emit_text(
            f"  # field_load {dest.name} = {obj.name}.{field_name.value}"
        )
        self._emit_text("  # TODO: implementar layout de objetos / vtables reales")
        self._emit_text("  move $t0, $zero")
        self._store_var_from(dest.name, "$t0")

    # --- Try/catch como pseudo-ops (no hay raising real todavía) ---

    def _emit_try_catch(self, instr: Instruction):
        if instr.opcode == "begin_try":
            handler = instr.args[0]
            self._emit_text(f"  # begin_try handler={handler.name}")
            # Aquí podrías guardar handler en alguna estructura global/stack
        elif instr.opcode == "end_try":
            self._emit_text("  # end_try")
        elif instr.opcode == "begin_catch":
            self._emit_text("  # begin_catch")
        else:
            self._emit_text(f"  # unknown try/catch op {instr.opcode}")

    # --- return value? ---

    def _emit_return(self, instr: Instruction):
        if instr.args:
            val = instr.args[0]
            self._emit_text(f"  # return {val.name}")
            self._load_operand_into(val, "$v0")
        else:
            self._emit_text("  # return void")
        self._emit_epilogue()

    # -------------------------------------------------------------
    #  Runtime en MIPS (arrays)
    # -------------------------------------------------------------

    def _emit_runtime(self):
        """
        Implementación muy sencilla de __cs_array_new:

          Entrada:
            a0 = length (n)
          Hace:
            bytes = (n+1)*4
            syscall 9 (sbrk)
            [base] = n
            retorna base+4 en v0 (puntero a elem0)
        """
        self._emit_text("# --- runtime: __cs_array_new ---")
        self._emit_text("__cs_array_new:")
        self._emit_text("  addi $a0, $a0, 1       # length + 1 (header)")
        self._emit_text("  sll  $a0, $a0, 2       # * 4")
        self._emit_text("  li   $v0, 9           # sbrk")
        self._emit_text("  syscall")
        self._emit_text("  move $t0, $v0         # t0 = base")
        self._emit_text("  lw   $a1, 0($sp)      # opcional, aquí estaría length original si lo guardas")
        self._emit_text("  # Por simplicidad, asumimos que el length ya está en $a1")
        self._emit_text("  sw   $a1, 0($t0)      # header = length (muy simplificado)")
        self._emit_text("  addi $v0, $t0, 4      # v0 -> elem0")
        self._emit_text("  jr   $ra")
        self._emit_text("")
