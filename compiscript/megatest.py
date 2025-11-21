import sys
from pathlib import Path

from program.mips.pipeline import tac_source_to_mips

SAMPLE_TAC = r"""# ============================================================================
# FUNCIÓN MAIN (todo el código global va aquí)
# ============================================================================

function main() : void
main_entry:
  # -------------------------
  # Constantes y variables globales
  # -------------------------
  
  # const PI: integer = 314;
  PI := 314
  
  # let greeting: string = "Hello, Compiscript!";
  greeting := "Hello, Compiscript!"
  
  # let flag: boolean; (sin inicializar, por defecto null/0)
  flag := 0
  
  # let numbers: integer[] = [1, 2, 3, 4, 5];
  t0 := array_new 5
  array_store t0, 0, 1
  array_store t0, 1, 2
  array_store t0, 2, 3
  array_store t0, 3, 4
  array_store t0, 4, 5
  numbers := t0
  
  # let matrix: integer[][] = [[1, 2], [3, 4]];
  # Crear primer subarray [1, 2]
  t1 := array_new 2
  array_store t1, 0, 1
  array_store t1, 1, 2
  
  # Crear segundo subarray [3, 4]
  t2 := array_new 2
  array_store t2, 0, 3
  array_store t2, 1, 4
  
  # Crear array principal
  t3 := array_new 2
  array_store t3, 0, t1
  array_store t3, 1, t2
  matrix := t3
  
  # -------------------------
  # Llamada a función makeAdder
  # -------------------------
  
  # let addFive: integer = (makeAdder(5));
  t4 := call makeAdder(5)
  addFive := t4
  
  # print("5 + 1 = " + addFive);
  print "5 + 1 = "
  print addFive
  
  # -------------------------
  # If-else statement
  # -------------------------
  
  # if (addFive > 5)
  t5 := addFive > 5
  branch t5, if_true_1, if_false_1
  
if_true_1:
  print "Greater than 5"
  jump if_end_1
  
if_false_1:
  print "5 or less"
  jump if_end_1
  
if_end_1:
  
  # -------------------------
  # While loop
  # -------------------------
  
  # while (addFive < 10)
  jump while_cond_2
  
while_cond_2:
  t6 := addFive < 10
  branch t6, while_body_2, while_end_2
  
while_body_2:
  t7 := addFive + 1
  addFive := t7
  jump while_cond_2
  
while_end_2:
  
  # -------------------------
  # Do-while loop
  # -------------------------
  
  # do { ... } while (addFive > 7)
do_body_3:
  print "Result is now "
  print addFive
  t8 := addFive - 1
  addFive := t8
  jump do_test_3
  
do_test_3:
  t9 := addFive > 7
  branch t9, do_body_3, do_end_3
  
do_end_3:
  
  # -------------------------
  # For loop
  # -------------------------
  
  # for (let i: integer = 0; i < 3; i = i + 1)
  i := 0
  jump for_cond_4
  
for_cond_4:
  t10 := i < 3
  branch t10, for_body_4, for_end_4
  
for_body_4:
  print "Loop index: "
  print i
  jump for_step_4
  
for_step_4:
  t11 := i + 1
  i := t11
  jump for_cond_4
  
for_end_4:
  
  # -------------------------
  # Foreach loop
  # -------------------------
  
  # foreach (n in numbers)
  _idx_5 := 0
  t12 := array_length numbers
  jump foreach_cond_5
  
foreach_cond_5:
  t13 := _idx_5 < t12
  branch t13, foreach_body_5, foreach_end_5
  
foreach_body_5:
  n := array_index numbers, _idx_5
  
  # if (n == 3) continue;
  t14 := n == 3
  branch t14, foreach_continue_5, foreach_check_break_5
  
foreach_continue_5:
  jump foreach_incr_5
  
foreach_check_break_5:
  print "Number: "
  print n
  
  # if (n > 4) break;
  t15 := n > 4
  branch t15, foreach_end_5, foreach_incr_5
  
foreach_incr_5:
  t16 := _idx_5 + 1
  _idx_5 := t16
  jump foreach_cond_5
  
foreach_end_5:
  
  # -------------------------
  # Switch-case
  # -------------------------
  
  # switch (addFive)
  jump switch_cmp_6
  
switch_cmp_6:
  # case 7:
  t17 := addFive == 7
  branch t17, switch_case_7, switch_cmp_7
  
switch_case_7:
  print "It's seven"
  jump switch_end_6
  
switch_cmp_7:
  # case 6:
  t18 := addFive == 6
  branch t18, switch_case_8, switch_default_6
  
switch_case_8:
  print "It's six"
  jump switch_end_6
  
switch_default_6:
  print "Something else"
  jump switch_end_6
  
switch_end_6:
  
  # -------------------------
  # Try-catch
  # -------------------------
  
  begin_try try_handler_9
  jump try_body_9
  
try_body_9:
  # let risky: integer = numbers[10];
  risky := array_index numbers, 10
  print "Risky access: "
  print risky
  end_try
  jump try_end_9
  
try_handler_9:
  err := begin_catch
  print "Caught an error: "
  print err
  end_catch
  jump try_end_9
  
try_end_9:
  
  # -------------------------
  # Instanciar clase Dog y llamar método
  # -------------------------
  
  # let dog: Dog = new Dog("Rex");
  dog := call Dog.constructor("Rex")
  
  # print(dog.speak());
  t19 := call Dog.speak(dog)
  print t19
  
  # -------------------------
  # Acceso a arrays
  # -------------------------
  
  # let first: integer = numbers[0];
  first := array_index numbers, 0
  print "First number: "
  print first
  
  # -------------------------
  # Llamada a función que retorna array
  # -------------------------
  
  # let multiples: integer[] = getMultiples(2);
  multiples := call getMultiples(2)
  
  # print("Multiples of 2: " + multiples[0] + ", " + multiples[1]);
  print "Multiples of 2: "
  t20 := array_index multiples, 0
  print t20
  print ", "
  t21 := array_index multiples, 1
  print t21
  
  # -------------------------
  # Fin del programa
  # -------------------------
  
  print "Program finished."
  return


# ============================================================================
# FUNCIÓN: makeAdder
# ============================================================================

function makeAdder(x) : integer
makeAdder_entry:
  # return x + 1;
  t0 := x + 1
  return t0


# ============================================================================
# FUNCIÓN: getMultiples
# ============================================================================

function getMultiples(n) : integer
getMultiples_entry:
  # let result: integer[] = [n * 1, n * 2, n * 3, n * 4, n * 5];
  t0 := n * 1
  t1 := n * 2
  t2 := n * 3
  t3 := n * 4
  t4 := n * 5
  
  result := array_new 5
  array_store result, 0, t0
  array_store result, 1, t1
  array_store result, 2, t2
  array_store result, 3, t3
  array_store result, 4, t4
  
  # return result;
  return result


# ============================================================================
# FUNCIÓN: factorial (recursiva)
# ============================================================================

function factorial(n) : integer
factorial_entry:
  # if (n <= 1)
  t0 := n <= 1
  branch t0, factorial_base, factorial_recursive
  
factorial_base:
  return 1
  
factorial_recursive:
  # return n * factorial(n - 1);
  t1 := n - 1
  t2 := call factorial(t1)
  t3 := n * t2
  return t3


# ============================================================================
# CLASE: Animal
# ============================================================================

function Animal.constructor(this, name) : void
Animal.constructor_entry:
  field_store this, "name", name
  return this


function Animal.speak(this) : string
Animal.speak_entry:
  t0 := field_load this, "name"
  print t0
  print " makes a sound."
  return


# ============================================================================
# CLASE: Dog (hereda de Animal)
# ============================================================================

function Dog.constructor(this, name) : void
Dog.constructor_entry:
  t0 := call Animal.constructor(this, name)
  return this


function Dog.speak(this) : string
Dog.speak_entry:
  t0 := field_load this, "name"
  print t0
  print " barks."
  return
"""


def run_sample() -> None:
    mips = tac_source_to_mips(SAMPLE_TAC)
    print("=== MIPS GENERADO ===\n")
    print(mips)


def run_file(input_path: Path, output_path: Path | None = None) -> None:
    text = input_path.read_text(encoding="utf-8")
    mips = tac_source_to_mips(text)
    if output_path is not None:
        output_path.write_text(mips, encoding="utf-8")
        print(f"ASM escrito en: {output_path}")
    else:
        print(mips)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        run_sample()
        return 0
    in_path = Path(args[0])
    if not in_path.exists():
        print(f"Entrada no encontrada: {in_path}", file=sys.stderr)
        return 1
    out_path = Path(args[1]) if len(args) > 1 else None
    run_file(in_path, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
