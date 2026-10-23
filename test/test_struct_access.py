"""Check native VPI access to packed struct fields without a wrapper."""
import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def native_struct_fields(dut):
    # Use different field widths, including an enum and a 32-bit address.
    dut._log.info("Native field handle: %s", type(dut["command_i.mem_addr"]).__name__)
    for name in ("mem_addr", "nb_transfer", "cache_addr", "wb_rf"):
        assert dut[f"command_i.{name}"] is not None

    # Check both the individual fields and the packed value observed by RTL.
    # Multiple field writes in one cycle must preserve neighboring fields.
    cache_width = len(dut["command_i.cache_addr"])
    for address, length, cache, operation in (
        (0, 0, 0, 0),
        (0xFEDCBA98, 255, (1 << cache_width) - 1, 1),
        (0x12345670, 63, 17, 0),
    ):
        dut["command_i.mem_addr"].value = address
        dut["command_i.nb_transfer"].value = length
        dut["command_i.cache_addr"].value = cache
        dut["command_i.wb_rf"].value = operation
        await Timer(1, unit="ns")
        expected = (((address << 8) | length) << cache_width | cache) << 1 | operation
        assert int(dut.packed_o.value) == expected
        assert int(dut.address_o.value) == address
        for name, expected_field in (
            ("mem_addr", address), ("nb_transfer", length),
            ("cache_addr", cache), ("wb_rf", operation),
        ):
            assert int(dut[f"command_o.{name}"].value) == expected_field

    # Updating one field must preserve the other fields in the packed value.
    dut["command_i.nb_transfer"].value = 7
    await Timer(1, unit="ns")
    assert int(dut["command_o.mem_addr"].value) == 0x12345670
    assert int(dut["command_o.cache_addr"].value) == 17
    assert int(dut["command_o.nb_transfer"].value) == 7


def test_struct_access(runner):
    runner.test(hdl_toplevel="struct_access", test_module=__name__, test_args=["--trace"])
