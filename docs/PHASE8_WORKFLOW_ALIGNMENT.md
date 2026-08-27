# Phase 8 Workflow Alignment

This document captures the v1.0 acquisition semantics confirmed during real hardware use.

## 1. Separate “what to capture” from “how to repeat it”

The product has two independent dimensions.

### Capture Recipe

1. `ext_paired` — DSO-X + FSW EXT + one additional FSW IMM spectrum saved as one logical training sample.
2. `spectrum_imm` — FSW IMM spectrum only.
3. `scope_only` — DSO-X only.

### Run Strategy

1. single
2. frequency sweep
3. fixed-frequency repeat

A scope-only recipe does not need a frequency sweep. The UI should disable combinations that do not make sense instead of requiring unused instruments.

## 2. EXT paired recipe

A logical sample is atomic. Proposed sequence:

1. Configure FSW frequency/span/bandwidth.
2. Set FSW trigger to EXT.
3. Arm FSW before the hardware trigger occurs.
4. Execute the DSO-X acquisition that produces/participates in the hardware trigger.
5. Wait for and read the completed EXT trace.
6. Set FSW trigger to IMM.
7. Acquire one IMM trace.
8. Save DSO-X data + EXT trace + IMM trace together.

The extra IMM trace is treated as paired data for the same frequency/repetition index and does not advance the Batch repetition counter by itself. If the dataset later needs EXT and IMM to be counted as separate training examples, that is a labeling/export concern rather than a reason to split the hardware transaction.

The platform FSW driver currently exposes `acquire_trace_ascii()`, which combines arm/wait/read. v1 needs a lower-level split such as `arm_single_trace()` plus `wait_and_read_trace()` so the commercial workflow can place the DSO-X action between FSW arm and FSW read without moving product semantics into the driver repository.

## 3. Scope channel

Waveform channel must be explicit in the GUI. First-run default is Channel 1; later runs restore the saved user value.

## 4. Data schema v2

One logical sample should keep paired data in one Job/sample directory. Suggested artifact names:

- `job.json`
- `metadata.json`
- `spectrum_ext.csv` / `spectrum_ext.npz` when applicable
- `spectrum_imm.csv` / `spectrum_imm.npz` when applicable
- `waveform.csv` / `waveform.npz` when applicable

Readers/reporting must remain able to open existing schema-v1 data.

## 5. Pause / stop / resume

### Pause

Pause is cooperative and happens at a logical-sample boundary. Completed samples remain committed. The process may keep its current instrument session while paused.

### Stop

Stop releases instrument sessions but leaves the Batch resumable.

### Resume after stop or process exit

The Batch manifest stores a durable cursor. On restart the GUI detects incomplete batches and offers `Continue previous task`.

If a process exits halfway through a paired sample, do not splice partial old data with new data. Mark that attempt incomplete and rerun the whole logical sample with a new attempt ID.

## 6. Timing telemetry

Every node should record wall-clock timestamps and monotonic duration:

- `started_at`
- `finished_at`
- `duration_ms`
- `state`
- `error` if any

At minimum record FSW configure, EXT arm, DSO-X acquisition, EXT wait/read, IMM acquisition, DSO-X measurement nodes, save, and total Job duration. Batch reports can later calculate average/P95/max timings.
