from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..frontend import compat  # noqa: F401 ensures ANTLR compatibility
from ..frontend.generated.program.CompiscriptParser import CompiscriptParser
from ..frontend.generated.program.CompiscriptVisitor import CompiscriptVisitor
from ..tables.symbol_table import MemorySlot, SymbolTable
from ..semantics.symbols import ClassSymbol, FuncSymbol, VarSymbol
from .builder import IRBuilder
from .ir import BasicBlock, IRFunction, Operand


_TERMINATORS = {"return", "jump"}


@dataclass
class _LoopTarget:
    continue_label: str
    break_label: str


class IntermediateGenerator(CompiscriptVisitor):
    def __init__(self, *, builder: Optional[IRBuilder] = None) -> None:
        super().__init__()
        self.builder = builder or IRBuilder()
        self.symbols = SymbolTable()
        self._values: List[Dict[str, Operand]] = [dict()]
        self._loop_stack: List[_LoopTarget] = []
        self._label_counter = 0
        self._function_stack: List[Dict[str, Any]] = []
        self._class_stack: List[str] = []
        self._class_info_stack: List[Dict[str, Any]] = []

    def generate(self, tree: CompiscriptParser.ProgramContext) -> IRFunction:
        self._label_counter = 0
        self._values = [dict()]
        self._loop_stack = []
        self._push_scope(activation_name="main")
        function = self.builder.start_function("main", return_type="void")
        for statement in tree.statement():
            self.visit(statement)
        if not self._block_terminated():
            self.builder.emit_return()
        activation = self.symbols.current_activation()
        if activation:
            function.metadata["activation"] = activation.describe()
            slots = function.metadata["activation"].get("slots", {})
            for name, meta in getattr(function, "locals", {}).items():
                if name in slots:
                    slots[name]["const"] = meta.get("const", False)
        self.builder.end_function()
        self._pop_scope()
        return function

    def _push_scope(self, activation_name: Optional[str] = None, **activation_meta):
        self.symbols.push(activation_name=activation_name, **activation_meta)
        self._values.append({})

    def _pop_scope(self):
        if len(self._values) > 1:
            self._values.pop()
        self.symbols.pop()

    def _bind_operand(self, name: str, operand: Operand):
        self._values[-1][name] = operand

    def _resolve_operand(self, name: str) -> Operand:
        for scope in reversed(self._values):
            if name in scope:
                return scope[name]
        symbol = self.symbols.resolve(name)
        if isinstance(symbol, FuncSymbol):
            ir_name = getattr(symbol, "ir_name", symbol.name)
            return self.builder.identifier(ir_name, type_hint="function")
        if isinstance(symbol, ClassSymbol):
            return self.builder.identifier(symbol.name, type_hint="class")
        if isinstance(symbol, VarSymbol):
            slot = self.symbols.get_slot(name)
            if slot:
                operand = self.builder.identifier(slot.name, type_hint=slot.type_hint)
                self._values[-1][name] = operand
                return operand
        slot = self.symbols.get_slot(name)
        if slot:
            return self.builder.identifier(slot.name, type_hint=slot.type_hint)
        return self.builder.identifier(name)

    def _register_local(self, symbol: VarSymbol, slot: MemorySlot):
        function = self.builder.state.function
        if not function:
            return
        function.locals[symbol.name] = {
            "slot": slot.to_dict(),
            "const": symbol.is_const,
            "type": getattr(symbol, "type", None).name if getattr(symbol, "type", None) else None,
        }

    def _new_label(self, prefix: str) -> str:
        self._label_counter += 1
        return f"{prefix}_{self._label_counter}"

    def _block_terminated(self, block: Optional[BasicBlock] = None) -> bool:
        block = block or self.builder.state.block
        if not block or not block.instructions:
            return False
        return block.instructions[-1].opcode in _TERMINATORS

    def _release_operand(self, operand: Operand, *, keep: Optional[Operand] = None) -> None:
        if operand is keep:
            return
        if getattr(operand, "kind", None) == "temp":
            self.builder.release_temp(operand)

    @contextmanager
    def _in_block(self, block: BasicBlock):
        previous = self.builder.state.block
        self.builder.position_at_end(block)
        try:
            yield
        finally:
            self.builder.position_at_end(block)

    def _current_class_info(self) -> Optional[Dict[str, Any]]:
        return self._class_info_stack[-1] if self._class_info_stack else None

    @contextmanager
    def _function_definition(
        self,
        internal_name: str,
        param_specs: List[Dict[str, Any]],
        return_type: Optional[str],
        *,
        attributes: Optional[Dict[str, Any]] = None,
        activation_meta: Optional[Dict[str, Any]] = None,
    ):
        prev_function = self.builder.state.function
        prev_block = self.builder.state.block
        prev_loop_stack = list(self._loop_stack)
        self._push_scope(activation_name=internal_name, **(activation_meta or {}))
        function = self.builder.start_function(
            internal_name,
            params=[spec["name"] for spec in param_specs],
            return_type=return_type,
            attributes=attributes,
        )
        context = {"name": internal_name, "return_type": return_type, "attributes": attributes or {}}
        self._function_stack.append(context)
        try:
            yield function
        finally:
            activation = self.symbols.current_activation()
            if activation:
                function.metadata["activation"] = activation.describe()
                slots = function.metadata["activation"].get("slots", {})
                for name, meta in getattr(function, "locals", {}).items():
                    if name in slots:
                        slots[name]["const"] = meta.get("const", False)
            self._function_stack.pop()
            self._pop_scope()
            self.builder.end_function()
            self.builder.state.function = prev_function
            if prev_block is not None:
                self.builder.position_at_end(prev_block)
            else:
                self.builder.state.block = None
            self._loop_stack = prev_loop_stack

    def _bind_parameters(self, param_specs: List[Dict[str, Any]]):
        for spec in param_specs:
            name = spec["name"]
            type_hint = spec.get("type")
            role = spec.get("role", "param")
            symbol = VarSymbol(name=name, type=None, is_const=spec.get("const", False))
            self.symbols.define(symbol)
            slot = self.symbols.reserve_slot(name, role=role, type_hint=type_hint)
            operand = self.builder.identifier(slot.name, type_hint=type_hint)
            self._bind_operand(name, operand)
            self._register_local(symbol, slot)
            spec["slot"] = slot.to_dict()

    def _emit_property_access(self, target: Operand, prop: str) -> Operand:
        dest = self.builder.temporary(type_hint=None)
        self.builder.emit(
            "field_load",
            dest=dest,
            args=[target, self.builder.literal(prop, type_hint="string")],
        )
        return dest

    def _emit_index_access(self, target: Operand, index: Operand) -> Operand:
        dest = self.builder.temporary(type_hint=None)
        self.builder.emit("array_index", dest=dest, args=[target, index])
        self._release_operand(index)
        return dest

    def _emit_property_store(self, target: Operand, prop: str, value: Operand) -> Operand:
        self.builder.emit(
            "field_store",
            args=[target, self.builder.literal(prop, type_hint="string"), value],
        )
        return value

    def _emit_index_store(self, target: Operand, index: Operand, value: Operand) -> Operand:
        self.builder.emit("array_store", args=[target, index, value])
        self._release_operand(index)
        return value

    def _evaluate_left_hand_side(self, lhs: CompiscriptParser.LeftHandSideContext) -> tuple[Operand, Optional[Any]]:
        target = self.visit(lhs.primaryAtom())
        suffixes = list(lhs.suffixOp() or [])
        for suffix in suffixes[:-1]:
            if isinstance(suffix, CompiscriptParser.CallExprContext):
                args = []
                if suffix.arguments():
                    args = [self.visit(exp) for exp in suffix.arguments().expression()]
                result = self.builder.emit_call(target, args, comment="call")
                for arg in args:
                    self._release_operand(arg)
                self._release_operand(target, keep=result)
                target = result
            elif isinstance(suffix, CompiscriptParser.PropertyAccessExprContext):
                prop = suffix.Identifier().getText()
                result = self._emit_property_access(target, prop)
                self._release_operand(target, keep=result)
                target = result
            elif isinstance(suffix, CompiscriptParser.IndexExprContext):
                index = self.visit(suffix.expression())
                result = self._emit_index_access(target, index)
                self._release_operand(target, keep=result)
                target = result
        last = suffixes[-1] if suffixes else None
        return target, last

    def _type_text(self, node) -> Optional[str]:
        if node is None:
            return None
        getter = None
        if hasattr(node, "type"):
            getter = getattr(node, "type")
        elif hasattr(node, "type_"):
            getter = getattr(node, "type_")
        if getter is None:
            return None
        type_ctx = getter()
        return type_ctx.getText() if type_ctx else None

    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        self._push_scope()
        for statement in ctx.statement():
            self.visit(statement)
        self._pop_scope()

    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        name = ctx.Identifier().getText()
        type_hint = ctx.typeAnnotation().getText() if ctx.typeAnnotation() else None
        symbol = VarSymbol(name=name, type=None, is_const=False)
        if self._class_stack and not self._function_stack:
            class_symbol = self.symbols.resolve(self._class_stack[-1])
            if isinstance(class_symbol, ClassSymbol):
                class_symbol.define_member(symbol)
            class_info = self._current_class_info()
            if class_info is not None:
                default_value = None
                if ctx.initializer():
                    default_value = ctx.initializer().expression().getText()
                class_info.setdefault("fields", {})[name] = {
                    "type": type_hint,
                    "const": False,
                    "default": default_value,
                }
            return
        self.symbols.define(symbol)
        slot = self.symbols.reserve_slot(name, role="local", type_hint=type_hint)
        operand = self.builder.identifier(slot.name, type_hint=type_hint)
        self._bind_operand(name, operand)
        self._register_local(symbol, slot)
        if ctx.initializer():
            value = self.visit(ctx.initializer().expression())
            self.builder.emit_assign(operand, value, comment=f"init {name}")
            self._release_operand(value)

    def visitConstantDeclaration(self, ctx: CompiscriptParser.ConstantDeclarationContext):
        name = ctx.Identifier().getText()
        type_hint = ctx.typeAnnotation().getText() if ctx.typeAnnotation() else None
        symbol = VarSymbol(name=name, type=None, is_const=True)
        if self._class_stack and not self._function_stack:
            class_symbol = self.symbols.resolve(self._class_stack[-1])
            if isinstance(class_symbol, ClassSymbol):
                class_symbol.define_member(symbol)
            class_info = self._current_class_info()
            if class_info is not None:
                class_info.setdefault("fields", {})[name] = {
                    "type": type_hint,
                    "const": True,
                    "default": ctx.expression().getText(),
                }
            return
        self.symbols.define(symbol)
        slot = self.symbols.reserve_slot(name, role="const", type_hint=type_hint)
        operand = self.builder.identifier(slot.name, type_hint=type_hint)
        self._bind_operand(name, operand)
        self._register_local(symbol, slot)
        value = self.visit(ctx.expression())
        self.builder.emit_assign(operand, value, comment=f"const {name}")
        self._release_operand(value)

    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        name = ctx.Identifier().getText()
        return_type = self._type_text(ctx)
        is_method = bool(self._class_stack)
        class_name = self._class_stack[-1] if is_method else None
        internal_name = f"{class_name}.{name}" if class_name else name
        if not is_method and self._function_stack:
            parent = self._function_stack[-1]["name"]
            internal_name = f"{parent}.{name}"
        param_specs: List[Dict[str, Any]] = []
        if is_method:
            param_specs.append({"name": "this", "type": class_name, "role": "this", "const": True})
        if ctx.parameters():
            for param in ctx.parameters().parameter():
                pname = param.Identifier().getText()
                ptype = self._type_text(param)
                param_specs.append({"name": pname, "type": ptype, "role": "param"})
        attributes = {"kind": "method" if is_method else "function"}
        activation_meta = {"kind": attributes["kind"], "name": internal_name}
        if class_name:
            attributes["class"] = class_name
            attributes["method"] = name
            activation_meta["class"] = class_name
            if name == "constructor":
                attributes["constructor"] = True
                activation_meta["constructor"] = True
        if is_method:
            class_symbol = self.symbols.resolve(class_name)
            if isinstance(class_symbol, ClassSymbol):
                method_symbol = FuncSymbol(name=name, params=[], return_type=None)
                setattr(method_symbol, "ir_name", internal_name)
                class_symbol.define_member(method_symbol)
            class_info = self._current_class_info()
            if class_info is not None:
                methods = class_info.setdefault("methods", {})
                methods[name] = {
                    "ir_name": internal_name,
                    "params": [spec["name"] for spec in param_specs if spec["name"] != "this"],
                    "return": return_type,
                }
        else:
            func_symbol = FuncSymbol(name=name, params=[], return_type=None)
            setattr(func_symbol, "ir_name", internal_name)
            self.symbols.define(func_symbol)
            self.symbols.update(name, ir_name=internal_name, return_type=return_type)
            self._bind_operand(name, self.builder.identifier(internal_name, type_hint="function"))
        with self._function_definition(
            internal_name,
            param_specs,
            return_type,
            attributes=attributes,
            activation_meta=activation_meta,
        ) as function:
            self._bind_parameters(param_specs)
            function.metadata["params"] = [
                {key: spec[key] for key in ("name", "type", "role", "slot") if key in spec}
                for spec in param_specs
            ]
            function.metadata.update(attributes)
            self.visit(ctx.block())
            if not self._block_terminated():
                if attributes.get("constructor"):
                    self.builder.emit_return(self._resolve_operand("this"))
                else:
                    self.builder.emit_return()
        return self.builder.module.get_function(internal_name)

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        name = ctx.Identifier(0).getText()
        base = ctx.Identifier(1).getText() if ctx.Identifier(1) else None
        class_symbol = ClassSymbol(name)
        self.symbols.define(class_symbol)
        class_info = {
            "kind": "class",
            "name": name,
            "parent": base,
            "fields": {},
            "methods": {},
        }
        self.builder.module.globals[name] = class_info
        self._class_stack.append(name)
        self._class_info_stack.append(class_info)
        try:
            for member in ctx.classMember():
                self.visit(member)
        finally:
            self._class_info_stack.pop()
            self._class_stack.pop()
        return class_info

    def visitAssignment(self, ctx: CompiscriptParser.AssignmentContext):
        if ctx.Identifier() and len(ctx.expression()) == 1:
            name = ctx.Identifier().getText()
            expr = ctx.expression()
            if isinstance(expr, list):
                expr = expr[-1]
            value = self.visit(expr)
            self._emit_assignment(name, value)
        else:
            receiver = self.visit(ctx.expression(0))
            value = self.visit(ctx.expression(1))
            result = self._emit_property_store(receiver, ctx.Identifier().getText(), value)
            self._release_operand(receiver)
            self._release_operand(result)

    def visitExpressionStatement(self, ctx: CompiscriptParser.ExpressionStatementContext):
        self.visit(ctx.expression())

    def visitPrintStatement(self, ctx: CompiscriptParser.PrintStatementContext):
        value = self.visit(ctx.expression())
        self.builder.emit("print", args=[value], comment="print")
        self._release_operand(value)

    def visitReturnStatement(self, ctx: CompiscriptParser.ReturnStatementContext):
        if ctx.expression():
            value = self.visit(ctx.expression())
            self.builder.emit_return(value)
        else:
            self.builder.emit_return()

    def visitIfStatement(self, ctx: CompiscriptParser.IfStatementContext):
        condition = self.visit(ctx.expression())
        true_label = self._new_label("if_true")
        end_label = self._new_label("if_end")
        if ctx.block(1):
            false_label = self._new_label("if_false")
            self.builder.emit_branch(condition, true_label, false_label)
            self._release_operand(condition)
            true_block = self.builder.new_block(true_label)
            with self._in_block(true_block):
                self.visit(ctx.block(0))
                if not self._block_terminated(true_block):
                    self.builder.emit_jump(end_label)
            false_block = self.builder.new_block(false_label)
            with self._in_block(false_block):
                self.visit(ctx.block(1))
                if not self._block_terminated(false_block):
                    self.builder.emit_jump(end_label)
            end_block = self.builder.new_block(end_label)
            self.builder.position_at_end(end_block)
        else:
            self.builder.emit_branch(condition, true_label, end_label)
            self._release_operand(condition)
            true_block = self.builder.new_block(true_label)
            with self._in_block(true_block):
                self.visit(ctx.block(0))
                if not self._block_terminated(true_block):
                    self.builder.emit_jump(end_label)
            end_block = self.builder.new_block(end_label)
            self.builder.position_at_end(end_block)

    def visitWhileStatement(self, ctx: CompiscriptParser.WhileStatementContext):
        cond_label = self._new_label("while_cond")
        body_label = self._new_label("while_body")
        end_label = self._new_label("while_end")
        self.builder.emit_jump(cond_label)
        cond_block = self.builder.new_block(cond_label)
        with self._in_block(cond_block):
            condition = self.visit(ctx.expression())
            self.builder.emit_branch(condition, body_label, end_label)
            self._release_operand(condition)
        body_block = self.builder.new_block(body_label)
        self._loop_stack.append(_LoopTarget(continue_label=cond_label, break_label=end_label))
        with self._in_block(body_block):
            self.visit(ctx.block())
            if not self._block_terminated(body_block):
                self.builder.emit_jump(cond_label)
        self._loop_stack.pop()
        end_block = self.builder.new_block(end_label)
        self.builder.position_at_end(end_block)

    def visitDoWhileStatement(self, ctx: CompiscriptParser.DoWhileStatementContext):
        body_label = self._new_label("do_body")
        test_label = self._new_label("do_test")
        end_label = self._new_label("do_end")
        body_block = self.builder.new_block(body_label)
        self.builder.position_at_end(body_block)
        self._loop_stack.append(_LoopTarget(continue_label=test_label, break_label=end_label))
        with self._in_block(body_block):
            self.visit(ctx.block())
            if not self._block_terminated(body_block):
                self.builder.emit_jump(test_label)
        self._loop_stack.pop()
        test_block = self.builder.new_block(test_label)
        with self._in_block(test_block):
            condition = self.visit(ctx.expression())
            self.builder.emit_branch(condition, body_label, end_label)
            self._release_operand(condition)
        end_block = self.builder.new_block(end_label)
        self.builder.position_at_end(end_block)

    def visitForStatement(self, ctx: CompiscriptParser.ForStatementContext):
        self._push_scope()
        try:
            init = ctx.variableDeclaration() or ctx.assignment()
            if init:
                self.visit(init)
            cond_label = self._new_label("for_cond")
            body_label = self._new_label("for_body")
            step_label = self._new_label("for_step")
            end_label = self._new_label("for_end")
            self.builder.emit_jump(cond_label)
            cond_block = self.builder.new_block(cond_label)
            with self._in_block(cond_block):
                if ctx.expression(0):
                    condition = self.visit(ctx.expression(0))
                    self.builder.emit_branch(condition, body_label, end_label)
                    self._release_operand(condition)
                else:
                    self.builder.emit_jump(body_label)
            body_block = self.builder.new_block(body_label)
            self._loop_stack.append(_LoopTarget(continue_label=step_label, break_label=end_label))
            with self._in_block(body_block):
                self.visit(ctx.block())
                if not self._block_terminated(body_block):
                    self.builder.emit_jump(step_label)
            self._loop_stack.pop()
            step_block = self.builder.new_block(step_label)
            with self._in_block(step_block):
                if ctx.expression(1):
                    step = self.visit(ctx.expression(1))
                    self._release_operand(step)
                if not self._block_terminated(step_block):
                    self.builder.emit_jump(cond_label)
            end_block = self.builder.new_block(end_label)
            self.builder.position_at_end(end_block)
        finally:
            self._pop_scope()

    def visitForeachStatement(self, ctx: CompiscriptParser.ForeachStatementContext):
        iter_var = ctx.Identifier().getText()
        array = self.visit(ctx.expression())
        index_name = f"_idx_{self._label_counter}"
        self._label_counter += 1
        index_symbol = VarSymbol(name=index_name, type=None, is_const=False)
        self.symbols.define(index_symbol)
        slot = self.symbols.reserve_slot(index_name, role="local", type_hint="integer")
        index = self.builder.identifier(slot.name, type_hint="integer")
        self._bind_operand(index_name, index)
        zero = self.builder.literal(0, type_hint="integer")
        self.builder.emit_assign(index, zero)
        length = self.builder.temporary(type_hint="integer")
        self.builder.emit("array_length", dest=length, args=[array])
        cond_label = self._new_label("foreach_cond")
        body_label = self._new_label("foreach_body")
        incr_label = self._new_label("foreach_incr")
        end_label = self._new_label("foreach_end")
        self.builder.emit_jump(cond_label)
        cond_block = self.builder.new_block(cond_label)
        with self._in_block(cond_block):
            condition = self.builder.emit_binary("lt", index, length, type_hint="boolean")
            self.builder.emit_branch(condition, body_label, end_label)
            self._release_operand(condition)
        body_block = self.builder.new_block(body_label)
        self._loop_stack.append(_LoopTarget(continue_label=incr_label, break_label=end_label))
        with self._in_block(body_block):
            iter_symbol = VarSymbol(name=iter_var, type=None, is_const=False)
            self.symbols.define(iter_symbol)
            iter_slot = self.symbols.reserve_slot(iter_var, role="local", type_hint=None)
            iter_operand = self.builder.identifier(iter_slot.name)
            self._bind_operand(iter_var, iter_operand)
            element = self._emit_index_access(array, index)
            self.builder.emit_assign(iter_operand, element)
            self._release_operand(element)
            self.visit(ctx.block())
            if not self._block_terminated(body_block):
                self.builder.emit_jump(incr_label)
        self._loop_stack.pop()
        incr_block = self.builder.new_block(incr_label)
        with self._in_block(incr_block):
            one = self.builder.literal(1, type_hint="integer")
            new_index = self.builder.emit_binary("add", index, one, type_hint="integer")
            self.builder.emit_assign(index, new_index)
            self._release_operand(new_index)
            self.builder.emit_jump(cond_label)
        end_block = self.builder.new_block(end_label)
        self.builder.position_at_end(end_block)

    def visitBreakStatement(self, ctx: CompiscriptParser.BreakStatementContext):
        if not self._loop_stack:
            raise RuntimeError("'break' fuera de un bucle")
        target = self._loop_stack[-1].break_label
        self.builder.emit_jump(target)

    def visitContinueStatement(self, ctx: CompiscriptParser.ContinueStatementContext):
        if not self._loop_stack:
            raise RuntimeError("'continue' fuera de un bucle")
        target = self._loop_stack[-1].continue_label
        self.builder.emit_jump(target)

    def visitSwitchStatement(self, ctx: CompiscriptParser.SwitchStatementContext):
        switch_value = self.visit(ctx.expression())
        end_label = self._new_label("switch_end")
        default_ctx = ctx.defaultCase()
        default_label = self._new_label("switch_default") if default_ctx else end_label
        dispatch_label = self._new_label("switch_cmp")
        self.builder.emit_jump(dispatch_label)
        dispatch_block = self.builder.new_block(dispatch_label)
        cases = list(ctx.switchCase())
        for index, case_ctx in enumerate(cases):
            true_label = self._new_label("switch_case")
            has_more = index < len(cases) - 1
            need_fallthrough = has_more or default_ctx
            false_label = self._new_label("switch_cmp") if need_fallthrough else end_label
            with self._in_block(dispatch_block):
                case_value = self.visit(case_ctx.expression())
                cmp_result = self.builder.emit_binary("eq", switch_value, case_value, type_hint="boolean")
                self._release_operand(case_value)
                self.builder.emit_branch(cmp_result, true_label, false_label)
                self._release_operand(cmp_result)
            case_block = self.builder.new_block(true_label)
            with self._in_block(case_block):
                for statement in case_ctx.statement():
                    self.visit(statement)
                if not self._block_terminated(case_block):
                    self.builder.emit_jump(end_label)
            if need_fallthrough:
                dispatch_block = self.builder.new_block(false_label)
            else:
                dispatch_block = None
                break
        if default_ctx and dispatch_block is not None:
            with self._in_block(dispatch_block):
                self._push_scope()
                try:
                    for statement in default_ctx.statement():
                        self.visit(statement)
                finally:
                    self._pop_scope()
                if not self._block_terminated(dispatch_block):
                    self.builder.emit_jump(end_label)
        elif dispatch_block is not None:
            with self._in_block(dispatch_block):
                if not self._block_terminated(dispatch_block):
                    self.builder.emit_jump(end_label)
        end_block = self.builder.new_block(end_label)
        self.builder.position_at_end(end_block)
        self._release_operand(switch_value)

    def visitTryCatchStatement(self, ctx: CompiscriptParser.TryCatchStatementContext):
        try_label = self._new_label("try_body")
        catch_label = self._new_label("try_handler")
        end_label = self._new_label("try_end")
        self.builder.emit(
            "begin_try",
            args=[self.builder.identifier(catch_label, type_hint="label")],
            comment="try",
        )
        self.builder.emit_jump(try_label)
        try_block = self.builder.new_block(try_label)
        with self._in_block(try_block):
            for statement in ctx.block(0).statement():
                self.visit(statement)
            if not self._block_terminated(try_block):
                self.builder.emit("end_try")
                self.builder.emit_jump(end_label)
        catch_block = self.builder.new_block(catch_label)
        with self._in_block(catch_block):
            catcher = self.builder.temporary(type_hint="exception")
            self.builder.emit("begin_catch", dest=catcher)
            self._push_scope()
            try:
                name = ctx.Identifier().getText()
                symbol = VarSymbol(name=name, type=None, is_const=False)
                self.symbols.define(symbol)
                slot = self.symbols.reserve_slot(name, role="local", type_hint="exception")
                operand = self.builder.identifier(slot.name, type_hint="exception")
                self._bind_operand(name, operand)
                self._register_local(symbol, slot)
                self.builder.emit_assign(operand, catcher, comment="catch bind")
                for statement in ctx.block(1).statement():
                    self.visit(statement)
            finally:
                self._pop_scope()
            if not self._block_terminated(catch_block):
                self.builder.emit_jump(end_label)
        self._release_operand(catcher)
        end_block = self.builder.new_block(end_label)
        self.builder.position_at_end(end_block)

    def visitExpression(self, ctx: CompiscriptParser.ExpressionContext):
        return self.visit(ctx.assignmentExpr())

    def visitAssignExpr(self, ctx: CompiscriptParser.AssignExprContext):
        value = self.visit(ctx.assignmentExpr())
        target, last_suffix = self._evaluate_left_hand_side(ctx.lhs)
        if last_suffix is None:
            comment = f"assign {ctx.lhs.getText()}"
            self.builder.emit_assign(target, value, comment=comment)
            return target
        if isinstance(last_suffix, CompiscriptParser.PropertyAccessExprContext):
            result = self._emit_property_store(target, last_suffix.Identifier().getText(), value)
            self._release_operand(target)
            return result
        if isinstance(last_suffix, CompiscriptParser.IndexExprContext):
            index = self.visit(last_suffix.expression())
            result = self._emit_index_store(target, index, value)
            self._release_operand(target)
            return result
        raise NotImplementedError("Tipo de asignación no soportado")

    def visitExprNoAssign(self, ctx: CompiscriptParser.ExprNoAssignContext):
        return self.visit(ctx.conditionalExpr())

    def visitTernaryExpr(self, ctx: CompiscriptParser.TernaryExprContext):
        logical = self.visit(ctx.logicalOrExpr())
        if not ctx.expression():
            return logical
        true_label = self._new_label("ternary_true")
        false_label = self._new_label("ternary_false")
        end_label = self._new_label("ternary_end")
        result = self.builder.temporary()
        self.builder.emit_branch(logical, true_label, false_label)
        self._release_operand(logical)
        true_block = self.builder.new_block(true_label)
        with self._in_block(true_block):
            true_value = self.visit(ctx.expression(0))
            self.builder.emit_assign(result, true_value)
            self._release_operand(true_value)
            if not self._block_terminated(true_block):
                self.builder.emit_jump(end_label)
        false_block = self.builder.new_block(false_label)
        with self._in_block(false_block):
            false_value = self.visit(ctx.expression(1))
            self.builder.emit_assign(result, false_value)
            self._release_operand(false_value)
            if not self._block_terminated(false_block):
                self.builder.emit_jump(end_label)
        end_block = self.builder.new_block(end_label)
        self.builder.position_at_end(end_block)
        return result

    def visitConditionalExpr(self, ctx: CompiscriptParser.ConditionalExprContext):
        logical = self.visit(ctx.logicalOrExpr())
        if not ctx.expression():
            return logical
        true_label = self._new_label("ternary_true")
        false_label = self._new_label("ternary_false")
        end_label = self._new_label("ternary_end")
        result = self.builder.temporary()
        self.builder.emit_branch(logical, true_label, false_label)
        self._release_operand(logical)
        true_block = self.builder.new_block(true_label)
        with self._in_block(true_block):
            true_value = self.visit(ctx.expression(0))
            self.builder.emit_assign(result, true_value)
            self._release_operand(true_value)
            if not self._block_terminated(true_block):
                self.builder.emit_jump(end_label)
        false_block = self.builder.new_block(false_label)
        with self._in_block(false_block):
            false_value = self.visit(ctx.expression(1))
            self.builder.emit_assign(result, false_value)
            self._release_operand(false_value)
            if not self._block_terminated(false_block):
                self.builder.emit_jump(end_label)
        end_block = self.builder.new_block(end_label)
        self.builder.position_at_end(end_block)
        return result

    def visitLogicalOrExpr(self, ctx: CompiscriptParser.LogicalOrExprContext):
        value = self.visit(ctx.logicalAndExpr(0))
        for expr in ctx.logicalAndExpr()[1:]:
            rhs = self.visit(expr)
            result = self.builder.emit_binary("or", value, rhs, type_hint="boolean")
            self._release_operand(rhs)
            self._release_operand(value, keep=result)
            value = result
        return value

    def visitLogicalAndExpr(self, ctx: CompiscriptParser.LogicalAndExprContext):
        value = self.visit(ctx.equalityExpr(0))
        for expr in ctx.equalityExpr()[1:]:
            rhs = self.visit(expr)
            result = self.builder.emit_binary("and", value, rhs, type_hint="boolean")
            self._release_operand(rhs)
            self._release_operand(value, keep=result)
            value = result
        return value

    def visitEqualityExpr(self, ctx: CompiscriptParser.EqualityExprContext):
        value = self.visit(ctx.relationalExpr(0))
        children = ctx.relationalExpr()
        for index in range(1, len(children)):
            rhs = self.visit(children[index])
            op = ctx.children[2 * index - 1].getText()
            opcode = "eq" if op == "==" else "ne"
            result = self.builder.emit_binary(opcode, value, rhs, type_hint="boolean")
            self._release_operand(rhs)
            self._release_operand(value, keep=result)
            value = result
        return value

    def visitRelationalExpr(self, ctx: CompiscriptParser.RelationalExprContext):
        value = self.visit(ctx.additiveExpr(0))
        children = ctx.additiveExpr()
        for index in range(1, len(children)):
            rhs = self.visit(children[index])
            op = ctx.children[2 * index - 1].getText()
            opcode = {
                "<": "lt",
                "<=": "le",
                ">": "gt",
                ">=": "ge",
            }[op]
            result = self.builder.emit_binary(opcode, value, rhs, type_hint="boolean")
            self._release_operand(rhs)
            self._release_operand(value, keep=result)
            value = result
        return value

    def visitAdditiveExpr(self, ctx: CompiscriptParser.AdditiveExprContext):
        value = self.visit(ctx.multiplicativeExpr(0))
        children = ctx.multiplicativeExpr()
        for index in range(1, len(children)):
            rhs = self.visit(children[index])
            op = ctx.children[2 * index - 1].getText()
            opcode = "add" if op == "+" else "sub"
            result = self.builder.emit_binary(opcode, value, rhs, type_hint="integer")
            self._release_operand(rhs)
            self._release_operand(value, keep=result)
            value = result
        return value

    def visitMultiplicativeExpr(self, ctx: CompiscriptParser.MultiplicativeExprContext):
        value = self.visit(ctx.unaryExpr(0))
        children = ctx.unaryExpr()
        for index in range(1, len(children)):
            rhs = self.visit(children[index])
            op = ctx.children[2 * index - 1].getText()
            opcode = {
                "*": "mul",
                "/": "div",
                "%": "mod",
            }[op]
            result = self.builder.emit_binary(opcode, value, rhs, type_hint="integer")
            self._release_operand(rhs)
            self._release_operand(value, keep=result)
            value = result
        return value

    def visitUnaryExpr(self, ctx: CompiscriptParser.UnaryExprContext):
        if ctx.getChildCount() == 2:
            op = ctx.getChild(0).getText()
            operand = self.visit(ctx.unaryExpr())
            opcode = "not" if op == "!" else "neg"
            type_hint = "boolean" if op == "!" else "integer"
            result = self.builder.emit_unary(opcode, operand, type_hint=type_hint)
            self._release_operand(operand, keep=result)
            return result
        return self.visit(ctx.primaryExpr())

    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext):
        if ctx.literalExpr():
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide():
            return self.visit(ctx.leftHandSide())
        if ctx.expression():
            return self.visit(ctx.expression())
        raise NotImplementedError("Expresión primaria no soportada")

    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext):
        token = ctx.Literal()
        if token:
            text = token.getText()
            if text.startswith('"') and text.endswith('"'):
                value = text[1:-1]
                return self.builder.literal(value, type_hint="string")
            return self.builder.literal(int(text), type_hint="integer")
        text = ctx.getText()
        if text == "true":
            return self.builder.literal(True, type_hint="boolean")
        if text == "false":
            return self.builder.literal(False, type_hint="boolean")
        if text == "null":
            return self.builder.literal(None, type_hint="null")
        if ctx.arrayLiteral():
            values = [self.visit(exp) for exp in ctx.arrayLiteral().expression()]
            dest = self.builder.temporary(type_hint="array")
            size = self.builder.literal(len(values), type_hint="integer")
            self.builder.emit("array_new", dest=dest, args=[size], comment=f"array[{len(values)}]")
            for idx, val in enumerate(values):
                index = self.builder.literal(idx, type_hint="integer")
                self.builder.emit("array_store", args=[dest, index, val], comment=f"arr[{idx}] = value")
                self._release_operand(val)
            return dest
        raise NotImplementedError("Literal no soportado")

    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        value = self.visit(ctx.primaryAtom())
        for suffix in ctx.suffixOp() or []:
            if isinstance(suffix, CompiscriptParser.CallExprContext):
                args = []
                if suffix.arguments():
                    args = [self.visit(exp) for exp in suffix.arguments().expression()]
                value = self.builder.emit_call(value, args, comment="call")
                for a in args:
                    self._release_operand(a)
            elif isinstance(suffix, CompiscriptParser.PropertyAccessExprContext):
                prop = suffix.Identifier().getText()
                value = self._emit_property_access(value, prop)
            elif isinstance(suffix, CompiscriptParser.IndexExprContext):
                index = self.visit(suffix.expression())
                value = self._emit_index_access(value, index)
        return value

    def visitIdentifierExpr(self, ctx: CompiscriptParser.IdentifierExprContext):
        name = ctx.Identifier().getText()
        return self._resolve_operand(name)

    def visitNewExpr(self, ctx: CompiscriptParser.NewExprContext):
        class_name = ctx.Identifier().getText()
        args = []
        if ctx.arguments():
            args = [self.visit(exp) for exp in ctx.arguments().expression()]
        callee = self.builder.identifier(f"{class_name}.constructor", type_hint="function")
        result = self.builder.emit_call(callee, args, comment=f"new {class_name}")
        for a in args:
            self._release_operand(a)
        return result

    def visitThisExpr(self, ctx: CompiscriptParser.ThisExprContext):
        return self._resolve_operand("this")

    def _emit_assignment(self, name: str, value: Operand) -> Operand:
        target = self._resolve_operand(name)
        self.builder.emit_assign(target, value, comment=f"assign {name}")
        self._release_operand(value)
        return target
