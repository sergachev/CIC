import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotb.triggers import RisingEdge, ReadOnly
from fixedpoint import FixedPoint
from collections import deque

import random
import warnings
import os
import logging
import cocotb_test.simulator
import pytest
import math
import numpy as np

import importlib.util

CLK_PERIOD_NS = 8

class TB(object):
    def __init__(self,dut):
        random.seed(30) # reproducible tests
        self.dut = dut
        self.R = int(dut.CIC_R)
        self.N = int(dut.CIC_N)
        self.M = int(dut.CIC_M)
        self.INP_DW = int(dut.INP_DW)
        self.OUT_DW = int(dut.OUT_DW)

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)        

        self.input = []

        tests_dir = os.path.abspath(os.path.dirname(__file__))
        model_dir = os.path.abspath(os.path.join(tests_dir, '../model/cic_d_model.py'))
        spec = importlib.util.spec_from_file_location("cic_d_model", model_dir)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        self.model = foo.Model(self.R, self.N, self.M, self.INP_DW, self.OUT_DW) 
        cocotb.fork(Clock(self.dut.clk, CLK_PERIOD_NS, units='ns').start())
        

    async def generate_input(self):
        phase = 0
        freq = 10000
        phase_step = CLK_PERIOD_NS * 2 * freq * math.pi * 0.000000001
        self.input = []
        delay = np.zeros(1000)
        while True:
            await RisingEdge(self.dut.clk)
            phase += phase_step
            value = int(np.round(math.sin(phase)*(2**(self.INP_DW-1)-1)))
            self.input.append(value)
            self.model.set_data(value) 
            self.model.tick()
            self.dut.s_axis_in_tdata <= value
            self.dut.s_axis_in_tvalid <= 1

    async def cycle_reset(self):
        self.dut.reset_n.setimmediatevalue(1)
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.reset_n <= 0
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.reset_n <= 1
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        
@cocotb.test()
async def simple_test(dut):
    tb = TB(dut)
    await tb.cycle_reset()
    cocotb.fork(tb.generate_input())
    output = []
    output_model = []
    tolerance = 1
    for _ in range(5000):
        await RisingEdge(dut.clk)
        if(tb.model.data_valid()):
            output_model.append(tb.model.get_data())
            # print(f"model: {output_model[-1]}")

        if dut.m_axis_out_tvalid == 1:
            a=dut.m_axis_out_tdata.value.integer
            if (a & (1 << (tb.OUT_DW - 1))) != 0:
                a = a - (1 << tb.OUT_DW)
            output.append(a)
            # print(f"hdl: {a}")
            assert np.abs(a - output_model[-1]) <= tolerance, f"hdl: {a} \t model: {output_model[-1]}"
        # print(f"{tb.model.data_valid()} {dut.out_samp_str}")
    tb.dut.s_axis_in_tvalid <= 0
    await RisingEdge(dut.clk)
    print(f"received {len(output)} samples")
    
# cocotb-test


tests_dir = os.path.abspath(os.path.dirname(__file__))
rtl_dir = os.path.abspath(os.path.join(tests_dir, '..', 'hdl'))

def calculate_prune_bits(R, N, M, INP_DW, OUT_DW):
    tests_dir = os.path.abspath(os.path.dirname(__file__))
    model_dir = os.path.abspath(os.path.join(tests_dir, '../model/cic_d_model.py'))
    spec = importlib.util.spec_from_file_location("cic_d_model", model_dir)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)
    model = foo.Model(R, N, M, INP_DW, OUT_DW, 0) 
    B_j = model.calculate_register_pruning(R, N, M, INP_DW, OUT_DW)
    
    ret = 0;
    for i in range(1,2*N+2):
        print(f"B_j[{i}] = {B_j[i]}")
        ret += int(B_j[i])<<(32*(i))
    return ret

@pytest.mark.parametrize("R", [10, 100])
@pytest.mark.parametrize("N", [3, 7])
@pytest.mark.parametrize("M", [1, 3])
@pytest.mark.parametrize("INP_DW", [17])
@pytest.mark.parametrize("OUT_DW", [14, 17])
@pytest.mark.parametrize("PRECALCULATE_PRUNE_BITS", [1, 0])
@pytest.mark.parametrize("VARIABLE_RATE", [0])
def test_cic_d(request, R, N, M, INP_DW, OUT_DW, VARIABLE_RATE, PRECALCULATE_PRUNE_BITS):
    dut = "cic_d"
    module = os.path.splitext(os.path.basename(__file__))[0]
    toplevel = dut

    verilog_sources = [
        os.path.join(rtl_dir, f"{dut}.sv"),
        os.path.join(rtl_dir, "comb.sv"),
        os.path.join(rtl_dir, "integrator.sv"),
        os.path.join(rtl_dir, "downsampler.sv"),
        os.path.join(rtl_dir, "downsampler_variable.sv"),
    ]
    includes = [
        os.path.join(rtl_dir, ""),
        os.path.join(rtl_dir, "cic_functions.vh"),
    ]    

    parameters = {}

    parameters['CIC_R'] = R
    parameters['CIC_M'] = M
    parameters['CIC_N'] = N
    parameters['INP_DW'] = INP_DW
    parameters['OUT_DW'] = OUT_DW
    parameters['VARIABLE_RATE'] = VARIABLE_RATE
    if PRECALCULATE_PRUNE_BITS:
        parameters['PRUNE_BITS'] = calculate_prune_bits(R, N, M, INP_DW, OUT_DW)

    extra_env = {f'PARAM_{k}': str(v) for k, v in parameters.items()}
    sim_build="sim_build/" + "_".join(("{}={}".format(*i) for i in parameters.items()))
    cocotb_test.simulator.run(
        python_search=[tests_dir],
        verilog_sources=verilog_sources,
        includes=includes,
        toplevel=toplevel,
        module=module,
        parameters=parameters,
        sim_build=sim_build,
        extra_env=extra_env,
    )