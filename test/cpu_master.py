"""Small AXI-Lite test driver; each bench supplies its own cycle() function."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CpuSample:
    awready: int
    wready: int
    arready: int
    bvalid: int
    bresp: int
    rvalid: int
    rdata: int
    rresp: int


def sample_cpu(dut):
    return CpuSample(
        awready=int(dut.axi_awready_o.value),
        wready=int(dut.axi_wready_o.value),
        arready=int(dut.axi_arready_o.value),
        bvalid=int(dut.axi_bvalid_o.value),
        bresp=int(dut.axi_bresp_o.value),
        rvalid=int(dut.axi_rvalid_o.value),
        rdata=int(dut.axi_rdata_o.value),
        rresp=int(dut.axi_rresp_o.value),
    )


class CpuMaster:
    def __init__(self, dut, cycle):
        self.dut = dut
        self.cycle = cycle

    def initialize(self):
        dut = self.dut
        dut.axi_awvalid_i.value = 0
        dut.axi_awaddr_i.value = 0
        dut.axi_wvalid_i.value = 0
        dut.axi_wdata_i.value = 0
        dut.axi_wstrb_i.value = 0
        dut.axi_bready_i.value = 0
        dut.axi_arvalid_i.value = 0
        dut.axi_araddr_i.value = 0
        dut.axi_rready_i.value = 0

    async def write(self, address, data, strobe=15, *, aw_delay=0, w_delay=0,
                    response_delay=4, status=0):
        dut = self.dut
        dut.axi_awaddr_i.value = address
        dut.axi_wdata_i.value = data
        dut.axi_wstrb_i.value = strobe
        address_sent = data_sent = False
        held_response = None
        waiting = 0
        for cycle in range(20000):
            # Inputs may change immediately after their channel is accepted.
            dut.axi_awaddr_i.value = address ^ 0x4000 if address_sent else address
            dut.axi_wdata_i.value = data ^ 0xFFFFFFFF if data_sent else data
            dut.axi_awvalid_i.value = int(not address_sent and cycle >= aw_delay)
            dut.axi_wvalid_i.value = int(not data_sent and cycle >= w_delay)
            # Waiting for VALID before READY is legal for an AXI receiver.
            dut.axi_bready_i.value = int(held_response is not None and waiting >= response_delay)
            sample = await self.cycle()
            if dut.axi_awvalid_i.value and sample.awready:
                address_sent = True
            if dut.axi_wvalid_i.value and sample.wready:
                data_sent = True
            if sample.bvalid:
                assert address_sent and data_sent, "Premature B response"
                assert sample.bresp == status
                if held_response is not None:
                    assert sample.bresp == held_response
                held_response = sample.bresp
                waiting += 1
                if dut.axi_bready_i.value:
                    break
            elif held_response is not None:
                raise AssertionError("BVALID was withdrawn before acceptance")
        else:
            raise AssertionError(f"Write timeout at {address:#x}")
        dut.axi_awvalid_i.value = 0
        dut.axi_wvalid_i.value = 0
        dut.axi_bready_i.value = 0

    async def read(self, address, *, response_delay=4, status=0):
        dut = self.dut
        dut.axi_araddr_i.value = address
        address_sent = False
        held_response = None
        waiting = 0
        for _ in range(20000):
            dut.axi_araddr_i.value = address ^ 0x4000 if address_sent else address
            dut.axi_arvalid_i.value = int(not address_sent)
            dut.axi_rready_i.value = int(held_response is not None and waiting >= response_delay)
            sample = await self.cycle()
            if dut.axi_arvalid_i.value and sample.arready:
                address_sent = True
            if sample.rvalid:
                assert address_sent, "Premature R response"
                assert sample.rresp == status
                response = (sample.rdata, sample.rresp)
                if held_response is not None:
                    assert response == held_response, "R changed while stalled"
                held_response = response
                waiting += 1
                if dut.axi_rready_i.value:
                    break
            elif held_response is not None:
                raise AssertionError("RVALID was withdrawn before acceptance")
        else:
            raise AssertionError(f"Read timeout at {address:#x}")
        dut.axi_arvalid_i.value = 0
        dut.axi_rready_i.value = 0
        return held_response[0]
