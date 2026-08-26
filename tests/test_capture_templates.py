from instrument_capture_studio.data.capture_templates import CaptureTemplateStore


def test_capture_template_round_trip(tmp_path):
    store = CaptureTemplateStore(tmp_path / "templates")

    record = store.save(
        "700-800MHz",
        {
            "sweep/start_mhz": "700",
            "sweep/stop_mhz": "800",
            "sweep/captures_per_frequency": 100,
        },
    )

    assert record.name == "700-800MHz"
    assert store.list_names() == ("700-800MHz",)

    loaded = store.load("700-800MHz")
    assert loaded.values["sweep/start_mhz"] == "700"
    assert loaded.values["sweep/captures_per_frequency"] == 100

    store.delete("700-800MHz")
    assert store.list_names() == ()


def test_capture_template_rejects_windows_invalid_name(tmp_path):
    store = CaptureTemplateStore(tmp_path / "templates")

    try:
        store.save("bad/name", {})
    except ValueError as exc:
        assert "模板名称" in str(exc)
    else:
        raise AssertionError("invalid template name must fail")
