import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "probe_dsox3034a.py"
)


def load_probe_module():
    spec = importlib.util.spec_from_file_location(
        "probe_dsox3034a",
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
            "TCPIP0::192.168.1.10::inst0::INSTR",
            "--delay",
            "--cycle-count",
            "--waveform",
            "--delay-edge1",
            "+1",
            "--delay-edge2",
            "-1",
            "--cycle-source",
            "CHANnel3",
            "--waveform-channel",
            "2",
        ]
    )

    assert args.delay is True
    assert args.cycle_count is True
    assert args.waveform is True
    assert args.delay_edge1 == "+1"
    assert args.delay_edge2 == "-1"
    assert args.cycle_source == "CHANnel3"
    assert args.waveform_channel == 2


def test_probe_resource_is_required():
    module = load_probe_module()
    parser = module.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])
