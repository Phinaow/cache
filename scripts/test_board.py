"""Exercise the programmed cache through its 115200-baud UART interface.

This overwrites the tested DDR addresses. It never programs the FPGA or flash.
Run after programming either RAM backend and releasing the board reset button.
"""
import argparse
import json
import random
import struct
import time

import serial


class Board:
    def __init__(self, port):
        self.port = port
        self.commands = 0

    def exchange(self, request, length):
        self.port.write(request)
        self.port.flush()
        response = self.port.read(length)
        if len(response) != length:
            raise RuntimeError(f"UART timeout: request={request.hex()}, response={response.hex()}")
        self.commands += 1
        return response

    def write(self, address, value, status=b"OKAY"):
        response = self.exchange(b"WRIT" + struct.pack("<II", address, value), 4)
        assert response == status, f"Write {address:#x}: {response!r}"

    def read(self, address, value=None, status=b"OKAY"):
        response = self.exchange(b"READ" + struct.pack("<I", address), 8)
        assert response[4:] == status, f"Read {address:#x}: {response!r}"
        observed = struct.unpack("<I", response[:4])[0]
        if value is not None:
            assert observed == value, f"Read {address:#x}: {observed:#010x} != {value:#010x}"
        return observed


def exercise(board, operations):
    assert board.exchange(b"CMDA", 4) == b"RESP", "UART command handshake failed"
    rng = random.Random(0xCA2026)
    # More than eight lines force dirty evictions; offsets exercise every byte bank.
    addresses = [line * 1024 + offset for line in range(32)
                 for offset in (0, 4, 12, 16, 508, 512, 1008, 1020)]
    addresses.extend((0x1FFFFC00, 0x1FFFFFFC))
    reference = {}
    for address in addresses:
        reference[address] = rng.getrandbits(32)
        board.write(address, reference[address])
    for address in reversed(addresses):
        board.read(address, reference[address])
    for _ in range(operations):
        address = rng.choice(addresses)
        if rng.randrange(2):
            reference[address] = rng.getrandbits(32)
            board.write(address, reference[address])
        else:
            board.read(address, reference[address])
    # Invalid aliases must neither read nor overwrite a resident legal word.
    for address in (1, 0x20000000, 0xFFFFFFFF):
        board.write(address, 0xDEADBEEF, status=b"ERR!")
        board.read(address, status=b"ERR!")
    for address in addresses:
        board.read(address, reference[address])
    return len(addresses)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    parser.add_argument("--operations", type=int, default=1000)
    parser.add_argument("--backend", choices=("ip", "rtl"), required=True)
    parser.add_argument("--output")
    arguments = parser.parse_args()
    started = time.monotonic()
    with serial.Serial(arguments.port, 115200, timeout=3, write_timeout=3,
                       exclusive=True) as port:
        port.reset_input_buffer()
        board = Board(port)
        words = exercise(board, arguments.operations)
    result = dict(result="PASS", backend=arguments.backend, port=arguments.port,
                  commands=board.commands, words=words, random_operations=arguments.operations,
                  seconds=round(time.monotonic() - started, 3))
    rendered = json.dumps(result, indent=2) + "\n"
    print(rendered, end="")
    if arguments.output:
        with open(arguments.output, "w") as output:
            output.write(rendered)


if __name__ == "__main__":
    main()
