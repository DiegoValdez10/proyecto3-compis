import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from antlr4.tree.Trees import Trees

from compiscript.semantics.parser import parse_text
from compiscript.semantics.type_checker import TypeChecker
from compiscript.semantics.proclog import ProcLog

from compiscript.intermediate.generator import IntermediateGenerator


class IDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Compiscript IDE")
        self.geometry("1200x800")
        self.minsize(900, 600)
        
        self.configure(bg='#1e1e1e')
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.colors = {
            'bg': '#1e1e1e',
            'bg_secondary': '#252526',
            'bg_tertiary': '#2d2d30',
            'text': '#d4d4d4',
            'text_secondary': '#9cdcfe',
            'accent': '#007acc',
            'accent_hover': '#1177bb',
            'button': '#0e639c',
            'button_hover': '#1177bb',
            'border': '#3e3e42',
            'success': '#4ec9b0',
            'error': '#f14c4c',
            'warning': '#ffcc02'
        }
        
        self._configure_styles()
        
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self._build_ui()

    def _configure_styles(self):
        self.style.configure('Custom.TFrame', 
                           background=self.colors['bg'])
        
        self.style.configure('Toolbar.TFrame', 
                           background=self.colors['bg_secondary'],
                           relief='flat')
        
        self.style.configure('Custom.TButton',
                           background=self.colors['button'],
                           foreground='white',
                           borderwidth=0,
                           focuscolor='none',
                           relief='flat',
                           padding=(15, 8))
        
        self.style.map('Custom.TButton',
                      background=[('active', self.colors['button_hover']),
                                ('pressed', self.colors['accent'])])
        
        self.style.configure('Custom.TNotebook',
                           background=self.colors['bg'],
                           borderwidth=0)
        
        self.style.configure('Custom.TNotebook.Tab',
                           background=self.colors['bg_tertiary'],
                           foreground=self.colors['text'],
                           padding=(20, 12),
                           borderwidth=0)
        
        self.style.map('Custom.TNotebook.Tab',
                      background=[('selected', self.colors['accent']),
                                ('active', self.colors['bg_secondary'])])
        
        self.style.configure('Custom.Treeview',
                           background=self.colors['bg_secondary'],
                           foreground=self.colors['text'],
                           fieldbackground=self.colors['bg_secondary'],
                           borderwidth=0)
        
        self.style.configure('Custom.Treeview.Heading',
                           background=self.colors['bg_tertiary'],
                           foreground=self.colors['text_secondary'],
                           relief='flat',
                           borderwidth=1)
        
        self.style.configure('Custom.Vertical.TScrollbar',
                           background=self.colors['bg_tertiary'],
                           troughcolor=self.colors['bg'],
                           borderwidth=0,
                           arrowcolor=self.colors['text'],
                           darkcolor=self.colors['bg_tertiary'],
                           lightcolor=self.colors['bg_tertiary'])

    def _build_ui(self):
        main_frame = tk.Frame(self, bg=self.colors['bg'])
        main_frame.pack(fill='both', expand=True, padx=8, pady=8)
        
        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)

        left = tk.Frame(main_frame, bg=self.colors['bg_secondary'], relief='flat', bd=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        topbar = tk.Frame(left, bg=self.colors['bg_tertiary'], height=60)
        topbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        topbar.pack_propagate(False)
        
        title_label = tk.Label(topbar, text="Editor", 
                              font=("Segoe UI", 11, "bold"),
                              bg=self.colors['bg_tertiary'],
                              fg=self.colors['text_secondary'])
        title_label.pack(side="left", padx=10, pady=15)
        
        button_frame = tk.Frame(topbar, bg=self.colors['bg_tertiary'])
        button_frame.pack(side="right", padx=10, pady=8)
        
        buttons_config = [
            ("Nuevo", self.on_new, self.colors['success']),
            ("Abrir", self.on_open, self.colors['accent']),
            ("Guardar", self.on_save, self.colors['button']),
            ("Chequear (F5)", self.on_check, self.colors['accent']),
            ("Subir & IR", self.on_upload_and_ir, self.colors['button']),
            ("IR (F6)", self.on_generate_ir, self.colors['accent'])
        ]
        
        for text, command, color in buttons_config:
            btn = tk.Button(button_frame, text=text, command=command,
                           font=("Segoe UI", 9, "bold"),
                           bg=color, fg="white", relief="flat",
                           borderwidth=0, cursor="hand2",
                           padx=12, pady=6)
            btn.pack(side="left", padx=3)
            
            def on_enter(e, btn=btn, hover_color=self._darken_color(color)):
                btn.configure(bg=hover_color)
            def on_leave(e, btn=btn, orig_color=color):
                btn.configure(bg=orig_color)
            
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

        editor_frame = tk.Frame(left, bg=self.colors['bg_secondary'])
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)
        
        self.editor = tk.Text(editor_frame, wrap="none", undo=True, 
                             font=("Cascadia Code", 12),
                             bg=self.colors['bg_secondary'],
                             fg=self.colors['text'],
                             insertbackground=self.colors['accent'],
                             selectbackground=self.colors['accent'],
                             selectforeground="white",
                             relief="flat",
                             borderwidth=0,
                             padx=15, pady=15)
        self.editor.grid(row=0, column=0, sticky="nsew")
        
        yscroll = ttk.Scrollbar(editor_frame, orient="vertical", 
                               command=self.editor.yview,
                               style='Custom.Vertical.TScrollbar')
        self.editor.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        right_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        
        self.right = ttk.Notebook(right_frame, style='Custom.TNotebook')
        self.right.grid(row=0, column=0, sticky="nsew")

        self._create_process_tab(self.right)
        self._create_diagnostics_tab(self.right)
        self._create_symbols_tab(self.right)
        self._create_ast_tab(self.right)
        self._create_ir_tab(self.right)

        self.bind("<F5>", lambda e: self.on_check())
        self.bind("<F6>", lambda e: self.on_generate_ir())

    def _create_process_tab(self, parent):
        proc_frame = tk.Frame(parent, bg=self.colors['bg_secondary'])
        self.proc_text = tk.Text(proc_frame, wrap="word", state="disabled", 
                                font=("Cascadia Code", 11),
                                bg=self.colors['bg_secondary'],
                                fg=self.colors['text'],
                                relief="flat", borderwidth=0,
                                padx=15, pady=15)
        self.proc_text.pack(fill="both", expand=True, padx=8, pady=8)
        parent.add(proc_frame, text="Proceso")

    def _create_diagnostics_tab(self, parent):
        diag_frame = tk.Frame(parent, bg=self.colors['bg_secondary'])
        self.diag_text = tk.Text(diag_frame, wrap="word", state="disabled", 
                                font=("Cascadia Code", 11),
                                bg=self.colors['bg_secondary'],
                                fg=self.colors['text'],
                                relief="flat", borderwidth=0,
                                padx=15, pady=15)
        self.diag_text.pack(fill="both", expand=True, padx=8, pady=8)
        parent.add(diag_frame, text="Diagnosticos")

    def _create_symbols_tab(self, parent):
        self.sym_frame = tk.Frame(parent, bg=self.colors['bg_secondary'])
        self._build_symtab_view(self.sym_frame)
        parent.add(self.sym_frame, text="Simbolos")

    def _create_ast_tab(self, parent):
        ast_frame = tk.Frame(parent, bg=self.colors['bg_secondary'])
        self.ast_text = tk.Text(ast_frame, wrap="none", state="disabled", 
                               font=("Cascadia Code", 10),
                               bg=self.colors['bg_secondary'],
                               fg=self.colors['text'],
                               relief="flat", borderwidth=0,
                               padx=15, pady=15)
        self.ast_text.pack(fill="both", expand=True, padx=8, pady=8)
        parent.add(ast_frame, text="Arbol")

    def _create_ir_tab(self, parent):
        ir_frame = tk.Frame(parent, bg=self.colors['bg_secondary'])
        
        ir_container = tk.Frame(ir_frame, bg=self.colors['bg_secondary'])
        ir_container.pack(fill="both", expand=True, padx=8, pady=8)
        ir_container.rowconfigure(0, weight=1)
        ir_container.columnconfigure(0, weight=1)
        
        self.ir_text = tk.Text(ir_container, wrap="word", state="disabled",
                            font=("Cascadia Code", 10),
                            bg=self.colors['bg_secondary'],
                            fg=self.colors['text'],
                            relief="flat", borderwidth=0,
                            padx=15, pady=15)
        self.ir_text.pack(fill="both", expand=True)
        
        parent.add(ir_frame, text="Intermedio")

    def _build_symtab_view(self, parent):
        parent.configure(bg=self.colors['bg_secondary'])
        
        main_frame = tk.Frame(parent, bg=self.colors['bg_secondary'])
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        cols = ("ambito", "nombre", "clase", "tipo/retorno", "meta")
        self.sym_tree = ttk.Treeview(main_frame, columns=cols, show="headings", 
                                    height=18, style='Custom.Treeview')
        
        col_widths = [80, 150, 120, 180, 200]
        for i, (col, width) in enumerate(zip(cols, col_widths)):
            self.sym_tree.heading(col, text=col.upper())
            self.sym_tree.column(col, width=width, anchor="w", minwidth=60)
        
        self.sym_tree.grid(row=0, column=0, sticky="nsew")
        
        yscroll = ttk.Scrollbar(main_frame, orient="vertical", 
                               command=self.sym_tree.yview,
                               style='Custom.Vertical.TScrollbar')
        self.sym_tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

    def _darken_color(self, color):
        if color.startswith('#'):
            color = color[1:]
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darker_rgb = tuple(max(0, c - 30) for c in rgb)
        return '#' + ''.join(f'{c:02x}' for c in darker_rgb)

    def on_new(self):
        self.editor.delete("1.0", "end")

    def on_open(self):
        path = filedialog.askopenfilename(filetypes=[("Compiscript", "*.cps *.comp"), ("Todos", "*.*")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", f.read())

    def on_save(self):
        path = filedialog.asksaveasfilename(defaultextension=".cps", filetypes=[("Compiscript", "*.cps *.comp")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.editor.get("1.0", "end-1c"))
        messagebox.showinfo("Guardar", "Archivo guardado.")

    def on_check(self):
        code = self.editor.get("1.0", "end-1c")
        self._run_semantic_check(code)

    def on_upload_and_ir(self):
        path = filedialog.askopenfilename(filetypes=[("Compiscript", "*.cps *.comp"), ("Todos", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo leer el archivo:\n{ex}")
            return

        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", code)

        self._run_ir_generation(code)
        try:
            self.right.select(self.right.tabs()[-1])
        except Exception:
            pass

    def on_generate_ir(self):
        code = self.editor.get("1.0", "end-1c")
        self._run_ir_generation(code)
        try:
            self.right.select(self.right.tabs()[-1])
        except Exception:
            pass

    def _sink(self, msg: str, tag: str):
        prefixes = {
            "step": "Step: ", 
            "info": "Info: ", 
            "ok": "OK: ", 
            "err": "Error: "
        }
        prefix = prefixes.get(tag, "")
        self._append(self.proc_text, prefix + msg + "\n")

    def _append(self, text_widget: tk.Text, s: str, clear: bool = False):
        text_widget.configure(state="normal")
        if clear:
            text_widget.delete("1.0", "end")
        text_widget.insert("end", s)
        text_widget.configure(state="disabled")
        text_widget.see("end")

    def _update_symtab(self, tc):
        for i in self.sym_tree.get_children():
            self.sym_tree.delete(i)

        snap = []
        try:
            if hasattr(tc, "syms") and tc.syms is not None:
                if hasattr(tc.syms, "snapshot"):
                    snap = tc.syms.snapshot() or []
                else:
                    if hasattr(tc.syms, "scopes"):
                        snap = []
                        for scope in tc.syms.scopes:
                            fake = {}
                            for k, v in scope.items():
                                try:
                                    from compiscript.tables.symbol_table import SymEntry
                                    if isinstance(v, SymEntry):
                                        fake[k] = v
                                    else:
                                        fake[k] = SymEntry(name=k, value=v, meta={})
                                except Exception:
                                    fake[k] = {"name": k, "value": v, "meta": {}}
                            snap.append(fake)
            else:
                self._append(self.proc_text, "Tabla de simbolos no inicializada\n")
        except Exception as ex:
            self._append(self.proc_text, f"Error leyendo tabla de simbolos: {ex}\n")
            snap = []

        for idx, scope in enumerate(snap, start=1):
            ambito = f"{idx}/{len(snap)}"
            for name, entry in scope.items():
                val = getattr(entry, "value", None)
                meta = getattr(entry, "meta", {}) or {}
                clase = getattr(val, "__class__", type(val)).__name__
                tipo = ""
                if hasattr(val, "type"):
                    tipo = str(val.type)
                if hasattr(val, "return_type") and getattr(val, "return_type") is not None:
                    tipo = f"ret: {val.return_type}"
                meta_str = ", ".join(f"{k}={v}" for k, v in meta.items()) if meta else ""
                self.sym_tree.insert("", "end", values=(ambito, name, clase, tipo, meta_str))

    def _update_ast(self, tree, parser):
        s = Trees.toStringTree(tree, None, parser)
        self._append(self.ast_text, s + "\n", clear=True)

    def _update_diags(self, diags):
        self._append(self.diag_text, "", clear=True)
        if hasattr(diags, "ok") and diags.ok():
            self._append(self.diag_text, "Typecheck completado exitosamente!\n")
            return
        items = []
        if hasattr(diags, "all") and callable(diags.all):
            items = diags.all()
        elif hasattr(diags, "items"):
            items = getattr(diags, "items")
        for d in items:
            self._append(self.diag_text, f"{d.code}: {d} (linea {d.line}, col {d.column})\n")

    def _run_semantic_check(self, code: str):
        self._append(self.proc_text, "", clear=True)
        logger = ProcLog(sink=self._sink)
        try:
            tree, parser = parse_text(code)
        except Exception as ex:
            self._append(self.proc_text, f"Error de parser: {ex}\n")
            messagebox.showerror("Error", f"Parser: {ex}")
            return
        tc = TypeChecker(logger=logger)
        diags = tc.visit(tree)
        self._update_ast(tree, parser)
        self._update_symtab(tc)
        self._update_diags(diags)

    def _run_ir_generation(self, code: str):
        self._append(self.ir_text, "", clear=True)
        try:
            tree, _ = parse_text(code)
        except Exception as ex:
            self._append(self.ir_text, f"Error de parser: {ex}\n", clear=True)
            messagebox.showerror("Error", f"Parser: {ex}")
            return

        try:
            gen = IntermediateGenerator()
            module = gen.generate(tree)
            text = repr(module)
            self._append(self.ir_text, text + "\n", clear=True)
            self._append(self.proc_text, "IR generado correctamente\n")
        except Exception as ex:
            self._append(self.ir_text, f"Error generando IR: {ex}\n", clear=True)
            messagebox.showerror("Error", f"IR: {ex}")


def main():
    app = IDE()
    app.mainloop()


if __name__ == "__main__":
    main()