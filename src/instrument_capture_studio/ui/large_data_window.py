"""Scalable Batch -> frequency -> Job navigation for large result sets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidgetItem,
    QWidget,
)

from instrument_capture_studio.data.data_browser import (
    BatchFrequencySummary,
    BatchJobSummary,
    list_batch_frequency_groups,
    list_recent_batches,
    list_recent_jobs,
)
from instrument_capture_studio.ui.long_session_window import MainWindow as LongSessionWindow
from instrument_capture_studio.ui.product_window import _FORMAL_JOB_FILES, _file_description


_PAGE_SIZE = 100
_KIND_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_MANIFEST_ROLE = int(Qt.ItemDataRole.UserRole) + 2
_FREQUENCY_ROLE = int(Qt.ItemDataRole.UserRole) + 3
_LOADED_ROLE = int(Qt.ItemDataRole.UserRole) + 4


class MainWindow(LongSessionWindow):
    """v1.0.1 workspace with lazy navigation for thousands of Batch Jobs."""

    def __init__(self) -> None:
        self._data_frequency_jobs: dict[tuple[str, int], tuple[BatchJobSummary, ...]] = {}
        super().__init__()
        self._install_large_data_filters()
        self.data_tree.itemExpanded.connect(self._on_large_data_item_expanded)
        self.data_tree.itemClicked.connect(self._on_large_data_item_clicked)
        self._refresh_data_tree()
        self.statusBar().showMessage("就绪 · v1.0.1")

    # ------------------------------------------------------------------
    # Filter controls
    # ------------------------------------------------------------------
    def _install_large_data_filters(self) -> None:
        group = self.data_tree.parentWidget()
        layout = group.layout() if group is not None else None
        if layout is None:
            return

        bar = QWidget(group)
        bar.setObjectName("largeDataFilterBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.data_search_edit = QLineEdit(bar)
        self.data_search_edit.setObjectName("dataSearchEdit")
        self.data_search_edit.setClearButtonEnabled(True)
        self.data_search_edit.setPlaceholderText(
            "搜索频率 / Job ID，例如 700、705MHz、n0035"
        )

        self.data_status_filter = QComboBox(bar)
        self.data_status_filter.setObjectName("dataStatusFilter")
        self.data_status_filter.addItems(("全部状态", "成功", "失败/取消"))

        self.data_filter_refresh_button = QPushButton("应用筛选", bar)
        self.data_filter_refresh_button.setObjectName("dataFilterRefreshButton")

        row.addWidget(QLabel("数据筛选", bar))
        row.addWidget(self.data_search_edit, 1)
        row.addWidget(self.data_status_filter)
        row.addWidget(self.data_filter_refresh_button)

        # The product toolbar is already near the top of the data card. Put the
        # filter row immediately below it and above the master/detail splitter.
        insert_at = max(0, layout.count() - 1)
        layout.insertWidget(insert_at, bar)

        self._data_filter_timer = QTimer(self)
        self._data_filter_timer.setSingleShot(True)
        self._data_filter_timer.setInterval(300)
        self._data_filter_timer.timeout.connect(self._refresh_data_tree)
        self.data_search_edit.textChanged.connect(self._data_filter_timer.start)
        self.data_status_filter.currentIndexChanged.connect(self._refresh_data_tree)
        self.data_filter_refresh_button.clicked.connect(self._refresh_data_tree)

    # ------------------------------------------------------------------
    # Tree construction
    # ------------------------------------------------------------------
    def _refresh_data_tree(self) -> None:
        if not hasattr(self, "data_tree"):
            return

        self.data_tree.clear()
        self._data_frequency_jobs.clear()
        root = Path(self.output_root_edit.text()).expanduser()
        if not root.exists():
            self.data_tree.addTopLevelItem(QTreeWidgetItem(["暂无数据", str(root)]))
            if hasattr(self, "batch_report_button"):
                self._update_result_actions()
            if hasattr(self, "data_empty_hint"):
                self._refresh_data_empty_hint()
            return

        query = self._data_query()
        state_filter = self._data_state_filter()
        filters_active = bool(query) or state_filter != "all"

        batches = list_recent_batches(root, limit=50)
        batch_root = QTreeWidgetItem(
            [
                "批次结果",
                "按 Batch → 频率展开；每次加载 100 个 Job",
            ]
        )
        self.data_tree.addTopLevelItem(batch_root)

        visible_batches = 0
        for batch in batches:
            groups = None
            if filters_active:
                groups = self._matching_groups(batch.manifest_path)
                if not groups:
                    continue

            plan_parts = []
            if batch.start_hz is not None and batch.stop_hz is not None:
                plan_parts.append(
                    f"{batch.start_hz / 1e6:g}-{batch.stop_hz / 1e6:g} MHz"
                )
            if batch.step_hz is not None:
                plan_parts.append(f"step {batch.step_hz / 1e6:g} MHz")
            if batch.captures_per_frequency is not None:
                plan_parts.append(f"x{batch.captures_per_frequency}")
            summary = (
                f"{batch.state.upper()} · "
                f"{batch.completed_captures}/{batch.total_captures}"
            )
            if batch.failed_jobs:
                summary += f" · failed jobs {batch.failed_jobs}"
            if plan_parts:
                summary += " · " + " · ".join(plan_parts)

            node = QTreeWidgetItem([batch.batch_id, summary])
            node.setData(0, Qt.ItemDataRole.UserRole, str(batch.manifest_path))
            node.setData(0, _KIND_ROLE, "batch")
            node.setData(0, _MANIFEST_ROLE, str(batch.manifest_path))
            node.setData(0, _LOADED_ROLE, False)
            batch_root.addChild(node)
            visible_batches += 1

            directory_node = QTreeWidgetItem(
                ["打开批次目录", str(batch.manifest_path.parent)]
            )
            directory_node.setData(
                0,
                Qt.ItemDataRole.UserRole,
                str(batch.manifest_path.parent),
            )
            directory_node.setData(0, _KIND_ROLE, "directory")
            node.addChild(directory_node)

            if groups is None:
                placeholder = QTreeWidgetItem(
                    ["展开查看全部频率", "不会一次加载所有 Job"]
                )
                placeholder.setData(0, _KIND_ROLE, "batch_placeholder")
                node.addChild(placeholder)
            else:
                self._populate_frequency_nodes(node, groups)
                node.setExpanded(True)

        batch_root.setText(1, f"{visible_batches} 个 Batch · 按频率懒加载全部 Job")
        batch_root.setExpanded(True)

        # Keep the familiar recent-100 entry as a fast shortcut. It is no longer
        # the only way to reach Job data; all older Jobs live in the Batch tree.
        recent = list_recent_jobs(root, limit=100)
        recent = tuple(job for job in recent if self._recent_job_matches(job))
        job_root = QTreeWidgetItem(
            ["快速访问 · 最近 100 个 Job", f"当前显示 {len(recent)} 个"]
        )
        self.data_tree.addTopLevelItem(job_root)
        for job in recent:
            self._append_recent_job_node(job_root, job, root)
        job_root.setExpanded(False)

        if visible_batches == 0 and not recent:
            message = "没有符合筛选条件的数据" if filters_active else "暂无可识别的 Batch / Job"
            self.data_tree.addTopLevelItem(QTreeWidgetItem([message, str(root)]))

        if hasattr(self, "batch_report_button"):
            self._update_result_actions()
        if hasattr(self, "data_empty_hint"):
            self._refresh_data_empty_hint()

    def _matching_groups(
        self,
        manifest_path: Path,
    ) -> tuple[BatchFrequencySummary, ...]:
        groups = list_batch_frequency_groups(manifest_path)
        matches = []
        for group in groups:
            jobs = self._filtered_jobs(group)
            frequency_matches = self._query_matches_frequency(group)
            if self._data_query() and not frequency_matches and not jobs:
                continue
            if self._data_state_filter() != "all" and not jobs:
                continue
            if frequency_matches:
                jobs = self._state_filtered_jobs(group.jobs)
            matches.append(
                BatchFrequencySummary(
                    frequency_index=group.frequency_index,
                    frequency_hz=group.frequency_hz,
                    directory=group.directory,
                    jobs=jobs,
                )
            )
        return tuple(matches)

    def _populate_frequency_nodes(
        self,
        batch_item: QTreeWidgetItem,
        groups: tuple[BatchFrequencySummary, ...] | None = None,
    ) -> None:
        manifest_text = batch_item.data(0, _MANIFEST_ROLE)
        if not manifest_text:
            return
        manifest_path = Path(str(manifest_text))
        if groups is None:
            groups = list_batch_frequency_groups(manifest_path)

        # Remove only lazy placeholders/frequency nodes; keep the directory row.
        for index in range(batch_item.childCount() - 1, -1, -1):
            child = batch_item.child(index)
            if child.data(0, _KIND_ROLE) in {
                "batch_placeholder",
                "frequency",
                "info",
            }:
                batch_item.takeChild(index)

        added = 0
        for group in groups:
            jobs = group.jobs if self._filters_active() else tuple(group.jobs)
            if self._filters_active() and groups is not None:
                # When groups were supplied by _matching_groups they are already
                # filtered. When expanding after a filter refresh, apply again.
                jobs = self._filtered_jobs(group)
                if self._query_matches_frequency(group):
                    jobs = self._state_filtered_jobs(group.jobs)
                if self._data_query() and not self._query_matches_frequency(group) and not jobs:
                    continue
                if self._data_state_filter() != "all" and not jobs:
                    continue

            key = (str(manifest_path), group.frequency_index)
            self._data_frequency_jobs[key] = tuple(jobs)
            success = sum(1 for job in jobs if job.state.lower() == "succeeded")
            failed = len(jobs) - success
            summary = f"{len(jobs)} 个 Job · {success} 成功"
            if failed:
                summary += f" · {failed} 失败/取消"
            if self._filters_active():
                summary += " · 已筛选"

            frequency_item = QTreeWidgetItem(
                [f"{group.frequency_hz / 1e6:g} MHz", summary]
            )
            location = group.directory if group.directory.exists() else manifest_path.parent
            frequency_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                str(location),
            )
            frequency_item.setData(0, _KIND_ROLE, "frequency")
            frequency_item.setData(0, _MANIFEST_ROLE, str(manifest_path))
            frequency_item.setData(0, _FREQUENCY_ROLE, group.frequency_index)
            frequency_item.setData(0, _LOADED_ROLE, 0)
            batch_item.addChild(frequency_item)
            added += 1

            if jobs:
                placeholder = QTreeWidgetItem(
                    [
                        f"展开加载前 {min(_PAGE_SIZE, len(jobs))} 个 Job",
                        f"共 {len(jobs)} 个，可继续加载更多",
                    ]
                )
                placeholder.setData(0, _KIND_ROLE, "frequency_placeholder")
                frequency_item.addChild(placeholder)
            else:
                empty = QTreeWidgetItem(["暂无已记录 Job", "该频率尚未采集或无匹配结果"])
                empty.setData(0, _KIND_ROLE, "info")
                frequency_item.addChild(empty)

        if added == 0:
            empty = QTreeWidgetItem(["暂无匹配频率", "请调整搜索或状态筛选"])
            empty.setData(0, _KIND_ROLE, "info")
            batch_item.addChild(empty)
        batch_item.setData(0, _LOADED_ROLE, True)

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------
    def _on_large_data_item_expanded(self, item: QTreeWidgetItem) -> None:
        kind = item.data(0, _KIND_ROLE)
        if kind == "batch" and not bool(item.data(0, _LOADED_ROLE)):
            self._populate_frequency_nodes(item)
            return
        if kind == "frequency":
            self._load_frequency_job_page(item)

    def _on_large_data_item_clicked(
        self,
        item: QTreeWidgetItem,
        _column: int,
    ) -> None:
        kind = item.data(0, _KIND_ROLE)
        if kind == "load_more":
            parent = item.parent()
            if parent is not None:
                parent.removeChild(item)
                self._load_frequency_job_page(parent)
            return
        if kind == "batch_placeholder":
            parent = item.parent()
            if parent is not None:
                self._populate_frequency_nodes(parent)
                parent.setExpanded(True)
            return
        if kind == "frequency_placeholder":
            parent = item.parent()
            if parent is not None:
                parent.removeChild(item)
                self._load_frequency_job_page(parent)
                parent.setExpanded(True)

    def _load_frequency_job_page(self, frequency_item: QTreeWidgetItem) -> None:
        manifest_text = frequency_item.data(0, _MANIFEST_ROLE)
        frequency_index = frequency_item.data(0, _FREQUENCY_ROLE)
        if not manifest_text or frequency_index is None:
            return
        key = (str(manifest_text), int(frequency_index))
        jobs = self._data_frequency_jobs.get(key, ())
        loaded = int(frequency_item.data(0, _LOADED_ROLE) or 0)

        # Remove the initial placeholder before the first page.
        if loaded == 0:
            for index in range(frequency_item.childCount() - 1, -1, -1):
                child = frequency_item.child(index)
                if child.data(0, _KIND_ROLE) in {"frequency_placeholder", "info"}:
                    frequency_item.takeChild(index)

        end = min(len(jobs), loaded + _PAGE_SIZE)
        for job in jobs[loaded:end]:
            self._append_batch_job_node(frequency_item, job)
        frequency_item.setData(0, _LOADED_ROLE, end)

        if end < len(jobs):
            remaining = len(jobs) - end
            more = QTreeWidgetItem(
                [
                    f"加载更多 {min(_PAGE_SIZE, remaining)} 个…",
                    f"已显示 {end}/{len(jobs)}",
                ]
            )
            more.setData(0, _KIND_ROLE, "load_more")
            frequency_item.addChild(more)

    def _append_batch_job_node(
        self,
        parent: QTreeWidgetItem,
        job: BatchJobSummary,
    ) -> None:
        detail = (
            f"{job.state.upper()} · 样本 {job.capture_index}"
            f" · attempt {job.attempt}"
        )
        node = QTreeWidgetItem([job.job_id, detail])
        node.setData(0, Qt.ItemDataRole.UserRole, str(job.directory))
        node.setData(0, _KIND_ROLE, "job")
        parent.addChild(node)
        self._append_job_files(node, job.directory)

    def _append_recent_job_node(self, parent, job, root: Path) -> None:
        try:
            relative = job.directory.relative_to(root)
        except ValueError:
            relative = job.directory
        node = QTreeWidgetItem(
            [job.job_id, f"{job.state.upper()} · {relative}"]
        )
        node.setData(0, Qt.ItemDataRole.UserRole, str(job.directory))
        node.setData(0, _KIND_ROLE, "recent_job")
        parent.addChild(node)
        self._append_job_files(node, job.directory)

    @staticmethod
    def _append_job_files(node: QTreeWidgetItem, directory: Path) -> None:
        for filename in _FORMAL_JOB_FILES:
            path = directory / filename
            if not path.exists():
                continue
            child = QTreeWidgetItem([filename, _file_description(path)])
            child.setData(0, Qt.ItemDataRole.UserRole, str(path))
            child.setData(0, _KIND_ROLE, "file")
            node.addChild(child)

    # ------------------------------------------------------------------
    # Search / state filtering
    # ------------------------------------------------------------------
    def _data_query(self) -> str:
        if not hasattr(self, "data_search_edit"):
            return ""
        return self.data_search_edit.text().strip().lower().replace(" ", "")

    def _data_state_filter(self) -> str:
        if not hasattr(self, "data_status_filter"):
            return "all"
        return {0: "all", 1: "succeeded", 2: "problem"}.get(
            self.data_status_filter.currentIndex(),
            "all",
        )

    def _filters_active(self) -> bool:
        return bool(self._data_query()) or self._data_state_filter() != "all"

    def _state_filtered_jobs(
        self,
        jobs: tuple[BatchJobSummary, ...],
    ) -> tuple[BatchJobSummary, ...]:
        state_filter = self._data_state_filter()
        if state_filter == "all":
            return tuple(jobs)
        if state_filter == "succeeded":
            return tuple(job for job in jobs if job.state.lower() == "succeeded")
        return tuple(job for job in jobs if job.state.lower() != "succeeded")

    def _filtered_jobs(
        self,
        group: BatchFrequencySummary,
    ) -> tuple[BatchJobSummary, ...]:
        jobs = self._state_filtered_jobs(group.jobs)
        query = self._data_query()
        if not query or self._query_matches_frequency(group):
            return jobs
        matches = []
        for job in jobs:
            searchable = (
                f"{job.job_id} n{job.capture_index:04d} "
                f"{job.capture_index} {job.state}"
            ).lower().replace(" ", "")
            if query in searchable:
                matches.append(job)
        return tuple(matches)

    def _query_matches_frequency(self, group: BatchFrequencySummary) -> bool:
        query = self._data_query()
        if not query:
            return False
        mhz = group.frequency_hz / 1e6
        text = (
            f"{mhz:g} {mhz:g}mhz f{group.frequency_index:03d} "
            f"f{group.frequency_index:03d}_{mhz:g}mhz"
        ).lower().replace(" ", "")
        return query in text

    def _recent_job_matches(self, job) -> bool:
        state_filter = self._data_state_filter()
        if state_filter == "succeeded" and job.state.lower() != "succeeded":
            return False
        if state_filter == "problem" and job.state.lower() == "succeeded":
            return False
        query = self._data_query()
        if not query:
            return True
        return query in job.job_id.lower().replace(" ", "")
