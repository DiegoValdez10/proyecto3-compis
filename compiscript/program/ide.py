#!/usr/bin/env python3
"""
IDE Compilador Compiscript → TAC → MIPS
CORREGIDO: Ahora maneja correctamente múltiples funciones
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


from compiscript.semantics.parser import parse_text
from compiscript.intermediate.generator import IntermediateGenerator
from program.tac.tac_builder import parse_tac_text, build_tac_program
from program.mips.backend import MipsBackend
from program.mips.ir_fixer import fix_ir_module  



def ir_module_to_tac_text(ir_module) -> str:

    all_functions = []

    if hasattr(ir_module, 'functions'):
        functions = ir_module.functions
    elif hasattr(ir_module, 'name'):

        functions = [ir_module]
    else:
        functions = [ir_module]

    for func in functions:
        tac_func = ir_to_tac_text(func)
        all_functions.append(tac_func)
    
    return "\n\n".join(all_functions)


def ir_to_tac_text(ir_func) -> str:
    """Convierte IRFunction a texto TAC"""
    lines = []
    params = ", ".join(ir_func.params) if ir_func.params else ""
    ret_type = ir_func.return_type if ir_func.return_type and ir_func.return_type != "void" else None
    
    if ret_type:
        lines.append(f"function {ir_func.name}({params}): {ret_type}")
    else:
        lines.append(f"function {ir_func.name}({params})")
    
    for block in ir_func.blocks:
        lines.append(f"{block.label}:")
        for instr in block.instructions:
            tac_line = instruction_to_tac(instr)
            if tac_line:
                lines.append(f"    {tac_line}")
    
    return "\n".join(lines)


def operand_to_str(op) -> str:
    """Convierte un Operand a string"""
    if op is None:
        return "null"
    if hasattr(op, 'kind'):
        if op.kind == 'immediate':
            if op.type_hint == 'string':
                return f'"{op.value}"'
            elif op.type_hint == 'boolean':
                return 'true' if op.value else 'false'
            return str(op.value)
        elif op.kind in ('identifier', 'temp', 'label'):
            return op.name
    return str(op)


def instruction_to_tac(instr) -> str:
    """Convierte una Instruction IR a línea TAC"""
    op = instr.opcode
    dest = instr.dest
    args = instr.args or []
    
    if op == 'assign':
        return f"{operand_to_str(dest)} := {operand_to_str(args[0])}"
    
    if op in ('add', 'sub', 'mul', 'div', 'mod', 'lt', 'le', 'gt', 'ge', 'eq', 'ne', 'and', 'or'):
        symbols = {'add': '+', 'sub': '-', 'mul': '*', 'div': '/', 'mod': '%',
                   'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>=',
                   'eq': '==', 'ne': '!=', 'and': '&&', 'or': '||'}
        symbol = symbols.get(op, op)
        return f"{operand_to_str(dest)} := {operand_to_str(args[0])} {symbol} {operand_to_str(args[1])}"
    
    if op in ('neg', 'not'):
        symbol = '-' if op == 'neg' else '!'
        return f"{operand_to_str(dest)} := {symbol} {operand_to_str(args[0])}"
    
    if op == 'jump':
        return f"jump {operand_to_str(args[0])}"
    
    if op == 'branch':
        return f"branch {operand_to_str(args[0])}, {operand_to_str(args[1])}, {operand_to_str(args[2])}"
    
    if op == 'print':
        return f"print {operand_to_str(args[0])}"
    
    if op == 'return':
        if args:
            return f"return {operand_to_str(args[0])}"
        return "return"
    
    if op == 'call':
        func = operand_to_str(args[0])
        call_args = ", ".join(operand_to_str(a) for a in args[1:])
        if dest:
            return f"{operand_to_str(dest)} := call {func}({call_args})"
        return f"call {func}({call_args})"
    
    if op == 'array_new':
        return f"{operand_to_str(dest)} := array_new {operand_to_str(args[0])}"
    
    if op == 'array_store':
        return f"array_store {operand_to_str(args[0])}, {operand_to_str(args[1])}, {operand_to_str(args[2])}"
    
    if op == 'array_index':
        return f"{operand_to_str(dest)} := array_index {operand_to_str(args[0])}, {operand_to_str(args[1])}"
    
    if op == 'array_length':
        return f"{operand_to_str(dest)} := array_length {operand_to_str(args[0])}"
    
    if op == 'field_load':
        return f"{operand_to_str(dest)} := field_load {operand_to_str(args[0])}, {operand_to_str(args[1])}"
    
    if op == 'field_store':
        return f"field_store {operand_to_str(args[0])}, {operand_to_str(args[1])}, {operand_to_str(args[2])}"
    
    if op == 'begin_try':
        return f"begin_try {operand_to_str(args[0])}"
    if op == 'end_try':
        return "end_try"
    if op == 'begin_catch':
        return f"{operand_to_str(dest)} := begin_catch" if dest else "begin_catch"
    if op == 'end_catch':
        return "end_catch"
    
    return f"# unknown: {op}"


def add_exit_to_mips(mips_code: str) -> str:
    """Reemplaza el retorno de main con syscall exit"""
    lines = mips_code.split('\n')
    result = []
    in_main = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.strip() == 'main:':
            in_main = True
            result.append(line)
            i += 1
            continue
        
        if in_main and ':' in line and not line.strip().startswith('#') and not line.strip().startswith('main'):
            label = line.strip().rstrip(':')
            if not any(x in label for x in ['_entry', '_cond', '_body', '_step', '_end', '_true', '_false', 'for_', 'while_', 'if_']):
                in_main = False
        
        if in_main and 'jr $ra' in line:
            indent = '  '
            result.append(f'{indent}# Exit program')
            result.append(f'{indent}li $v0, 10')
            result.append(f'{indent}syscall')
            i += 1
            continue
        
        if in_main and i + 2 < len(lines):
            if 'lw $ra' in line and 'addi $sp' in lines[i+1] and 'jr $ra' in lines[i+2]:
                indent = '  '
                result.append(f'{indent}# Exit program')
                result.append(f'{indent}li $v0, 10')
                result.append(f'{indent}syscall')
                i += 3
                continue
        
        result.append(line)
        i += 1
    
    return '\n'.join(result)



class CompiscriptIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 Compiscript IDE - CSPT → TAC → MIPS")
        self.root.geometry("1500x900")
        
        self.current_file = None
        self.modified = False
        
        self.colors = {
            'bg': '#1e1e1e',
            'bg_secondary': '#252526',
            'bg_editor': '#1e1e1e',
            'fg': '#d4d4d4',
            'accent': '#007acc',
            'success': '#4ec9b0',
            'error': '#f14c4c',
            'warning': '#dcdcaa',
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        self.setup_styles()
        self.create_menu()
        self.create_toolbar()
        self.create_main_area()
        self.create_status_bar()
        self.load_example()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Dark.TFrame', background=self.colors['bg'])
        style.configure('Dark.TLabel', background=self.colors['bg'], foreground=self.colors['fg'])
        style.configure('Dark.TButton', background=self.colors['accent'], foreground='white')
        style.configure('Dark.TNotebook', background=self.colors['bg'])
        style.configure('Dark.TNotebook.Tab', background=self.colors['bg_secondary'], 
                       foreground=self.colors['fg'], padding=[15, 8])
        style.map('Dark.TNotebook.Tab',
                 background=[('selected', self.colors['accent'])],
                 foreground=[('selected', 'white')])
        
    def create_menu(self):
        menubar = tk.Menu(self.root, bg=self.colors['bg_secondary'], fg=self.colors['fg'])
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.colors['bg_secondary'], fg=self.colors['fg'])
        menubar.add_cascade(label="📁 Archivo", menu=file_menu)
        file_menu.add_command(label="Nuevo", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Abrir...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Guardar", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Guardar como...", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.exit_app, accelerator="Ctrl+Q")
        
        compile_menu = tk.Menu(menubar, tearoff=0, bg=self.colors['bg_secondary'], fg=self.colors['fg'])
        menubar.add_cascade(label="⚙️ Compilar", menu=compile_menu)
        compile_menu.add_command(label="Compilar (F5)", command=self.compile_code, accelerator="F5")
        compile_menu.add_command(label="Guardar MIPS...", command=self.save_mips)
        compile_menu.add_separator()
        compile_menu.add_command(label="Limpiar todo", command=self.clear_all)
        
        self.root.bind('<Control-n>', lambda e: self.new_file())
        self.root.bind('<Control-o>', lambda e: self.open_file())
        self.root.bind('<Control-s>', lambda e: self.save_file())
        self.root.bind('<Control-q>', lambda e: self.exit_app())
        self.root.bind('<F5>', lambda e: self.compile_code())
        
    def create_toolbar(self):
        toolbar = tk.Frame(self.root, bg=self.colors['bg_secondary'], height=50)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        buttons = [
            ("📄 Nuevo", self.new_file, self.colors['accent']),
            ("📂 Abrir", self.open_file, self.colors['accent']),
            ("💾 Guardar", self.save_file, self.colors['accent']),
            ("", None, None),
            ("▶️ Compilar (F5)", self.compile_code, self.colors['success']),
            ("💾 Guardar MIPS", self.save_mips, self.colors['warning']),
            ("", None, None),
            ("🗑️ Limpiar", self.clear_all, self.colors['error']),
        ]
        
        for text, cmd, color in buttons:
            if not text:
                ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
            else:
                btn = tk.Button(toolbar, text=text, command=cmd,
                               bg=color, fg='white', relief='flat',
                               font=('Segoe UI', 10, 'bold'),
                               padx=15, pady=8, cursor='hand2')
                btn.pack(side=tk.LEFT, padx=3)
                btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=self._lighten(b.cget('bg'))))
                btn.bind('<Leave>', lambda e, b=btn, c=color: b.configure(bg=c))
                
    def _lighten(self, color):
        if color.startswith('#'):
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            r, g, b = min(255, r+30), min(255, g+30), min(255, b+30)
            return f'#{r:02x}{g:02x}{b:02x}'
        return color
        
    def create_main_area(self):
        main = tk.Frame(self.root, bg=self.colors['bg'])
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left = tk.LabelFrame(main, text="📝 Código Compiscript (CSPT)", 
                            bg=self.colors['bg'], fg=self.colors['accent'],
                            font=('Segoe UI', 11, 'bold'))
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.editor = scrolledtext.ScrolledText(left, wrap=tk.NONE,
            font=('Cascadia Code', 12), bg=self.colors['bg_editor'],
            fg=self.colors['fg'], insertbackground=self.colors['accent'],
            selectbackground=self.colors['accent'], relief='flat', padx=10, pady=10)
        self.editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        right = tk.Frame(main, bg=self.colors['bg'])
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        notebook = ttk.Notebook(right, style='Dark.TNotebook')
        notebook.pack(fill=tk.BOTH, expand=True)
        
        tac_frame = tk.Frame(notebook, bg=self.colors['bg_secondary'])
        notebook.add(tac_frame, text="📋 Código TAC")
        
        self.tac_output = scrolledtext.ScrolledText(tac_frame, wrap=tk.NONE,
            font=('Cascadia Code', 11), bg='#0d1117', fg='#58a6ff',
            relief='flat', padx=10, pady=10, state=tk.DISABLED)
        self.tac_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        mips_frame = tk.Frame(notebook, bg=self.colors['bg_secondary'])
        notebook.add(mips_frame, text="💻 Código MIPS")
        
        self.mips_output = scrolledtext.ScrolledText(mips_frame, wrap=tk.NONE,
            font=('Cascadia Code', 11), bg='#0c1021', fg='#00ff00',
            relief='flat', padx=10, pady=10, state=tk.DISABLED)
        self.mips_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.notebook = notebook
        
    def create_status_bar(self):
        self.status = tk.Label(self.root, text="✅ Listo", anchor=tk.W,
                              bg=self.colors['bg_secondary'], fg=self.colors['success'],
                              font=('Segoe UI', 10), padx=10, pady=5)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)
        
    def update_status(self, msg, error=False):
        icon = "❌" if error else "✅"
        color = self.colors['error'] if error else self.colors['success']
        self.status.config(text=f"{icon} {msg}", fg=color)
        
    def load_example(self):
        example = '''// Ejemplo: ciclo for
for (var a = 1; a < 5; a = a + 1) {
    print a;
}'''
        self.editor.delete('1.0', tk.END)
        self.editor.insert('1.0', example)
        self.update_status("Ejemplo cargado")
        
    def new_file(self):
        self.editor.delete('1.0', tk.END)
        self.current_file = None
        self.update_status("Nuevo archivo")
        
    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Compiscript", "*.cspt *.cps"), ("Todos", "*.*")])
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                self.editor.delete('1.0', tk.END)
                self.editor.insert('1.0', f.read())
            self.current_file = Path(path)
            self.update_status(f"Archivo abierto: {self.current_file.name}")
            
    def save_file(self):
        if not self.current_file:
            return self.save_file_as()
        with open(self.current_file, 'w', encoding='utf-8') as f:
            f.write(self.editor.get('1.0', tk.END))
        self.update_status(f"Guardado: {self.current_file.name}")
        
    def save_file_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".cspt",
            filetypes=[("Compiscript", "*.cspt *.cps"), ("Todos", "*.*")])
        if path:
            self.current_file = Path(path)
            self.save_file()
            
    def compile_code(self):
        self.update_status("Compilando...")
        cspt_code = self.editor.get('1.0', tk.END).strip()
        
        try:
            # CSPT → IR
            tree, _ = parse_text(cspt_code)
            gen = IntermediateGenerator()
            ir_module = gen.generate(tree)

            ir_module = fix_ir_module(ir_module)

            tac_code = ir_module_to_tac_text(ir_module)

            self.tac_output.config(state=tk.NORMAL)
            self.tac_output.delete('1.0', tk.END)
            self.tac_output.insert('1.0', tac_code)
            self.tac_output.config(state=tk.DISABLED)

            tac_tree = parse_tac_text(tac_code)
            program = build_tac_program(tac_tree)
            

            print(f"[DEBUG] TAC Program has {len(program.functions)} functions:")
            for fname in program.functions.keys():
                print(f"  - {fname}")
            
            backend = MipsBackend()
            mips_code = backend.emit_program(program)

            mips_code = add_exit_to_mips(mips_code)
            

            self.mips_output.config(state=tk.NORMAL)
            self.mips_output.delete('1.0', tk.END)
            self.mips_output.insert('1.0', mips_code)
            self.mips_output.config(state=tk.DISABLED)
            
            self.notebook.select(1)
            
            lines = len(mips_code.split('\n'))
            self.update_status(f"Compilación exitosa - {lines} líneas MIPS generadas")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error de compilación", str(e))
            self.update_status(f"Error: {e}", error=True)
            
    def save_mips(self):
        mips = self.mips_output.get('1.0', tk.END).strip()
        if not mips:
            messagebox.showwarning("Aviso", "No hay código MIPS para guardar. Compila primero.")
            return
            
        name = self.current_file.stem + ".asm" if self.current_file else "output.asm"
        path = filedialog.asksaveasfilename(
            defaultextension=".asm", initialfile=name,
            filetypes=[("Assembly MIPS", "*.asm"), ("Todos", "*.*")])
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(mips)
            self.update_status(f"MIPS guardado: {Path(path).name}")
            
    def clear_all(self):
        self.tac_output.config(state=tk.NORMAL)
        self.tac_output.delete('1.0', tk.END)
        self.tac_output.config(state=tk.DISABLED)
        
        self.mips_output.config(state=tk.NORMAL)
        self.mips_output.delete('1.0', tk.END)
        self.mips_output.config(state=tk.DISABLED)
        
        self.update_status("Salida limpiada")
        
    def exit_app(self):
        self.root.quit()


def main():
    root = tk.Tk()
    app = CompiscriptIDE(root)
    root.mainloop()


if __name__ == "__main__":
    main()