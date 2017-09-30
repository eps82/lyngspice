# -*- coding: utf-8 -*-
"""First example using an external netlist "example_simple.cir"
"""

from lyngspice import NgSpice

# ##### example_simple.cir #####
#
# Very basic example          1---/\/\/\/--2--/\/\/\/--.
# r1 1 2 50                  _|_   r1=50Ohm   r2=50Ohm |
# r2 2 0 50           vg=1V / + \                      |
# vg 1 0 1                  \_-_/                      |
# .op                         |                        |
# .end                      -----                    -----
#                            ---                      ---

ng = NgSpice()  # Optionally pass a file handler such as sys.stdout as an argument if interested in ngspice output
data, units = ng.run('example_simple.cir')  # Simulate and get results as dictionaries. Instead of a file name,
                                            # run() also accepts a list of strings with each line of the netlist. 

# example_simple.cir only has an .OP analysis, so their results are stored in data['op1']
# ngspice syntax is respected, so other analyses will be 'tranN', 'acN', 'dcN' and so on
# The second value returned by run() is analogous to data, but containing the corresponding (type, units)
# For example, data['op1']['V(1)'] is a voltage, so units['op1']['V(1)'] contains ('V', 'voltage')
# Alternatively, top level dictionaries are accessible as data.op1, units.op1, etc

print("Analyses: " + str(list(data.keys())))
print()

print("Node voltages:")
print("V(1)=%f %s" % (data.op1['V(1)'], str(units.op1['V(1)'])))
print("V(2)=%f %s" % (data.op1['V(2)'], str(units.op1['V(2)'])))  

# Generator currents are stored by default with the suffix '#branch'
print("Generator currents:")
for vector_name, vector_data in data.op1.items():
  if '#branch' in vector_name:
    print("%s=%e %s" % (vector_name, vector_data, str(units.op1[vector_name])))
    
# ngspice also returns a series of constants under the name 'const'
print()
print("Constants:")
for constant_name, value in data.const.items():
  try:
    print('%s = %e' % (constant_name, value))
  except:
    print('%s = %e+j%e' % (constant_name, value.real, value.imag))