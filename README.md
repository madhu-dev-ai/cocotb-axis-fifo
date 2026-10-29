# AXI-Stream FIFO: cocotb Verification



![tests](https://github.com/madhu-dev-ai/cocotb-axis-fifo/actions/workflows/test.yml/badge.svg)



A verification environment for an 8-bit, 4-deep AXI-Stream FIFO with `tvalid`/`tready` backpressure, written in Python with cocotb and Icarus Verilog.



## What is verified



- AXI-Stream handshake: a word moves only on a clock edge where both `tvalid` and `tready` are 1

- No data loss, duplication or reordering (Python scoreboard)

- `tlast` (packet boundary) travels with its data word

- AXI-Stream stability rule: once `m_tvalid` is 1, the waiting word must not change or disappear until it is taken



## Design



`axis_fifo.sv` is a 4-entry FIFO. Each entry holds 8 bits of `tdata` plus 1 bit of `tlast`. It has a write pointer, a read pointer and a fill counter. `s_tready` is 0 when full. `m_tvalid` is 0 when empty.



## Tests (`test_axis.py`)



| Test | What it does |

|------|--------------|

| `test_one_word` | Reset, push one word, pop it, check empty |

| `test_stream_in_order` | 20 words, receiver always ready, checked against a Python model |

| `test_random_backpressure` | 300 random words, random sender pauses, random receiver stalls, scoreboard and stability check, functional coverage |



## Functional coverage (11 bins, all hit)



FIFO fill level 0 to 4, push when full, pop attempt when empty, push and pop in the same cycle, `tlast` pushed, output stalled, sender idle.



## Bug stories



### Bug 1: FIFO accepts data when full



**Change:** `push = s_tvalid` (ignored `s_tready`).



**Caught by:** `test_random_backpressure` (2 of 3 tests still passed).



**Message:** `AssertionError: waiting word changed`, `assert (101, 0) == (38, 0)`



**Cause:** When the FIFO was full, a new word overwrote the oldest entry. The word waiting at the output changed from 38 to 101 before the receiver took it. The stability check caught it. The simple tests never fill the FIFO, so only the random test with backpressure could find this bug.



**Fix:** `push = s_tvalid && s_tready`.



### Bug 2: tlast forgotten



**Change:** `m_tlast = 1'b0` (always 0).



**Caught by:** all 3 tests.



**Message:** `AssertionError: tlast: got 0, expected 1`



**Cause:** Data was correct, but the packet-boundary flag was lost. In a real chip, packets would run together.



**Fix:** `m_tlast = mem[rd_ptr][8]`.



## How to run



```

make

```



Needs: Python, cocotb 2.x, Icarus Verilog, make.

