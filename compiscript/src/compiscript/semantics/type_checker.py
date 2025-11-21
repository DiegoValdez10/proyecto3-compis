from ..frontend.generated.program.CompiscriptParser import CompiscriptParser
from ..frontend.generated.program.CompiscriptVisitor import CompiscriptVisitor
from ..tables.symbol_table import SymbolTable
from .diagnostics import DiagBag
from .proclog import ProcLog
from .symbols import VarSymbol, FuncSymbol, ClassSymbol
from .typesys import (
    Integer, String, Boolean, Null,
    ArrayType, from_type_name, from_type_rule,
    is_numeric, is_array, elem_type, same, Type
)


class TypeChecker(CompiscriptVisitor):
    def __init__(self, logger=None):
        super().__init__()
        self.log = logger or ProcLog()
        self.syms = SymbolTable(logger=self.log)
        self.diag = DiagBag()
        self.loop_depth = 0
        self.func_stack: list[FuncSymbol | None] = []
        self.class_stack: list[ClassSymbol | None] = []
        self._in_class_block = False

    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        self.log.step("Typecheck: inicio")
        for st in ctx.statement():
            kind = st.getChild(0).getText()
            self.log.info(f"— Instrucción: {kind}")
            self.visit(st)
        ok = self.diag.ok()
        if ok:
            self.log.ok("Typecheck finalizado sin errores")
        else:
            self.log.err("Typecheck finalizado con errores")
        return self.diag

    def _get_class_from_type(self, t):
        if isinstance(t, Type) and (t not in (Integer, String, Boolean, Null)) and not is_array(t):
            cs = self.syms.resolve(t.name)
            if isinstance(cs, ClassSymbol):
                return cs
        return None

    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        self.log.step("Entrar a bloque")
        self.syms.push()
        terminated = False
        for st in list(ctx.statement()):
            if terminated:
                self.log.info("Código muerto tras instrucción que termina flujo")
                self.diag.warn(
                    "DC01",
                    "Código inalcanzable tras instrucción previa que termina el flujo",
                    st.start,
                )
            term = self.visit(st)
            terminated = terminated or bool(term)
        self.syms.pop()
        self.log.step("Salir de bloque")
        return terminated

    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        name_tok = ctx.Identifier().getSymbol()
        name = name_tok.text
        self.log.info(f"Declaración variable '{name}'")
        t = from_type_rule(ctx.typeAnnotation().type_()) if ctx.typeAnnotation() else None
        if ctx.initializer():
            et = self.visit(ctx.initializer().expression())
            self.log.info(f"  tipo init: {et}, declarado: {t}")
            if t is None:
                t = et
            else:
                if et and not same(t, et):
                    self.diag.err("E101", f"Tipo incompatible en inicialización: {t} <- {et}", name_tok)
                    self.log.err("  incompatibilidad en inicialización")
        else:
            if t is None:
                self.diag.err("E102", f"Variable '{name}' requiere tipo o inicializador", name_tok)
                self.log.err("  falta tipo e inicializador")
                return
        sym = VarSymbol(name=name, type=t, is_const=False)
        if self.class_stack and self.class_stack[-1] is not None and self._in_class_block:
            cls = self.class_stack[-1]
            if not cls.define_member(sym):
                self.diag.err("E030", f"Redeclaración de miembro '{name}' en clase '{cls.name}'", name_tok)
                self.log.err(f"  redeclaración en clase {cls.name}")
        if not self.syms.define(sym):
            self.diag.err("E030", f"Redeclaración en el mismo ámbito: '{name}'", name_tok)
            self.log.err("  redeclaración en mismo ámbito")

    def visitConstantDeclaration(self, ctx: CompiscriptParser.ConstantDeclarationContext):
        name_tok = ctx.Identifier().getSymbol()
        name = name_tok.text
        self.log.info(f"Declaración const '{name}'")
        if ctx.expression() is None:
            self.diag.err("E110", f"Const '{name}' debe inicializarse", name_tok)
            self.log.err("  const sin inicializador")
            return
        t = from_type_rule(ctx.typeAnnotation().type_()) if ctx.typeAnnotation() else None
        et = self.visit(ctx.expression())
        self.log.info(f"  tipo init: {et}, declarado: {t}")
        if t is None:
            t = et
        else:
            if et and not same(t, et):
                self.diag.err("E101", f"Tipo incompatible en const: {t} <- {et}", name_tok)
                self.log.err("  incompatibilidad en inicialización const")
        sym = VarSymbol(name=name, type=t, is_const=True)
        if self.class_stack and self.class_stack[-1] is not None and self._in_class_block:
            cls = self.class_stack[-1]
            if not cls.define_member(sym):
                self.diag.err("E030", f"Redeclaración de miembro '{name}' en clase '{cls.name}'", name_tok)
                self.log.err(f"  redeclaración en clase {cls.name}")
        if not self.syms.define(sym):
            self.diag.err("E030", f"Redeclaración en el mismo ámbito: '{name}'", name_tok)
            self.log.err("  redeclaración en mismo ámbito")

    def visitAssignment(self, ctx: CompiscriptParser.AssignmentContext):
        if ctx.Identifier() and ctx.getChild(1).getText() == '=':
            id_tok = ctx.Identifier().getSymbol()
            name = id_tok.text
            sym = self.syms.resolve(name)
            if sym is None:
                self.diag.err("E010", f"Identificador no declarado: '{name}'", id_tok)
                return
            rhs = ctx.expression()
            if isinstance(rhs, list):
                rhs = rhs[-1]
            et = self.visit(rhs)
            if getattr(sym, "is_const", False):
                self.diag.err("E111", f"No se puede asignar a const '{name}'", id_tok)
                return
            if et and not same(sym.type, et):
                self.diag.err("E100", f"Tipo incompatible en asignación: {sym.type} <- {et}", id_tok)
                return
            self.syms.update(name, last_assigned_at=(id_tok.line, id_tok.column))
            return

        exprs = ctx.expression()
        if isinstance(exprs, list) and len(exprs) == 2:
            recv_t = self.visit(exprs[0])
            pname_tok = ctx.Identifier().getSymbol()
            pname = pname_tok.text
            cs = self._get_class_from_type(recv_t)
            if cs is None:
                self.diag.err("SX03", "Acceso a propiedad sobre un no-objeto", ctx.start)
                self.visit(exprs[1])
                return
            mem = cs.get_member(pname)
            if mem is None:
                self.diag.err("CL02", f"La clase '{cs.name}' no tiene miembro '{pname}'", pname_tok)
                self.visit(exprs[1])
                return
            if isinstance(mem, FuncSymbol):
                self.diag.err("PA02", f"No se puede asignar a método '{pname}'", pname_tok)
                self.visit(exprs[1])
                return
            rt = self.visit(exprs[1])
            if getattr(mem, "is_const", False):
                self.diag.err("E111", f"No se puede asignar a const '{pname}'", pname_tok)
                return
            if rt and not same(mem.type, rt):
                self.diag.err("E100", f"Tipo incompatible en asignación: {mem.type} <- {rt}", pname_tok)
                return
            self.syms.update(pname, last_assigned_member=(pname, getattr(mem, "type", None)))
            return

        if isinstance(exprs, list):
            for e in exprs:
                self.visit(e)
        else:
            self.visit(exprs)

    def visitExpressionStatement(self, ctx: CompiscriptParser.ExpressionStatementContext):
        self.visit(ctx.expression())

    def _require_bool(self, ectx, code: str, msg: str):
        t = self.visit(ectx)
        if t is not Boolean:
            self.diag.err(code, msg, ectx.start)

    def visitIfStatement(self, ctx: CompiscriptParser.IfStatementContext):
        self._require_bool(ctx.expression(), "CF01", "Condición de 'if' debe ser boolean")
        self.visit(ctx.block(0))
        if ctx.block(1):
            self.visit(ctx.block(1))

    def visitWhileStatement(self, ctx: CompiscriptParser.WhileStatementContext):
        self._require_bool(ctx.expression(), "CF02", "Condición de 'while' debe ser boolean")
        self.loop_depth += 1
        term = self.visit(ctx.block())
        self.loop_depth -= 1
        return term

    def visitDoWhileStatement(self, ctx: CompiscriptParser.DoWhileStatementContext):
        self.loop_depth += 1
        term = self.visit(ctx.block())
        self.loop_depth -= 1
        self._require_bool(ctx.expression(), "CF03", "Condición de 'do-while' debe ser boolean")
        return term

    def visitForStatement(self, ctx: CompiscriptParser.ForStatementContext):
        self.syms.push()
        if ctx.variableDeclaration():
            self.visit(ctx.variableDeclaration())
        elif ctx.assignment():
            self.visit(ctx.assignment())
        if ctx.expression(0):
            self._require_bool(ctx.expression(0), "CF04", "Condición de 'for' debe ser boolean")
        if ctx.expression(1):
            self.visit(ctx.expression(1))
        self.loop_depth += 1
        term = self.visit(ctx.block())
        self.loop_depth -= 1
        self.syms.pop()
        return term

    def visitSwitchStatement(self, ctx: CompiscriptParser.SwitchStatementContext):
        self._require_bool(ctx.expression(), "CF05", "Expresión de 'switch' debe ser boolean")
        for sc in ctx.switchCase():
            for st in sc.statement():
                self.visit(st)
        if ctx.defaultCase():
            for st in ctx.defaultCase().statement():
                self.visit(st)

    def visitBreakStatement(self, ctx: CompiscriptParser.BreakStatementContext):
        if self.loop_depth == 0:
            self.diag.err("CF10", "'break' fuera de bucle", ctx.start)
            return False
        return True

    def visitContinueStatement(self, ctx: CompiscriptParser.ContinueStatementContext):
        if self.loop_depth == 0:
            self.diag.err("CF11", "'continue' fuera de bucle", ctx.start)
            return False
        return True

    def visitTryCatchStatement(self, ctx: CompiscriptParser.TryCatchStatementContext):
        self.visit(ctx.block(0))
        if ctx.Identifier():
            name_tok = ctx.Identifier().getSymbol()
            vname = name_tok.text
            self.syms.push()
            self.syms.define(VarSymbol(vname, Type("error"), is_const=False))
            self.visit(ctx.block(1))
            self.syms.pop()
        else:
            self.visit(ctx.block(1))

    def visitForeachStatement(self, ctx: CompiscriptParser.ForeachStatementContext):
        col_t = self.visit(ctx.expression())
        if not is_array(col_t):
            self.diag.err("FE01", "foreach requiere una colección (array) a la derecha de 'in'", ctx.expression().start)
            elem = None
        else:
            elem = elem_type(col_t)
        self.syms.push()
        name_tok = ctx.Identifier().getSymbol()
        it_name = name_tok.text
        self.syms.define(VarSymbol(it_name, elem, is_const=False))
        self.loop_depth += 1
        term = self.visit(ctx.block())
        self.loop_depth -= 1
        self.syms.pop()
        return term

    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        name_tok = ctx.Identifier().getSymbol()
        name = name_tok.text
        self.log.step(f"Declaración función '{name}'")
        params = []
        if ctx.parameters():
            for p in ctx.parameters().parameter():
                pname = p.Identifier().getText()
                ptype = from_type_rule(p.type_()) if p.type_() else None
                params.append((pname, ptype))
        ret_type = None
        if ctx.type_():
            ret_type = from_type_rule(ctx.type_())
        self.log.info(f"  firma: ({', '.join(f'{n}:{t}' for n,t in params)}) -> {ret_type}")
        fsym = FuncSymbol(name=name, params=params, return_type=ret_type)
        if self.class_stack and self.class_stack[-1] is not None and self._in_class_block:
            cls = self.class_stack[-1]
            if not cls.define_member(fsym):
                self.diag.err("E030", f"Redeclaración de función/miembro '{name}' en clase '{cls.name}'", name_tok)
                self.log.err("  redeclaración de miembro")
        if not self.syms.define(fsym):
            self.diag.err("E030", f"Redeclaración de función '{name}'", name_tok)
            self.log.err("  redeclaración de función")
        self.syms.push()
        if self.class_stack and self.class_stack[-1] is not None and self._in_class_block:
            cls = self.class_stack[-1]
            self.syms.define(VarSymbol("this", Type(cls.name), is_const=True))
        for pname, ptype in params:
            self.syms.define(VarSymbol(pname, ptype, is_const=False))
        self.func_stack.append(fsym)
        term = self.visit(ctx.block())
        self.func_stack.pop()
        self.syms.pop()
        return term

    def visitReturnStatement(self, ctx: CompiscriptParser.ReturnStatementContext):
        self.log.info("Return")
        if not self.func_stack:
            self.diag.err("CF20", "'return' fuera de función", ctx.start)
            self.log.err("  return fuera de función")
            if ctx.expression():
                self.visit(ctx.expression())
            return True
        fsym = self.func_stack[-1]
        if ctx.expression():
            rt = self.visit(ctx.expression())
            self.log.info(f"  retorna: {rt}, esperado: {fsym.return_type}")
            if fsym.return_type is None:
                self.diag.err("CF21", "La función no devuelve valor (return con valor no permitido)", ctx.start)
                self.log.err("  return no esperado")
            elif rt and not same(fsym.return_type, rt):
                self.diag.err("CF22", f"Tipo de retorno incompatible: {fsym.return_type} <- {rt}", ctx.start)
                self.log.err("  tipo retorno incompatible")
        else:
            if fsym.return_type is not None:
                self.diag.err("CF23", "Se esperaba valor de retorno", ctx.start)
                self.log.err("  falta valor de retorno")
        return True

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        name_tok = ctx.Identifier(0).getSymbol()
        cname = name_tok.text
        self.log.step(f"Declaración clase '{cname}'")
        cls_sym = ClassSymbol(cname)
        if not self.syms.define(cls_sym):
            self.diag.err("E030", f"Redeclaración de clase '{cname}'", name_tok)
            self.log.err("  redeclaración de clase")
        self.syms.push()
        self.class_stack.append(cls_sym)
        self._in_class_block = True
        for m in ctx.classMember():
            self.visit(m)
        self._in_class_block = False
        self.class_stack.pop()
        self.syms.pop()

    def visitExpression(self, ctx: CompiscriptParser.ExpressionContext):
        return self.visit(ctx.assignmentExpr())

    def visitExprNoAssign(self, ctx: CompiscriptParser.ExprNoAssignContext):
        return self.visit(ctx.conditionalExpr())

    def visitConditionalExpr(self, ctx: CompiscriptParser.ConditionalExprContext):
        if ctx.getChildCount() == 5:
            _cond = self.visit(ctx.logicalOrExpr())
            t1 = self.visit(ctx.expression(0))
            t2 = self.visit(ctx.expression(1))
            return t1 if same(t1, t2) else None
        return self.visit(ctx.logicalOrExpr())

    def visitLogicalOrExpr(self, ctx: CompiscriptParser.LogicalOrExprContext):
        t = self.visit(ctx.logicalAndExpr(0))
        for i in range(1, len(ctx.logicalAndExpr())):
            rt = self.visit(ctx.logicalAndExpr(i))
            if t is not Boolean or rt is not Boolean:
                self.diag.err("E221", "Operación '||' requiere booleanos", ctx.start)
                return None
            t = Boolean
        return t

    def visitLogicalAndExpr(self, ctx: CompiscriptParser.LogicalAndExprContext):
        t = self.visit(ctx.equalityExpr(0))
        for i in range(1, len(ctx.equalityExpr())):
            rt = self.visit(ctx.equalityExpr(i))
            if t is not Boolean or rt is not Boolean:
                self.diag.err("E220", "Operación '&&' requiere booleanos", ctx.start)
                return None
            t = Boolean
        return t

    def visitEqualityExpr(self, ctx: CompiscriptParser.EqualityExprContext):
        t = self.visit(ctx.relationalExpr(0))
        for i in range(1, len(ctx.relationalExpr())):
            rt = self.visit(ctx.relationalExpr(i))
            if (t is None) or (rt is None) or (not same(t, rt)):
                self.diag.err("E230", "Comparación requiere operandos del mismo tipo", ctx.start)
                return None
            t = Boolean
        return t

    def visitRelationalExpr(self, ctx: CompiscriptParser.RelationalExprContext):
        t = self.visit(ctx.additiveExpr(0))
        for i in range(1, len(ctx.additiveExpr())):
            rt = self.visit(ctx.additiveExpr(i))
            if not (is_numeric(t) and is_numeric(rt)):
                self.diag.err("E231", "Comparación relacional requiere enteros", ctx.start)
                return None
            t = Boolean
        return t

    def visitAdditiveExpr(self, ctx: CompiscriptParser.AdditiveExprContext):
        t = self.visit(ctx.multiplicativeExpr(0))
        for i in range(1, len(ctx.multiplicativeExpr())):
            rt = self.visit(ctx.multiplicativeExpr(i))
            op = ctx.children[2*i-1].getText()
            if not (is_numeric(t) and is_numeric(rt)):
                self.diag.err("E200", f"Operación '{op}' requiere enteros", ctx.start)
                return None
            t = Integer
        return t

    def visitMultiplicativeExpr(self, ctx: CompiscriptParser.MultiplicativeExprContext):
        t = self.visit(ctx.unaryExpr(0))
        for i in range(1, len(ctx.unaryExpr())):
            rt = self.visit(ctx.unaryExpr(i))
            op = ctx.children[2*i-1].getText()
            if not (is_numeric(t) and is_numeric(rt)):
                self.diag.err("E201", f"Operación '{op}' requiere enteros", ctx.start)
                return None
            t = Integer
        return t

    def visitUnaryExpr(self, ctx: CompiscriptParser.UnaryExprContext):
        if ctx.getChildCount() == 2:
            op = ctx.getChild(0).getText()
            t = self.visit(ctx.unaryExpr())
            if op == '!':
                if t is not Boolean:
                    self.diag.err("E210", "Operación '!' requiere boolean", ctx.start)
                    return None
                return Boolean
            if op == '-':
                if not is_numeric(t):
                    self.diag.err("E211", "Operación '-' unaria requiere entero", ctx.start)
                    return None
                return Integer
        return self.visit(ctx.primaryExpr())

    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext):
        if ctx.literalExpr():
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide():
            return self.visit(ctx.leftHandSide())
        if ctx.expression():
            return self.visit(ctx.expression())
        return None

    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext):
        lit = ctx.Literal()
        if lit:
            text = lit.getText()
            if text.startswith('"'):
                return String
            return Integer
        txt = ctx.getText()
        if txt == "true" or txt == "false":
            return Boolean
        if txt == "null":
            return None
        if ctx.arrayLiteral():
            return self.visit(ctx.arrayLiteral())
        return None

    def visitArrayLiteral(self, ctx: CompiscriptParser.ArrayLiteralContext):
        exps = list(ctx.expression() or [])
        if not exps:
            return ArrayType(Integer)
        first_t = self.visit(exps[0])
        for e in exps[1:]:
            t = self.visit(e)
            if not same(first_t, t):
                self.diag.err("E300", "Elementos del array deben ser del mismo tipo", e.start)
                return ArrayType(first_t)
        return ArrayType(first_t)

    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        curr_type = None
        curr_func = None
        curr_class = None
        pa = ctx.primaryAtom()
        if hasattr(pa, "Identifier") and pa.Identifier():
            tok = pa.Identifier().getSymbol()
            name = tok.text
            sym = self.syms.resolve(name)
            if sym is None:
                self.diag.err("E010", f"Identificador no declarado: '{name}'", tok)
                curr_type = None
            else:
                if isinstance(sym, VarSymbol):
                    curr_type = sym.type
                    cs = self._get_class_from_type(curr_type)
                    if cs:
                        curr_class = cs
                elif isinstance(sym, FuncSymbol):
                    curr_func = sym
                    curr_type = sym.return_type
                elif isinstance(sym, ClassSymbol):
                    curr_type = Type(sym.name)
                    curr_class = sym
        if pa.getChildCount() >= 1 and pa.getChild(0).getText() == "new":
            cname = pa.Identifier().getText()
            csym = self.syms.resolve(cname)
            if not isinstance(csym, ClassSymbol):
                self.diag.err("CL01", f"Clase '{cname}' no declarada", pa.start)
                return None
            arg_types = []
            if pa.arguments():
                for a in pa.arguments().expression():
                    arg_types.append(self.visit(a))
            ctor = csym.get_member("constructor")
            if isinstance(ctor, FuncSymbol):
                if len(arg_types) != len(ctor.params):
                    self.diag.err("CL21", f"Número de argumentos inválido en constructor de '{cname}': esperado {len(ctor.params)}, recibido {len(arg_types)}", pa.start)
                else:
                    for i, ((pname, ptype), at) in enumerate(zip(ctor.params, arg_types)):
                        if ptype is not None and at is not None and not same(ptype, at):
                            self.diag.err("CL22", f"Argumento {i+1} del constructor incompatible: {ptype} <- {at}", pa.start)
            else:
                if len(arg_types) != 0:
                    self.diag.err("CL20", f"Clase '{cname}' no tiene constructor: no se esperan argumentos", pa.start)
            curr_type = Type(cname)
            curr_class = csym
        if pa.getChildCount() == 1 and pa.getChild(0).getText() == "this":
            if not self.class_stack or self.class_stack[-1] is None:
                self.diag.err("CL10", "'this' usado fuera de clase", pa.start)
                curr_type = None
            else:
                curr_type = Type(self.class_stack[-1].name)
                curr_class = self.class_stack[-1]
        for sfx in ctx.suffixOp():
            head = sfx.getChild(0).getText()
            if head == '(':
                args_types = []
                if sfx.arguments():
                    for a in sfx.arguments().expression():
                        args_types.append(self.visit(a))
                target = curr_func
                if target is None:
                    self.diag.err("FN10", "No es una función invocable", sfx.start)
                    curr_type = None
                else:
                    if len(args_types) != len(target.params):
                        self.diag.err("FN11", f"Número de argumentos inválido: esperado {len(target.params)}, recibido {len(args_types)}", sfx.start)
                    else:
                        for i, ((pname, ptype), at) in enumerate(zip(target.params, args_types)):
                            if ptype is not None and at is not None and not same(ptype, at):
                                self.diag.err("FN12", f"Argumento {i+1} incompatible: {ptype} <- {at}", sfx.start)
                    curr_type = target.return_type
                    curr_func = None
            elif head == '[':
                idx_t = self.visit(sfx.expression())
                if idx_t is not Integer:
                    self.diag.err("SX01", "El índice de un array debe ser integer", sfx.start)
                    curr_type = None
                else:
                    if not is_array(curr_type):
                        self.diag.err("SX02", "Solo se puede indexar arrays", sfx.start)
                        curr_type = None
                    else:
                        curr_type = elem_type(curr_type)
            elif head == '.':
                pname = sfx.Identifier().getText()
                if curr_class is None:
                    cs = self._get_class_from_type(curr_type)
                    if cs:
                        curr_class = cs
                if curr_class is None:
                    self.diag.err("SX03", "Acceso a propiedad sobre un no-objeto", sfx.start)
                    curr_type = None
                else:
                    mem = curr_class.get_member(pname)
                    if mem is None:
                        self.diag.err("CL02", f"La clase '{curr_class.name}' no tiene miembro '{pname}'", sfx.start)
                        curr_type = None
                    else:
                        if isinstance(mem, VarSymbol):
                            curr_type = mem.type
                            curr_func = None
                        elif isinstance(mem, FuncSymbol):
                            curr_func = mem
                            curr_type = mem.return_type
                        else:
                            curr_type = None
        return curr_type

    def visitIdentifierExpr(self, ctx: CompiscriptParser.IdentifierExprContext):
        tok = ctx.Identifier().getSymbol()
        name = tok.text
        sym = self.syms.resolve(name)
        if sym is None:
            self.diag.err("E010", f"Identificador no declarado: '{name}'", tok)
            return None
        if isinstance(sym, VarSymbol):
            return sym.type
        if isinstance(sym, FuncSymbol):
            return sym.return_type
        if isinstance(sym, ClassSymbol):
            return Type(sym.name)
        return None