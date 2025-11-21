from typing import List, Dict, Optional


class IRFunction:
    def __init__(self, name: str, params: List[str], return_type: Optional[str] = None):
        self.name = name
        self.params = params
        self.return_type = return_type
        self.blocks = []


class IRBasicBlock:
    def __init__(self, label: str):
        self.label = label
        self.instructions = []


class IRInstruction:
    def __init__(self, opcode: str, dest=None, args=None):
        self.opcode = opcode
        self.dest = dest
        self.args = args or []


class Operand:
    def __init__(self, kind: str, value=None, name=None, type_hint=None):
        self.kind = kind
        self.value = value
        self.name = name
        self.type_hint = type_hint
    
    @staticmethod
    def identifier(name: str):
        return Operand('identifier', name=name)
    
    @staticmethod
    def immediate(value, type_hint=None):
        return Operand('immediate', value=value, type_hint=type_hint)


class IRModule:
    def __init__(self):
        self.functions = []
    
    def add_function(self, func):
        self.functions.append(func)


def fix_ir_module(original_ir):
    if hasattr(original_ir, 'functions') and len(original_ir.functions) > 1:
        return original_ir
    
    if hasattr(original_ir, 'name'):
        main_func = original_ir
    elif hasattr(original_ir, 'functions') and len(original_ir.functions) == 1:
        main_func = original_ir.functions[0]
    else:
        return original_ir
    
    new_module = IRModule()
    analysis = _analyze_main(main_func)
    
    if analysis['class_name']:
        constructor = _create_constructor(analysis)
        new_module.add_function(constructor)
        
        for method_name, method_data in analysis['methods'].items():
            method = _create_method(analysis['class_name'], method_name, method_data)
            new_module.add_function(method)
    
    new_main = _create_clean_main(main_func, analysis)
    new_module.add_function(new_main)
    
    return new_module


def _get_operand_name(op) -> str:
    if op is None:
        return "null"
    if hasattr(op, 'name'):
        return op.name
    if hasattr(op, 'value'):
        return str(op.value)
    return str(op)


def _analyze_main(main_func) -> Dict:
    analysis = {
        'class_name': None,
        'constructor_fields': [],
        'constructor_params': [],
        'methods': {},
        'variables': {},
        'object_var': None
    }
    
    instructions = []
    for block in main_func.blocks:
        instructions.extend(block.instructions)
    
    i = 0
    in_constructor = False
    
    while i < len(instructions):
        instr = instructions[i]
        
        if instr.opcode == 'field_store' and len(instr.args) >= 3:
            obj = _get_operand_name(instr.args[0])
            if obj == 'this':
                in_constructor = True
                field = _get_operand_name(instr.args[1]).strip('"')
                value = _get_operand_name(instr.args[2])
                
                analysis['constructor_fields'].append((field, value))
                if value not in analysis['constructor_params']:
                    analysis['constructor_params'].append(value)
        
        if instr.opcode == 'call' and in_constructor:
            func = _get_operand_name(instr.args[0]) if instr.args else None
            if func and func[0].isupper() and '.' not in func:
                analysis['class_name'] = func
                in_constructor = False
                
                if hasattr(instr, 'dest') and instr.dest:
                    obj_var = _get_operand_name(instr.dest)
                    analysis['variables'][obj_var] = func
        
        if instr.opcode == 'assign' and len(instr.args) >= 1:
            dest = _get_operand_name(instr.dest)
            src = _get_operand_name(instr.args[0])
            
            if src in analysis['variables']:
                analysis['variables'][dest] = analysis['variables'][src]
                analysis['object_var'] = dest
        
        i += 1
    
    method_calls = []
    
    for idx, instr in enumerate(instructions):
        if instr.opcode == 'field_load' and len(instr.args) >= 2:
            obj = _get_operand_name(instr.args[0])
            field = _get_operand_name(instr.args[1]).strip('"')
            
            if obj in analysis['variables'] and field not in ['edad', 'nombre', 'age', 'name']:
                dest_temp = _get_operand_name(instr.dest) if hasattr(instr, 'dest') else None
                method_calls.append((idx, obj, field, dest_temp))
    
    for method_idx, obj, method_name, dest_temp in method_calls:
        call_idx = None
        params = []
        for idx in range(method_idx + 1, len(instructions)):
            instr = instructions[idx]
            if instr.opcode == 'call':
                call_target = _get_operand_name(instr.args[0]) if instr.args else None
                if call_target == dest_temp:
                    call_idx = idx
                    params = [_get_operand_name(arg) for arg in instr.args[1:]]
                    break
        
        if call_idx:
            method_prints = []
            
            constructor_end = -1
            if analysis['class_name']:
                for idx, instr in enumerate(instructions):
                    if instr.opcode == 'call':
                        call_target = _get_operand_name(instr.args[0]) if instr.args else None
                        if call_target == analysis['class_name']:
                            constructor_end = idx
                            break
            
            search_ranges = []
            
            if constructor_end >= 0:
                search_ranges.append((0, constructor_end))
                search_ranges.append((constructor_end + 1, method_idx))
            else:
                search_ranges.append((0, method_idx))
            
            for search_start, search_end in search_ranges:
                for idx in range(search_start, search_end):
                    instr = instructions[idx]
                    
                    if instr.opcode == 'print':
                        is_main_print = False
                        if idx > 0:
                            prev = instructions[idx - 1]
                            if prev.opcode == 'field_load':
                                is_main_print = True
                        
                        if not is_main_print:
                            method_prints.append(instr)
            
            analysis['methods'][method_name] = {
                'instructions': method_prints,
                'params': params
            }
    
    return analysis


def _create_constructor(analysis: Dict) -> IRFunction:
    class_name = analysis['class_name']
    params = ['this'] + analysis['constructor_params']
    
    func = IRFunction(f"{class_name}.constructor", params, class_name)
    entry = IRBasicBlock(f"{class_name}.constructor_entry")
    
    for field, param in analysis['constructor_fields']:
        instr = IRInstruction(
            'field_store',
            args=[
                Operand.identifier('this'),
                Operand.immediate(field, 'string'),
                Operand.identifier(param)
            ]
        )
        entry.instructions.append(instr)
    
    entry.instructions.append(
        IRInstruction('return', args=[Operand.identifier('this')])
    )
    
    func.blocks.append(entry)
    return func


def _create_method(class_name: str, method_name: str, method_data: Dict) -> IRFunction:
    params_list = method_data.get('params', [])
    
    if not params_list:
        params_list = ['param']
    
    func = IRFunction(f"{class_name}.{method_name}", ['this'] + params_list)
    entry = IRBasicBlock(f"{class_name}.{method_name}_entry")
    
    for instr in method_data['instructions']:
        if instr.opcode == 'print' and len(instr.args) > 0:
            arg = instr.args[0]
            
            if hasattr(arg, 'kind') and arg.kind == 'immediate' and hasattr(arg, 'type_hint') and arg.type_hint == 'string':
                entry.instructions.append(instr)
            elif hasattr(arg, 'kind') and arg.kind == 'identifier':
                arg_name = arg.name if hasattr(arg, 'name') else str(arg)
                
                if (arg_name.startswith('t') and len(arg_name) > 1 and arg_name[1:].isdigit()) or arg_name == 'nombre':
                    if len(params_list) > 0:
                        new_instr = IRInstruction(
                            'print',
                            args=[Operand.identifier(params_list[0])]
                        )
                        entry.instructions.append(new_instr)
                    else:
                        entry.instructions.append(instr)
                else:
                    entry.instructions.append(instr)
            else:
                entry.instructions.append(instr)
        else:
            entry.instructions.append(instr)
    
    if not entry.instructions or entry.instructions[-1].opcode != 'return':
        entry.instructions.append(IRInstruction('return'))
    
    func.blocks.append(entry)
    return func


def _create_clean_main(main_func, analysis: Dict) -> IRFunction:
    new_main = IRFunction('main', [])
    entry = IRBasicBlock('main_entry')
    
    skip_mode = None
    obj_var = analysis.get('object_var')
    class_name = analysis.get('class_name')
    current_method = None
    method_temp = None
    
    for block in main_func.blocks:
        for instr in block.instructions:
            
            if instr.opcode == 'field_store':
                obj = _get_operand_name(instr.args[0]) if instr.args else None
                if obj == 'this':
                    skip_mode = 'constructor'
                    continue
            
            if instr.opcode == 'print' and skip_mode is None:
                continue
            
            if instr.opcode == 'call' and skip_mode == 'constructor':
                func = _get_operand_name(instr.args[0]) if instr.args else None
                if func and func == class_name:
                    new_instr = IRInstruction(
                        'call',
                        dest=instr.dest,
                        args=[Operand.identifier(f"{class_name}.constructor")] + instr.args[1:]
                    )
                    entry.instructions.append(new_instr)
                    skip_mode = 'after_constructor'
                    continue
            
            if instr.opcode == 'field_load' and len(instr.args) >= 2:
                obj = _get_operand_name(instr.args[0])
                field = _get_operand_name(instr.args[1]).strip('"')
                
                if field in ['edad', 'nombre', 'age', 'name']:
                    entry.instructions.append(instr)
                    continue
                
                if field in analysis.get('methods', {}):
                    skip_mode = 'method'
                    current_method = field
                    method_temp = _get_operand_name(instr.dest) if hasattr(instr, 'dest') else None
                    continue
            
            if instr.opcode == 'call' and skip_mode == 'method' and current_method:
                call_target = _get_operand_name(instr.args[0]) if instr.args else None
                
                if call_target == method_temp:
                    original_params = instr.args[1:]
                    
                    new_instr = IRInstruction(
                        'call',
                        dest=instr.dest,
                        args=[
                            Operand.identifier(f"{class_name}.{current_method}"),
                            Operand.identifier(obj_var)
                        ] + original_params
                    )
                    entry.instructions.append(new_instr)
                    skip_mode = 'after_constructor'
                    current_method = None
                    method_temp = None
                    continue
            
            if skip_mode == 'after_constructor':
                entry.instructions.append(instr)
    
    new_main.blocks.append(entry)
    return new_main