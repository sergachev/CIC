all:
		iverilog -g 2005-sv -I hdl hdl/cic_d.sv hdl/integrator.sv hdl/comb.sv hdl/downsampler_variable.sv hdl/downsampler.sv
		./a.out

test:
		poetry run pytest -v --workers 10
		poetry run make -C tests
