from dataclasses import dataclass, field

from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)


@dataclass
class CaptureContext:
    """一次采集任务运行期间共享的数据上下文。

    正式采集格式从 Phase 8 调试结束后重新从 schema v1 起步。EXT 配对
    样本明确包含两份频谱（EXT/IMM）和两次独立示波器采集
    （DELAY/CYCLE_COUNT），不再把两次示波器采集合并成一个 waveform。

    ``spectrum`` / ``waveform`` 暂时仅供旧的内部调试 workflow 使用；正式
    Recipe 使用 ``spectrum_ext`` / ``spectrum_imm``、``waveform_delay`` /
    ``waveform_cycle``。
    """

    spectrum: SpectrumResult | None = None
    spectrum_ext: SpectrumResult | None = None
    spectrum_imm: SpectrumResult | None = None

    delay: MeasurementResult | None = None
    cycle_count: MeasurementResult | None = None
    waveform: WaveformResult | None = None
    waveform_delay: WaveformResult | None = None
    waveform_cycle: WaveformResult | None = None

    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def schema_version(self) -> int:
        # 正式数据格式重新从 v1 开始；调试数据不承担兼容约束。
        return 1

    @property
    def is_complete(self) -> bool:
        """旧内部联合采集完整性，仅用于尚未删除的调试 workflow。"""
        return all(
            (
                self.spectrum is not None,
                self.delay is not None,
                self.cycle_count is not None,
                self.waveform is not None,
            )
        )

    @property
    def is_paired_complete(self) -> bool:
        """正式 EXT+IMM 训练样本完整性。"""
        return all(
            (
                self.spectrum_ext is not None,
                self.spectrum_imm is not None,
                self.delay is not None,
                self.cycle_count is not None,
                self.waveform_delay is not None,
                self.waveform_cycle is not None,
            )
        )

    @property
    def is_dsox_complete(self) -> bool:
        return all(
            (
                self.delay is not None,
                self.cycle_count is not None,
                self.waveform_delay is not None,
                self.waveform_cycle is not None,
            )
        )

    @property
    def capture_complete(self) -> bool:
        recipe = str(self.metadata.get("recipe", "")).lower()
        if recipe == "ext_imm_pair":
            return self.is_paired_complete
        if recipe == "imm_spectrum_only":
            return self.spectrum_imm is not None
        if recipe == "dsox_only":
            return self.is_dsox_complete
        return self.is_complete
