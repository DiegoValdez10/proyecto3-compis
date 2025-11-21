# Generated from Tac.g4 by ANTLR 4.9.3
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .TacParser import TacParser
else:
    from TacParser import TacParser

# This class defines a complete generic visitor for a parse tree produced by TacParser.

class TacVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by TacParser#program.
    def visitProgram(self, ctx:TacParser.ProgramContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#functionDecl.
    def visitFunctionDecl(self, ctx:TacParser.FunctionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#block.
    def visitBlock(self, ctx:TacParser.BlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#label.
    def visitLabel(self, ctx:TacParser.LabelContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#instruction.
    def visitInstruction(self, ctx:TacParser.InstructionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#assignInstr.
    def visitAssignInstr(self, ctx:TacParser.AssignInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#binaryInstr.
    def visitBinaryInstr(self, ctx:TacParser.BinaryInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#unaryInstr.
    def visitUnaryInstr(self, ctx:TacParser.UnaryInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#branchInstr.
    def visitBranchInstr(self, ctx:TacParser.BranchInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#jumpInstr.
    def visitJumpInstr(self, ctx:TacParser.JumpInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#callInstr.
    def visitCallInstr(self, ctx:TacParser.CallInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#returnInstr.
    def visitReturnInstr(self, ctx:TacParser.ReturnInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#arrayInstr.
    def visitArrayInstr(self, ctx:TacParser.ArrayInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#fieldInstr.
    def visitFieldInstr(self, ctx:TacParser.FieldInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#printInstr.
    def visitPrintInstr(self, ctx:TacParser.PrintInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#tryInstr.
    def visitTryInstr(self, ctx:TacParser.TryInstrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#paramList.
    def visitParamList(self, ctx:TacParser.ParamListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#argList.
    def visitArgList(self, ctx:TacParser.ArgListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#value.
    def visitValue(self, ctx:TacParser.ValueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#typeName.
    def visitTypeName(self, ctx:TacParser.TypeNameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#binOp.
    def visitBinOp(self, ctx:TacParser.BinOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by TacParser#unOp.
    def visitUnOp(self, ctx:TacParser.UnOpContext):
        return self.visitChildren(ctx)



del TacParser