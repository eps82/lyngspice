"""First example using an external netlist "example_simple.cir"
"""

from pathlib import Path
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

CIRCUIT = Path(__file__).resolve().parent / 'example_simple.cir'

ng = NgSpice()  # Optionally pass a file handler such as sys.stdout as an argument if interested in ngspice output
data, units = ng.run(CIRCUIT)  # Simulate and get results as dictionaries. Instead of a file name,
                               # run() also accepts a list of strings with each line of the netlist. 

# example_simple.cir only has an .OP analysis, so their results are stored in data['op1']
# ngspice syntax is respected, so other analyses will be 'tranN', 'acN', 'dcN' and so on
# The second value returned by run() is analogous to data, but containing the corresponding (type, units)
# For example, data['op1']['V(1)'] is a voltage, so units['op1']['V(1)'] contains ('V', 'voltage')
# Alternatively, top level dictionaries are accessible as data.op1, units.op1, etc

print(f"Analyses: {list(data.keys())}")
print()

print("Node voltages:")
print(f"V(1)={data.op1['V(1)'][0]:f} {units.op1['V(1)']}")
print(f"V(2)={data.op1['V(2)'][0]:f} {units.op1['V(2)']}")

# Generator currents are stored by default with the suffix '#branch'
print("Generator currents:")
for vector_name, vector_data in data.op1.items():
    if '#branch' in vector_name:
        print(f"{vector_name}={vector_data[0]:e} {units.op1[vector_name]}")
    
# ngspice also returns a series of constants under the name 'const'
print()
print("Constants:")
for constant_name, value in data.const.items():
    if value.dtype.kind == 'c':
        print(f'{constant_name} = {value[0].real:e}+j{value[0].imag:e}')
    else:
        print(f'{constant_name} = {value[0]:e}')
