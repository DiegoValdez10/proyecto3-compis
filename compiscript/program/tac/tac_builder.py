from __future__ import annotations

from typing import Dict, List, Optional

from antlr4 import InputStream, CommonTokenStream

from .generated.TacLexer import TacLexer
from .generated.TacParser import TacParser
from .tac_model import (
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
    TacBlock,
    TacFunction,
    TacProgram,
)


def parse_tac_text(source: str):
    input_stream = InputStream(source)
    lexer = TacLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = TacParser(token_stream)
    return parser.program()


def _value_from_ctx(v_ctx) -> Value:
    text = v_ctx.getText()
    if getattr(v_ctx, "Identifier", None) and v_ctx.Identifier():
        return Value(kind="identifier", text=text)
    if getattr(v_ctx, "IntegerLiteral", None) and v_ctx.IntegerLiteral():
        return Value(kind="int", text=text)
    if getattr(v_ctx, "StringLiteral", None) and v_ctx.StringLiteral():
        return Value(kind="string", text=text)
    if text in ("true", "false"):
        return Value(kind="bool", text=text)
    if text == "null":
        return Value(kind="null", text=text)
    return Value(kind="unknown", text=text)


def _build_instruction(instr_ctx) -> TacInstruction:
    # assignInstr: Identifier ':=' value
    a_ctx = instr_ctx.assignInstr()
    if a_ctx is not None:
        dest = a_ctx.Identifier().getText()
        val = _value_from_ctx(a_ctx.value())
        return Assign(dest=dest, value=val)

    # binaryInstr: Identifier ':=' value binOp value
    b_ctx = instr_ctx.binaryInstr()
    if b_ctx is not None:
        dest = b_ctx.Identifier().getText()
        left_val = _value_from_ctx(b_ctx.value(0))
        right_val = _value_from_ctx(b_ctx.value(1))
        op_token = b_ctx.binOp().getText()
        return BinaryOp(dest=dest, left=left_val, op=op_token, right=right_val)

    # unaryInstr: Identifier ':=' unOp value
    u_ctx = instr_ctx.unaryInstr()
    if u_ctx is not None:
        dest = u_ctx.Identifier().getText()
        op = u_ctx.unOp().getText()
        operand = _value_from_ctx(u_ctx.value())
        return UnaryOp(dest=dest, op=op, operand=operand)

    # arrayInstr
    arr_ctx = instr_ctx.arrayInstr()
    if arr_ctx is not None:
        text = arr_ctx.getText()
        
        # array_store array, index, value
        if text.startswith("array_store"):
            array_name = None
            values = []
            
            for i in range(arr_ctx.getChildCount()):
                child = arr_ctx.getChild(i)
                child_text = child.getText()
                
                # El primer Identifier después de array_store
                if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                    if array_name is None:
                        array_name = child_text
                        
            # Obtener los value()
            if arr_ctx.value(0):
                index_val = _value_from_ctx(arr_ctx.value(0))
            if arr_ctx.value(1):
                value_val = _value_from_ctx(arr_ctx.value(1))
                
            return ArrayStore(array=array_name, index=index_val, value=value_val)
        
        # dest := array_new size
        if "array_new" in text:
            # Primer Identifier es dest
            for i in range(arr_ctx.getChildCount()):
                child = arr_ctx.getChild(i)
                if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                    dest = child.getText()
                    break
            size_val = _value_from_ctx(arr_ctx.value(0))
            return ArrayNew(dest=dest, size=size_val)
        
        # dest := array_index array, index
        if "array_index" in text:
            identifiers = []
            for i in range(arr_ctx.getChildCount()):
                child = arr_ctx.getChild(i)
                if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                    identifiers.append(child.getText())
            
            if len(identifiers) >= 2:
                dest = identifiers[0]
                array_name = identifiers[1]
                index_val = _value_from_ctx(arr_ctx.value(0))
                return ArrayIndex(dest=dest, array=array_name, index=index_val)
        
        # dest := array_length array
        if "array_length" in text:
            identifiers = []
            for i in range(arr_ctx.getChildCount()):
                child = arr_ctx.getChild(i)
                if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                    identifiers.append(child.getText())
            
            if len(identifiers) >= 2:
                dest = identifiers[0]
                array_name = identifiers[1]
                return ArrayLength(dest=dest, array=array_name)

    # fieldInstr
    f_ctx = instr_ctx.fieldInstr()
    if f_ctx is not None:
        text = f_ctx.getText()
        
        # dest := field_load object, field
        if "field_load" in text:
            identifiers = []
            for i in range(f_ctx.getChildCount()):
                child = f_ctx.getChild(i)
                if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                    identifiers.append(child.getText())
            
            if len(identifiers) >= 2:
                dest = identifiers[0]
                obj = identifiers[1]
                field_val = _value_from_ctx(f_ctx.value(0))
                return FieldLoad(dest=dest, object=obj, field=field_val)
        
        # field_store object, field, value
        if text.startswith("field_store"):
            obj = None
            for i in range(f_ctx.getChildCount()):
                child = f_ctx.getChild(i)
                if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                    obj = child.getText()
                    break
                    
            field_val = _value_from_ctx(f_ctx.value(0))
            value_val = _value_from_ctx(f_ctx.value(1))
            return FieldStore(object=obj, field=field_val, value=value_val)

    # callInstr
    c_ctx = instr_ctx.callInstr()
    if c_ctx is not None:
        text = c_ctx.getText()
        identifiers = []
        
        # Recolectar todos los Identifiers
        for i in range(c_ctx.getChildCount()):
            child = c_ctx.getChild(i)
            if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                identifiers.append(child.getText())
        
        # Obtener argumentos
        args: List[Value] = []
        if c_ctx.argList():
            for v in c_ctx.argList().value():
                args.append(_value_from_ctx(v))
        
        # dest := call func(args)
        if ":=" in text and len(identifiers) >= 2:
            dest = identifiers[0]
            func = identifiers[1]
            return Call(dest=dest, function=func, args=args)
        
        # call func(args)
        if len(identifiers) >= 1:
            func = identifiers[0]
            return Call(dest=None, function=func, args=args)

    # branchInstr: branch condition, true_label, false_label
    br_ctx = instr_ctx.branchInstr()
    if br_ctx is not None:
        cond = _value_from_ctx(br_ctx.value())
        
        identifiers = []
        for i in range(br_ctx.getChildCount()):
            child = br_ctx.getChild(i)
            if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                identifiers.append(child.getText())
        
        t_true = identifiers[0] if len(identifiers) > 0 else "unknown"
        t_false = identifiers[1] if len(identifiers) > 1 else "unknown"
        
        return Branch(condition=cond, true_label=t_true, false_label=t_false)

    # jumpInstr: jump target
    j_ctx = instr_ctx.jumpInstr()
    if j_ctx is not None:
        for i in range(j_ctx.getChildCount()):
            child = j_ctx.getChild(i)
            if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                target = child.getText()
                return Jump(target=target)

    # printInstr: print value
    p_ctx = instr_ctx.printInstr()
    if p_ctx is not None:
        val = _value_from_ctx(p_ctx.value())
        return Print(value=val)

    # returnInstr: return value?
    r_ctx = instr_ctx.returnInstr()
    if r_ctx is not None:
        if r_ctx.value() is not None:
            val = _value_from_ctx(r_ctx.value())
            return Return(value=val)
        return Return(value=None)

    # tryInstr
    t_ctx = instr_ctx.tryInstr()
    if t_ctx is not None:
        text = t_ctx.getText()
        
        # begin_try handler_label
        if text.startswith("begin_try"):
            handler = None
            for i in range(t_ctx.getChildCount()):
                child = t_ctx.getChild(i)
                if hasattr(child, 'symbol') and child.symbol.type == TacParser.Identifier:
                    handler = child.getText()
                    break
            
            if handler:
                return BeginTry(handler_label=handler)
            # Fallback: extraer del texto
            handler = text.replace("begin_try", "").strip()
            return BeginTry(handler_label=handler)
        
        # end_try
        if text == "end_try":
            return EndTry()

        if "begin_catch" in text:
            if ":=" in text:
                # dest := begin_catch
                parts = text.split(":=")
                if len(parts) == 2:
                    dest = parts[0].strip()
                    return BeginCatch(dest=dest)
            # begin_catch sin destino
            return BeginCatch(dest=None)
        
        # end_catch
        if text == "end_catch":
            return EndCatch()

    # Fallback
    return Assign(dest="_", value=Value(kind="unknown", text=instr_ctx.getText()))


def build_tac_program(tree) -> TacProgram:
    functions: Dict[str, TacFunction] = {}
    for f_ctx in tree.functionDecl():
        name = f_ctx.Identifier().getText()
        params: List[str] = []
        if f_ctx.paramList() is not None:
            for pid in f_ctx.paramList().Identifier():
                params.append(pid.getText())
        ret_type: Optional[str] = None
        if f_ctx.typeName() is not None:
            ret_type = f_ctx.typeName().getText()

        blocks: List[TacBlock] = []
        current_label: Optional[str] = None
        current_instrs: List[TacInstruction] = []

        def flush_block():
            nonlocal current_label, current_instrs, blocks
            if current_label is None and not current_instrs:
                return
            label = current_label or f"{name}_entry"
            blocks.append(TacBlock(label=label, instructions=list(current_instrs)))
            current_label = None
            current_instrs = []

        for b_ctx in f_ctx.block():
            if b_ctx.label() is not None and b_ctx.instruction():
                flush_block()
                current_label = b_ctx.label().Identifier().getText()
                current_instrs = []
                for instr_ctx in b_ctx.instruction():
                    current_instrs.append(_build_instruction(instr_ctx))
            elif b_ctx.label() is not None and not b_ctx.instruction():
                flush_block()
                current_label = b_ctx.label().Identifier().getText()
                current_instrs = []
            else:
                for instr_ctx in b_ctx.instruction():
                    current_instrs.append(_build_instruction(instr_ctx))

        flush_block()
        functions[name] = TacFunction(
            name=name,
            params=params,
            return_type=ret_type,
            blocks=blocks,
        )
    return TacProgram(functions=functions)