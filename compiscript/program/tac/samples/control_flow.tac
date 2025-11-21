function main() : void
entry:
  cond := 1
  branch cond, if_true_1, if_false_2

if_true_1:
  print "T"
  goto end_3

if_false_2:
  print "F"
  goto end_3

end_3:
  return
