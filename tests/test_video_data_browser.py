from PySide6.QtWidgets import QTreeWidgetItem

from instrument_capture_studio.ui.video_trigger_window import MainWindow


def test_video_spectrum_files_are_exposed_in_job_tree(tmp_path):
    for filename in ("spectrum_video.npz", "spectrum_video.csv"):
        (tmp_path / filename).write_bytes(b"video")

    node = QTreeWidgetItem(["job", "SUCCEEDED"])
    MainWindow._append_job_files(node, tmp_path)

    names = {node.child(index).text(0) for index in range(node.childCount())}
    assert "spectrum_video.npz" in names
    assert "spectrum_video.csv" in names
