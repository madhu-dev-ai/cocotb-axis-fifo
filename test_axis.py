import random
from collections import deque

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge


async def reset(dut):
    dut.rst_n.value = 0
    dut.s_tvalid.value = 0
    dut.s_tdata.value = 0
    dut.s_tlast.value = 0
    dut.m_tready.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)


@cocotb.test()
async def test_one_word(dut):
    """Send one word in, take one word out."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset(dut)

    assert int(dut.m_tvalid.value) == 0, "FIFO should be empty after reset"
    assert int(dut.s_tready.value) == 1, "FIFO should be ready after reset"

    dut.s_tdata.value = 0xA5
    dut.s_tlast.value = 1
    dut.s_tvalid.value = 1
    await FallingEdge(dut.clk)
    dut.s_tvalid.value = 0

    assert int(dut.m_tvalid.value) == 1, "m_tvalid should be 1 after push"
    assert int(dut.m_tdata.value) == 0xA5, "wrong data at output"
    assert int(dut.m_tlast.value) == 1, "wrong tlast at output"

    dut.m_tready.value = 1
    await FallingEdge(dut.clk)
    dut.m_tready.value = 0

    assert int(dut.m_tvalid.value) == 0, "FIFO should be empty after pop"


@cocotb.test()
async def test_stream_in_order(dut):
    """Send 20 words (no backpressure) and check they come out in order."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset(dut)

    model = deque()
    sent = 0
    received = 0
    total = 20

    m_ready = 1
    dut.m_tready.value = m_ready

    while received < total:
        if sent < total:
            s_valid = 1
            s_data = sent + 1
            s_last = 1 if sent == total - 1 else 0
        else:
            s_valid = 0
            s_data = 0
            s_last = 0

        dut.s_tvalid.value = s_valid
        dut.s_tdata.value = s_data
        dut.s_tlast.value = s_last

        push = s_valid and int(dut.s_tready.value)
        pop = int(dut.m_tvalid.value) and m_ready

        if pop:
            exp_data, exp_last = model.popleft()
            got_data = int(dut.m_tdata.value)
            got_last = int(dut.m_tlast.value)
            assert got_data == exp_data, f"data: got {got_data}, expected {exp_data}"
            assert got_last == exp_last, f"tlast: got {got_last}, expected {exp_last}"
            received += 1

        if push:
            model.append((s_data, s_last))
            sent += 1

        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)

    dut.s_tvalid.value = 0
    assert len(model) == 0, "scoreboard should be empty at the end"


@cocotb.test()
async def test_random_backpressure(dut):
    """300 random words, random sender pauses, random receiver stalls, with coverage."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset(dut)

    model = deque()          # scoreboard
    total = 300
    generated = 0
    received = 0
    cur = None
    prev_stall = None
    cycles = 0

    # Functional coverage bins (each starts at 0 hits)
    cov = {
        "fill_0": 0, "fill_1": 0, "fill_2": 0, "fill_3": 0, "fill_4": 0,
        "push_when_full": 0,     # sender tries to push but FIFO is full
        "pop_when_empty": 0,     # receiver is ready but FIFO is empty
        "push_and_pop": 0,       # push and pop in the same cycle
        "tlast_pushed": 0,       # a tlast=1 word went in
        "output_stall": 0,       # output valid but receiver not ready
        "sender_idle": 0,        # sender had nothing to send
    }

    while received < total:
        cycles += 1
        assert cycles < 5000, "test is stuck (deadlock?)"

        if cur is None and generated < total and random.random() < 0.7:
            cur = (random.randint(0, 255), 1 if random.random() < 0.2 else 0)
            generated += 1

        if cur is not None:
            s_valid = 1
            s_data, s_last = cur
        else:
            s_valid = 0
            s_data, s_last = 0, 0

        m_ready = 1 if random.random() < 0.5 else 0

        dut.s_tvalid.value = s_valid
        dut.s_tdata.value = s_data
        dut.s_tlast.value = s_last
        dut.m_tready.value = m_ready

        s_ready = int(dut.s_tready.value)
        m_valid = int(dut.m_tvalid.value)
        m_data = int(dut.m_tdata.value)
        m_last = int(dut.m_tlast.value)
        level = int(dut.count.value)

        # AXI-Stream rule: a waiting word must not change or disappear
        if prev_stall is not None:
            assert m_valid == 1, "m_tvalid dropped before the word was taken"
            assert (m_data, m_last) == prev_stall, "waiting word changed"

        push = s_valid and s_ready
        pop = m_valid and m_ready

        # Record coverage
        cov[f"fill_{level}"] += 1
        if s_valid and not s_ready:
            cov["push_when_full"] += 1
        if m_ready and not m_valid:
            cov["pop_when_empty"] += 1
        if push and pop:
            cov["push_and_pop"] += 1
        if push and s_last:
            cov["tlast_pushed"] += 1
        if m_valid and not m_ready:
            cov["output_stall"] += 1
        if not s_valid:
            cov["sender_idle"] += 1

        if pop:
            exp_data, exp_last = model.popleft()
            assert m_data == exp_data, f"data: got {m_data}, expected {exp_data}"
            assert m_last == exp_last, f"tlast: got {m_last}, expected {exp_last}"
            received += 1

        if push:
            model.append(cur)
            cur = None

        prev_stall = (m_data, m_last) if (m_valid and not m_ready) else None

        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)

    dut.s_tvalid.value = 0
    dut.m_tready.value = 0
    assert len(model) == 0, "scoreboard should be empty at the end"

    # Coverage report
    hit = sum(1 for v in cov.values() if v > 0)
    dut._log.info(f"done: {total} words in {cycles} cycles")
    dut._log.info("---- FUNCTIONAL COVERAGE ----")
    for name, count in cov.items():
        dut._log.info(f"  {name:16s} {count:5d}  {'HIT' if count > 0 else 'MISSED'}")
    dut._log.info(f"COVERAGE: {hit}/{len(cov)} bins")
    assert hit == len(cov), "some coverage bins were never hit"