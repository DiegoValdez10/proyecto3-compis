grammar Tac;

program
  : functionDecl+ EOF
  ;

functionDecl
  : 'function' Identifier '(' paramList? ')' (':' typeName)? block*
  ;

block
  : label? instruction+
  ;

label
  : Identifier ':'
  ;

instruction
  : assignInstr
  | binaryInstr
  | unaryInstr
  | branchInstr
  | jumpInstr
  | callInstr
  | returnInstr
  | arrayInstr
  | fieldInstr
  | printInstr
  | tryInstr
  ;

assignInstr
  : Identifier ':=' value
  ;

binaryInstr
  // infix:   t1 := a < b
  : Identifier ':=' value binOp value
  // func:    t1 := lt a, b
  | Identifier ':=' binOp value ',' value
  ;

unaryInstr
  : Identifier ':=' unOp value
  ;

branchInstr
  : 'branch' value ',' Identifier ',' Identifier
  ;

jumpInstr
  : 'jump' Identifier
  ;

callInstr
  : Identifier ':=' 'call' Identifier '(' argList? ')'
  | 'call' Identifier '(' argList? ')'
  ;

returnInstr
  : 'return' value?
  ;

arrayInstr
  : Identifier ':=' 'array_new' value
  | 'array_store' Identifier ',' value ',' value
  | Identifier ':=' 'array_index' Identifier ',' value
  | Identifier ':=' 'array_length' Identifier
  ;

fieldInstr
  : Identifier ':=' 'field_load' Identifier ',' value
  | 'field_store' Identifier ',' value ',' value
  ;

printInstr
  : 'print' value
  ;

tryInstr
  : 'begin_try' Identifier
  | 'end_try'
  | Identifier ':=' 'begin_catch'
  | 'begin_catch'
  | 'end_catch'
  ;

paramList
  : Identifier (',' Identifier)*
  ;

argList
  : value (',' value)*
  ;

value
  : Identifier
  | IntegerLiteral
  | StringLiteral
  | 'true'
  | 'false'
  | 'null'
  ;

typeName
  : Identifier
  ;

binOp
  : '<'  | '>'  | '<=' | '>=' | '==' | '!='
  | '+'  | '-'  | '*'  | '/'  | '%'
  | '&&' | '||'
  | 'lt' | 'gt' | 'le' | 'ge' | 'eq' | 'ne'
  | 'add' | 'sub' | 'mul' | 'div' | 'mod'
  | 'and' | 'or'
  ;

unOp
  : 'neg' | 'not'
  ;

Identifier      : [a-zA-Z_][a-zA-Z0-9_.]*;
IntegerLiteral  : [0-9]+;
StringLiteral   : '"' (~["\r\n])* '"';

COMMENT : '#' ~[\r\n]* -> skip;
WS      : [ \t\r\n]+   -> skip;