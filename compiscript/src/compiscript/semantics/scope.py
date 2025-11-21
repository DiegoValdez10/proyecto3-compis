class Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.table = {}

    def define(self, sym):
        if sym.name in self.table:
            return False
        self.table[sym.name] = sym
        return True

    def resolve(self, name):
        s = self
        while s:
            if name in s.table:
                return s.table[name]
            s = s.parent
        return None
