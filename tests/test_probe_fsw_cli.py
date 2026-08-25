import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "probe_fsw.py"
)


def load_probe_module():
    spec = importlib.util.spec_from_file_location(
        "probe_fsw",
        SCRIPT_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def test_probe_parser_basic_configuration():
    module = load_probe_module()
    parser = module.build_parser()

    args = parser.parse_args(
        [
            "--resource",
            "TCPIP0::192.168.1.20::inst0::INSTR",
            "--spectrum",
            "--center-hz",
            "650000000",
            "--span-hz",
            "100000000",
            "--rbw-hz",
            "1000000",
            "--vbw-hz",
            "3000000",
            "--trigger-source",
            "EXT",
            "--channel",
            "1",
            "--window",
            "2",
            "--trace",
            "3",
        ]
    )

    assert (
        args.resource
        == "TCPIP0::192.168.1.20::inst0::INSTR"
    )

    assert args.spectrum is True

    assert args.center_hz == 650e6
    assert args.span_hz == 100e6
    assert args.rbw_hz == 1e6
    assert args.vbw_hz == 3e6

    assert args.trigger_source == "EXT"

    assert args.channel == 1
    assert args.window == 2
    assert args.trace == 3


def test_probe_resource_is_required():
    module = load_probe_module()
    parser = module.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])
