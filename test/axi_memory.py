"""Small AXI memory model shared by integration tests.

Call drive() before the clock edge, then observe() immediately before that edge.
All addresses are byte addresses; uninitialized bytes have a stable pattern.
"""
import random


class AxiMemory:
    def __init__(self, dut, seed=0):
        self.dut = dut
        self.rng = random.Random(seed)
        self.bytes = {}
        self.events = []
        self.read = None
        self.write = None
        self.read_payload = None
        self.write_response = None
        self.held_write = None
        self.next_read_error = False
        self.next_write_error = False
        self.next_bad_rid = False
        self.next_bad_bid = False
        self.pause_aw = self.pause_w = self.pause_ar = False
        self.pause_r = self.pause_b = False

    def reset_protocol(self):
        """Cancel transactions on a global reset, preserving external memory."""
        self.read = self.write = None
        self.read_payload = self.write_response = self.held_write = None
        self.next_read_error = self.next_write_error = False
        self.next_bad_rid = self.next_bad_bid = False
        self.pause_aw = self.pause_w = self.pause_ar = False
        self.pause_r = self.pause_b = False

    def value(self, name):
        return int(getattr(self.dut, f"m_axi_{name}").value)

    def set(self, name, value):
        getattr(self.dut, f"m_axi_{name}").value = value

    def load(self, address, count):
        return int.from_bytes(bytes(self.bytes.get(address + i, ((address + i) * 13 + 7) & 255)
                                    for i in range(count)), "little")

    def store(self, address, data, count, mask):
        for byte in range(count):
            if mask & (1 << byte):
                self.bytes[address + byte] = (data >> (8 * byte)) & 255

    def drive(self):
        self.set("awready", int(not self.pause_aw and self.write is None and self.write_response is None and self.rng.randrange(3) != 0))
        self.set("wready", int(not self.pause_w and self.write is not None and self.rng.randrange(4) != 0))
        self.set("arready", int(not self.pause_ar and self.read is None and self.rng.randrange(3) != 0))
        if self.read and self.read_payload is None and not self.pause_r and self.rng.randrange(3) != 0:
            address, beats, width, index, error, bad_id = self.read
            self.read_payload = (self.load(address + index * width, width),
                                 int(index == beats - 1), 2 if error and index == 0 else 0,
                                 1 if bad_id else 0)
        self.set("rvalid", int(self.read_payload is not None))
        for name, value in zip(("rdata", "rlast", "rresp", "rid"), self.read_payload or (0, 0, 0, 0)):
            self.set(name, value)
        self.set("bvalid", int(self.write_response is not None and not self.pause_b))
        response, response_id = self.write_response or (0, 0)
        self.set("bresp", response)
        self.set("bid", response_id)

    def observe(self):
        if self.value("awvalid") and self.value("awready"):
            address, beats, width = self.command("aw")
            self.write = [address, beats, width, 0, self.next_write_error, self.next_bad_bid]
            self.next_write_error = self.next_bad_bid = False
        payload = (self.value("wdata"), self.value("wstrb"), self.value("wlast"))
        if self.held_write is not None:
            assert self.value("wvalid") and payload == self.held_write, "AXI W payload changed while stalled"
        self.held_write = payload if self.value("wvalid") and not self.value("wready") else None
        if self.value("wvalid") and self.value("wready"):
            assert self.write is not None
            address, beats, width, index, error, bad_id = self.write
            assert payload[2] == int(index == beats - 1), "Incorrect WLAST"
            self.store(address + index * width, payload[0], width, payload[1])
            self.write[3] += 1
            if index == beats - 1:
                self.write = None
                self.write_response = (2 if error else 0, 1 if bad_id else 0)
        if self.value("bvalid") and self.value("bready"):
            self.write_response = None
        if self.value("arvalid") and self.value("arready"):
            address, beats, width = self.command("ar")
            self.read = [address, beats, width, 0, self.next_read_error, self.next_bad_rid]
            self.next_read_error = self.next_bad_rid = False
        if self.value("rvalid") and self.value("rready"):
            self.read[3] += 1
            self.read_payload = None
            if self.read[3] == self.read[1]:
                self.read = None

    def command(self, channel):
        address = self.value(f"{channel}addr")
        beats = self.value(f"{channel}len") + 1
        width = 1 << self.value(f"{channel}size")
        assert self.value(f"{channel}burst") == 1
        assert self.value(f"{channel}id") == 0
        assert address % width == 0
        assert address // 4096 == (address + beats * width - 1) // 4096
        self.events.append((channel, address, beats))
        return address, beats, width
