# ##################################################################################################
#
#          lyngspice v0.2.1 - A simple single-module wrapper for ngspice
#
# Copyright (c) 2018 Ernesto Pérez Serna
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Ngspice is an open-source analog circuit simulator based on Berkeley's prolific spice3f5. Nowadays
it also integrates event-driven simulation functionality from XPICE, and is distributed both as a
standalone application and a shared library, providing an interface from third party software.

lyngspice is a minimalistic wrapper to control this shared library from Python, with the goal of
providing easy access to ngspice in native Python code with minimal intrusion, avoiding overcomplicated 
data types or methods.

Many other libraries of this kind exist under different names: PySpice, ngspicepy, ngspyce... My only
reason for writing my own was none of those addressed my needs, either lacking functionality or limiting
it with high level structures. Nonetheless, some ctypes definitions of this version have been taken from 
pyngspice (https://github.com/turboaffe/pyngspice), with some ideas from cffi-based PySpice 
(https://pypi.python.org/pypi/PySpice), whose authors I thank.

This version has been tested on Linux and Windows with ngspice 27, which can be downloaded here:
    
http://ngspice.sourceforge.net/

ngspice's DLL for Windows is distributed from their website. Although there are packages for Linux they
are in general outdated, so it is recommended to download the source, uncompress it and build it with
  
./configure --with-ngshared
make
sudo make install

lyngspice will look for the corresponding file on any of the default paths defined in _LIB_PATHS. Edit
this variable if needed.

Basic usage:
  
  from lyngspice import NgSpice
  ng = NgSpice()
  data, units = ng.run('circuit.cir') # or alternatively a list of lines with the netlist instead
  
Results are returned as simple dictionaries. See the examples for extra tips.

@author: Ernesto Pérez Serna
"""

import platform
import os.path
import sys
import numpy as np
from queue import Queue
from ctypes import c_char_p, c_void_p, c_int, c_short, c_double, c_bool, Structure
from ctypes import cast, pointer, POINTER, CFUNCTYPE, py_object
try:
    from ctypes import windll as dll
    from _ctypes import FreeLibrary as dlclose
except ImportError:
    from ctypes import cdll as dll
    from _ctypes import dlclose

_LIB_PATHS = {
    'Linux'   :   ['libngspice.so', '/usr/local/lib/libngspice.so'],
    'Windows' :   ['C:\\Program Files\\Spice\\bin_dll\\ngspice.dll',
                   'C:\\Program Files\\Spice64\\bin_dll\\ngspice.dll',
                   'ngspice.dll'],
    'FreeBSD' :   ['/usr/local/lib/libngspice.so']
    }

_encoding = 'iso8859_15'

_UNITS = [
        '',
        's',
        'Hz',
        'V',
        'A',
        'V/Hz',
        'A/Hz',
        'sqrt(V)/Hz',
        'sqrt(I)/Hz',
        'sqrt(V)',
        'sqrt(I)',
        'Hz',
        'Hz',
        '',
        'C',
        'Ohm',
        'Ohm', 
        'S',
        'W',
        'deg',
        'dB',
        'C',
        'Q'
        ]
_TYPE = [
        'no_type',
        'time',
        'frequency',
        'voltage',
        'current',
        'voltage_density',
        'current_density',
        'sqr_voltage_density',
        'sqr_current_density',
        'sqr_voltage',
        'sqr_current',
        'pole',
        'zero',
        's_parameter',
        'temperature',
        'res',
        'impedance',
        'admittance',
        'power',
        'phase',
        'db',
        'capacitance',
        'charge']
# ########################################### DATA TYPES ###################################################### #

class ngcomplex_t(Structure):
    _fields_ = [('cx_real', c_double), 
                ('cx_imag', c_double)]

class pvector_info(Structure):
    _fields_ = [('v_name', c_char_p), 
                ('v_type', c_int),
                ('v_flags', c_short),
                ('v_realdata', POINTER(c_double)),
                ('v_compdata', POINTER(ngcomplex_t)),
                ('v_length', c_int)
                ]
 
class VecInfo(Structure):
    _fields_ = [('number', c_int),       # number of vector , as postion in the linked list of vectors , starts with 0
                ('vecname', c_char_p),   # name of the actual vector
                ('is_real', c_bool),     # TRUE if the actual vector has real data
                ('pdvec', c_void_p),     # a void pointer to struct dvec *d , the actual vector
                ('pdvecscale', c_void_p) # a void pointer to struct dvec *ds ,the scale vector
                ]

class VecInfoAll(Structure):
    _fields_ = [('name', c_char_p),     
                ('title', c_char_p),  
                ('date', c_char_p),    
                ('type', c_char_p),   
                ('veccount', c_int),    
                ('vecs', POINTER(POINTER(VecInfo))) #the data as an array of vecinfo with length equal to the number of vectors in the plot
                ]
 
class VecValues(Structure):
    _fields_ = [('name', c_char_p),     # name of a specific vector
               ('creal', c_double),     # actual data value
               ('cimag', c_double),     # actual data value
               ('is_scale', c_bool),    # if "name" is the scale vector
               ('is_complex', c_bool)   # if the data are complex numbers
               ]
 
class VecValuesAll(Structure):
    ''' Pointer vecvaluesall to be found as parameter to callback function SendData.'''
    _fields_ = [('veccount', c_int),    # number of vectors in plot
                ('vecindex', c_int),    # index of actual set of vectors, i.e. the number of accepted datapoints
                ('vecsa', POINTER(POINTER(VecValues))) # values of actual set of vectors, indexed from 0 to veccount − 1
                ]

_SendCharType = CFUNCTYPE(c_int, c_char_p, c_int, py_object)
_SendStatType = CFUNCTYPE(c_int, c_char_p, c_int, py_object)
_ControlledExitType = CFUNCTYPE(c_int, c_int, c_bool, c_bool, c_int, py_object)
_SendDataType = CFUNCTYPE(c_int, POINTER(VecValuesAll), c_int, c_int, py_object)
_SendInitDataType = CFUNCTYPE(c_int, POINTER(VecInfoAll), c_int, py_object)
_BGThreadRunningType = CFUNCTYPE(c_int, c_bool, c_int, py_object)
_GetSRCDataType = CFUNCTYPE(c_int, POINTER(c_double), c_double, c_char_p, c_int, py_object)

class Dataset(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__.update(self)
    def __setitem__(self, key, item):
        super().__setitem__(key, item)
        setattr(self, key, self[key])

# ########################################### NGSPICE INTERFACE ############################################### #

class NgSpice:

    def __init__(self, output=None):
        self._ng_out = output
        self._external_sources = {}
        self._thread_callback = lambda is_running, lib_id: 0
        self._msg_queue = Queue()
        self._shared = None
        self._dll_dir = None

        self.running_os = platform.system()

        try:
            self.__lib_loader = {
                'Windows' : dll.LoadLibrary,
                'Linux'   : dll.LoadLibrary,
                'FreeBSD' : dll.LoadLibrary}[self.running_os]
        except KeyError as exc:
            raise OSError(f"Unknown operating system: {self.running_os}") from exc

        try:
            self.lib_path = list(filter(os.path.isfile, _LIB_PATHS[self.running_os]))[0]
        except IndexError as exc:
            raise FileNotFoundError(
                f"No ngspice shared library found in any of the default locations: {_LIB_PATHS[self.running_os]}"
            ) from exc

        self.__attach()

    def command(self, command):
        self._msg_queue_flush()
        return self._shared.ngSpice_Command(command.encode(_encoding))

    def version(self):
        self.command('version -f')
        ngspice, cider, xspice, openmp = [False]*4

        while self._msg_queue.qsize():
            s = self._msg_queue.get()
            if 'ngspice-' in s:
                ngspice = s.split('-')[1].split(':')[0].strip() # stdout ** ngspice-27 : ....
            elif 'CIDER' in s:
                cider = s.split('CIDER')[1].split('(')[0].strip()
            elif 'XSPICE' in s:
                xspice = ('extensions included' in s)
            elif 'OpenMP' in s:
                openmp = ('enabled' in s)

        return {
            'ngspice': ngspice,
            'CIDER'  : cider,
            'XSPICE' : xspice,
            'OpenMP' : openmp
        }

    def _msg_queue_flush(self):
        while self._msg_queue.qsize():
            self._msg_queue.get()


    def load_netlist(self, netlist):

        # Load circuit as a file
        if isinstance(netlist, str):
            return self.command('source %s' % netlist)

        # Load circuit as an array (list) of strings
        else:
            c_netlist = (c_char_p*(len(netlist)+1))()
            for i, line in enumerate(netlist):
                c_netlist[i] = c_char_p(line.encode(_encoding) + os.linesep.encode(_encoding))
            c_netlist[-1] = c_char_p(None)
            return self._shared.ngSpice_Circ(c_netlist)

    def add_external_source(self, name, fun):
        self._external_sources[name] = fun

    def set_thread_callback(self, fun):
        self._thread_callback = fun

    # Reload ngspice shared library. Use periodically to minimize leaks
    def reset(self):
        self.__detach()
        self.__attach()

    def bg_halt(self):
        self.command('bg_halt')

    def bg_resume(self):
        self.command('bg_resume')

    def bg_run(self, netlist=None):
        return self.__run(netlist=netlist, background=True)

    def run(self, netlist=None):
        if self.__run(netlist=netlist, background=False):
            return (),
        else:
            return self.get_data()

    def __run(self, netlist, background):
        command = 'bg_run' if background else 'run'
        if netlist is not None:
            if self.load_netlist(netlist):
                sys.stderr.write('Error loading netlist. NgSpice.run() aborted\n')
                return 1

        if self.command(command):
            sys.stderr.write('Error simulating netlist. NgSpice.command(\'run\') returned 1\n')
            return 1


    def get_data(self):
        plots = self._shared.ngSpice_AllPlots()

        i = 0
        plot_names = []
        while plots[i] is not None:
            plot_names.append(plots[i])
            i+= 1

        data = Dataset({})
        units = Dataset({})
        for plot_name in plot_names:

            all_vectors = self._shared.ngSpice_AllVecs(plot_name)
            i = 0
            s_plot_name = plot_name.decode(_encoding)
            data[s_plot_name] = {}
            units[s_plot_name] = {}

            while all_vectors[i] is not None:
                vec_ptr = self._shared.ngGet_Vec_Info(plot_name + b'.' + all_vectors[i])
                # In mixed-mode (analog + XSPICE/event-driven) simulations, ngSpice_AllVecs can
                # list internal or digital/event vectors that ngGet_Vec_Info cannot return as
                # analog vectors (yielding a NULL pointer or empty data buffers).
                if not vec_ptr or not vec_ptr.contents.v_name:
                    i += 1
                    continue

                vec = vec_ptr.contents
                vec_name = vec.v_name.decode(_encoding)

                if self.is_real(vec.v_flags) and vec.v_realdata:
                    z = np.ctypeslib.as_array(vec.v_realdata, (vec.v_length,)).copy()
                elif self.is_complex(vec.v_flags) and vec.v_compdata:
                    x_jy = np.ctypeslib.as_array(cast(vec.v_compdata, POINTER(c_double)), (2*vec.v_length,)).copy()
                    z = np.array(x_jy[0::2], dtype=np.complex128)
                    if vec_name != 'frequency':
                        z.imag = x_jy[1::2]
                    else:
                        z = z.real
                else:
                    # Skip non-analog vectors (e.g., XSPICE event-driven nodes) with no real/complex data
                    i += 1
                    continue

                data[s_plot_name][vec_name] = z
                if 0 <= vec.v_type < len(_UNITS):
                    units[s_plot_name][vec_name] = (_UNITS[vec.v_type], _TYPE[vec.v_type])
                else:
                    units[s_plot_name][vec_name] = ('', 'unknown')
                i += 1

        return data, units

    def __attach(self):
        lib_path = os.path.abspath(self.lib_path)
        if hasattr(os, 'add_dll_directory'):
            self._dll_dir = os.add_dll_directory(os.path.dirname(lib_path))
        self._shared = self.__lib_loader(lib_path)

        self._shared.ngSpice_Init.argtypes = [
            _SendCharType,
            _SendStatType,
            _ControlledExitType,
            _SendDataType,
            _SendInitDataType,
            _BGThreadRunningType,
            py_object,
        ]
        self._shared.ngSpice_Init.restype = c_int

        self._shared.ngSpice_Init_Sync.argtypes = [
            _GetSRCDataType,
            _GetSRCDataType,
            c_void_p,
            POINTER(c_int),
            c_void_p,
        ]
        self._shared.ngSpice_Init_Sync.restype = c_int

        self._shared.ngSpice_Command.argtypes = [c_char_p]
        self._shared.ngSpice_Command.restype = c_int

        self._shared.ngSpice_Circ.argtypes = [POINTER(c_char_p)]
        self._shared.ngSpice_Circ.restype = c_int

        self._shared.ngSpice_AllPlots.argtypes = []
        self._shared.ngSpice_AllPlots.restype = POINTER(c_char_p)

        self._shared.ngSpice_AllVecs.argtypes = [c_char_p]
        self._shared.ngSpice_AllVecs.restype = POINTER(c_char_p)

        self._shared.ngGet_Vec_Info.argtypes = [c_char_p]
        self._shared.ngGet_Vec_Info.restype = POINTER(pvector_info)

        self._shared.ngSpice_Init(self._SendChar,
                                  self._SendStat,
                                  self._ControlledExit,
                                  self._SendData,
                                  self._SendInitData,
                                  self._BGThreadRunning,
                                  self)
        self._shared.ngSpice_Init_Sync(self._GetSRCData, self._GetSRCData, None, pointer(c_int(0)), None)

    def __detach(self):
        if getattr(self, '_shared', None) is not None:
            try:
                self.command('quit')
            finally:
                handle = self._shared._handle
                self._shared = None
                if dlclose is not None:
                    dlclose(handle)
        if getattr(self, '_dll_dir', None) is not None:
            dll_dir = self._dll_dir
            self._dll_dir = None
            dll_dir.close()

    def close(self):
        self.__detach()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def is_real(v_flags):
        return v_flags & 0b1

    @staticmethod
    def is_complex(v_flags):
        return v_flags & 0b10

    def __del__(self):
        self.close()


    # ############################################### Callbacks ##################################################### #

    @staticmethod
    @_ControlledExitType
    def _ControlledExit(exit_status, unloading, exit_upon_quit, lib_id, self):
        return 0

    @staticmethod
    @_BGThreadRunningType
    def _BGThreadRunning(is_running, lib_id, self):
        return self._thread_callback(is_running, lib_id)

    # Same function for voltages and currents (just use different identifiers to tell them apart!)
    @staticmethod
    @_GetSRCDataType
    def _GetSRCData(return_value, actual_time, node_name, lib_id, self):
        node_name = node_name.decode(_encoding)
        if node_name in self._external_sources:
            return_value[0] = self._external_sources[node_name](actual_time)
            return 0
        else:
            sys.stderr.write("Warning: Undefined external source \'%s\'. Returning 0 volts/amperes" % node_name)
            self._external_sources[node_name] = lambda t : 0.0
            return_value[0] = 0.0
            return 1

    @staticmethod
    @_SendCharType
    def _SendChar(p_output, lib_id, self):
        msg = p_output.decode(_encoding)
        self._msg_queue.put(msg)
        if self._ng_out is not None:
            self._ng_out.write(msg)
            self._ng_out.write('\n')
        return 0

    @staticmethod
    @_SendStatType
    def _SendStat(p_sim_stat, lib_id, self):
        return 0

    @staticmethod
    @_SendDataType
    def _SendData(p_vecvaluesall, nr_of_structs, lib_id, self):
        return 0

    @staticmethod
    @_SendInitDataType
    def _SendInitData(p_vecinfoall, lib_id, self):
        return 0
