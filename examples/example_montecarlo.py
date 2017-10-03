# -*- coding: utf-8 -*-
"""Example of AC analysis with random variables (Monte Carlo)

This example generates a netlist as a function of three parameters: two resistances and once capacitance.
The resulting circuit is a non-inverting amplifier with a low-pass capacitor

This function is called Nmc times to perform an AC analysis and obtain its gain versus frequency for random
values of r1, r2 and c2 around the central values R1, R2 and C2, introducing small variations with a standard
deviation of 5%. After every 10 simulations the library is reset with ng.reset() to avoid memory leaks.

All transfer functions are plotted together on the first figure, with the random distribution of the DC gain
represented as a histogram on the second figure.


"""

from matplotlib import pyplot as plt
import numpy as np
from lyngspice import NgSpice

def dB(x):
  return 20*np.log10(np.abs(x))

def netlist_non_inverting_lowpass(r2, r1, c2):
  return [
      'Non-inverting amplifier with single pole',
      '.include opamp_model.cir',
      'vin in 0 dc 0 ac 1',
      'r2 out 1 %e' % r2,
      'c2 out 1 %e' % c2,
      'r1 1 0 %e' % r1,
      'xopamp in 1 out opamp',
      '.ac dec 10 1k 10meg',
      '.end'
      ]
  

Nmc = 250
R2 = 100e3 # 100kOhm
R1 = 100e3 # 100kOHm
C2 = 1e-12 # 1pF

ng = NgSpice()


data,_ = ng.run(netlist_non_inverting_lowpass(r2=R2, r1=R1, c2=C2))
ac = data.ac1
freq = ac['frequency']

plt.figure()
Gdc = np.zeros(Nmc)
for n in range(Nmc):
  r2_tol, r1_tol, c2_tol = np.random.normal(1, 0.05, 3) # Return three gaussian random variables of mean=1 and stdvar=0.05
  
  data,_ = ng.run(netlist_non_inverting_lowpass(r2=R2*r2_tol, r1=R1*r1_tol, c2=C2*c2_tol))
  
  
  ac = data.ac1
  freq = ac['frequency']
  gain = dB(ac['out'])
  Gdc[n] = gain[0]
  plt.semilogx(freq, gain, 'r-', linewidth=0.5)
  
  if not n%10:
    print('%f%%' % (100*n/Nmc))
    # Flush memory every now and then to prevent leaks
    ng.reset()
  
plt.xticks([1e3, 1e4, 1e5, 1e6, 1e7], ['1k', '10k', '100k', '1M', '10M'])
plt.title('AC gain across %d samples' % Nmc)
plt.xlabel('Frequency [Hz]')
plt.ylabel('Gain [dB]')
plt.grid()
plt.draw()
plt.savefig('ac_gain.png')

plt.figure()
plt.hist(Gdc, bins=20)
plt.title('DC gain distribution')
plt.xlabel('DC gain [dB]')
plt.ylabel('# of samples')
plt.grid()
plt.draw()
plt.savefig('dc_gain.png')


plt.show()

