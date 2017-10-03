# -*- coding: utf-8 -*-
"""Example of external source definition

External time-domain voltage and current sources take the extra parameter "external":
  
  va0 a0 1 dc 0 external

These sources are defined by the user as functions of time, for example:
  
  def custom_generator(t):
    return 10.0*np.sin(2*numpy.pi*50*t)  # 50Hz sine with amplitude 10V

Before launching the simulation with NgSpice.run() they must be registered like:
  
  ng.add_external_source('va0', custom_generator)   # arguments: name, function
  ng.run('circuit.cir')

Whenever ngspice encounters an external source it will call a function that will look into
a dictionary of user-defined functions, find it by name, and evaluate it at the corresponding time.

This example creates a 4-bit R-2R DAC network ( https://en.wikipedia.org/wiki/Resistor_ladder )
and simulates it with a 100kHz tone. generate_bit_generator() is used to generate the user-defined
function for each bit of the ladder. The results are then plotted.
"""

from matplotlib import pyplot as plt
import numpy as np
from lyngspice import NgSpice

N = 4   # Number of bits for the DAC
R = 50  # Base resistor value (largely irrelevant in this ideal case)

# Returns a function bit_generator(t) that generates a square wave [0, V0]
# This wave is the n-th control bit in a N-bit DAC producing a cosine function at 'freq' Hz
def generate_bit_generator(N, n, freq, V0):
  def bit_generator(t):
    x = np.cos(2*np.pi*freq*t)
    xq = np.round((x+1.0)*((2.0**N)-1.0)/2.0)   # Scale amplitude between 0 and 2**(N-1) and quantize it
    xqn = (xq//(2**n)) % 2                      # Take the n-th bit
    return xqn * V0    
  return bit_generator  

ng = NgSpice()
netlist = ['R-2R network with external sources']
for n in range(N):
  netlist.append('r%d_0 %d %d %f' % (n, n+1, n, (1+(n==0))*R))
  netlist.append('r%d_1 a%d %d %f' % (n, n, n+1, 2*R))
  netlist.append('va%d a%d %d dc 0 external' % (n, n, 0))
  ng.add_external_source('va%d' % n, generate_bit_generator(N, n, 100e3, 1.0))
  
netlist += [
    '.tran 10n 20u',
    '.end'
    ]

print('########### Netlist #############')
f = open('dac_netlist.cir', 'w')
for line in netlist:
  print(line)
  f.write(line + '\n')
f.close()

data, units = ng.run(netlist)

tran = data.tran1
t = tran['time']*1e6
v = tran['V(%d)' % (N)]

plt.figure()
plt.plot(t, v)
plt.ylabel('Analog output [V]')
plt.xlabel('time $[\mu s]$')
plt.title('Output voltage')
plt.grid()
plt.draw()
plt.savefig('dac.png')

plt.figure()
for n in range(N):
  v = tran['a%d' % n]
  plt.plot(t, v + 2*n)
plt.xlabel('time $[\mu s]$')
plt.title('Digital inputs $a_0-a_{%d}$' % (N-1))
plt.yticks(range(2*N+1), 2*N*[''])
plt.grid()
plt.draw()
plt.savefig('dac_bits.png')

plt.show()