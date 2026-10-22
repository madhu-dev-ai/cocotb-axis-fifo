SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(CURDIR)/axis_fifo.sv
COMPILE_ARGS += -g2012

COCOTB_TOPLEVEL = axis_fifo
COCOTB_TEST_MODULES = test_axis

include $(shell cocotb-config --makefiles)/Makefile.sim