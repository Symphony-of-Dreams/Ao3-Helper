import io
from typing import Any, Dict, List, Optional

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PIL import Image
from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from wordcloud import WordCloud

from analysis_engine import AnalysisEngine
from database import get_activity_by_month, get_data_for_charts, get_reread_statistics
from logger_setup import logger
from ui_components import NumericTableWidgetItem
from workers import ExportWorker


class DashboardWindow(QDialog):
    def __init__(self, analysis_engine: AnalysisEngine, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reader Dashboard & Analysis Center")
        self.setMinimumSize(1000, 750)

        self.analysis_engine = analysis_engine
        self.analysis_data: Dict[str, List[Dict[str, Any]]] = {}
        self.chart_data: Dict[str, Any] = {}
        self.current_mask_array: Optional[np.ndarray] = None
        self.last_generated_cloud_image: Optional[Image.Image] = None

        self.word_cloud_debounce_timer = QTimer(self)
        self.word_cloud_debounce_timer.setSingleShot(True)
        self.word_cloud_debounce_timer.setInterval(250)
        self.word_cloud_debounce_timer.timeout.connect(self._update_word_cloud_image)

        self.export_thread: Optional[QThread] = None
        self.export_worker: Optional[ExportWorker] = None
        self.wait_dialog: Optional[QDialog] = None

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.overview_tab = QWidget()
        self.analysis_tab = QWidget()
        self.wordcloud_tab = QWidget()

        self._build_overview_tab_ui()
        self._build_analysis_tab_ui()
        self._build_wordcloud_tab_ui()

        self.tabs.addTab(self.overview_tab, "📊 Overview")
        self.tabs.addTab(self.analysis_tab, "🧠 True Favorites Analysis")
        self.tabs.addTab(self.wordcloud_tab, "☁️ Pro Word Clouds")

    def populate_data_and_show(self) -> None:
        """
        Fetches the latest data and populates the already-built UI components.
        This is the main entry point to be called from the main window.
        """
        logger.debug("Dashboard: Fetching fresh data and populating UI.")

        self.analysis_data = self.analysis_engine.get_analysis_results()
        self.chart_data = get_data_for_charts(chart_filter="lette")

        self._populate_overview_tab()
        self._populate_analysis_tab()
        self._populate_wordcloud_tab()

        self.exec()

    def _build_overview_tab_ui(self) -> None:
        layout = QHBoxLayout(self.overview_tab)

        left_panel_layout = QVBoxLayout()
        self.reread_group = QGroupBox("🏆 Most Reread Works (From History)")
        self.reread_layout = QVBoxLayout(self.reread_group)
        left_panel_layout.addWidget(self.reread_group)
        left_panel_layout.addStretch()

        right_panel_layout = QVBoxLayout()
        activity_group = QGroupBox("📈 Activity Timeline")
        activity_group_layout = QVBoxLayout(activity_group)
        self._setup_activity_chart_controls(activity_group_layout)
        right_panel_layout.addWidget(activity_group)

        layout.addLayout(left_panel_layout, 1)
        layout.addLayout(right_panel_layout, 2)

    def _build_analysis_tab_ui(self) -> None:
        layout = QVBoxLayout(self.analysis_tab)
        info_label = QLabel(
            "This analysis calculates a weighted score for every author, tag, fandom, etc., based on your reading habits.<br>"  # noqa: E501
            "<b>Total Score (TWS):</b> The overall impact. Higher means more time spent.<br>"
            "<b>Intensity (AWS):</b> The average score per fic. Higher means deeper interest in fewer works."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.analysis_tabs = QTabWidget()
        layout.addWidget(self.analysis_tabs)

        self.authors_table = self._create_analysis_table_widget()
        self.fandoms_table = self._create_analysis_table_widget()
        self.tags_table = self._create_analysis_table_widget()
        self.relationships_table = self._create_analysis_table_widget()
        self.characters_table = self._create_analysis_table_widget()

        self.analysis_tabs.addTab(self.authors_table, "✒️ Authors")
        self.analysis_tabs.addTab(self.fandoms_table, "🌌 Fandoms")
        self.analysis_tabs.addTab(self.tags_table, "🏷️ Tags")
        self.analysis_tabs.addTab(self.relationships_table, "💞 Relationships")
        self.analysis_tabs.addTab(self.characters_table, "👥 Characters")

    def _build_wordcloud_tab_ui(self) -> None:
        layout = QVBoxLayout(self.wordcloud_tab)
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("<b>Show Word Cloud For:</b>"))
        self.cloud_source_combo = QComboBox()
        self.cloud_source_combo.addItem("🏷️ Tags", "tags")
        self.cloud_source_combo.addItem("🌌 Fandoms", "fandoms")
        self.cloud_source_combo.addItem("💞 Relationships", "relationships")
        self.cloud_source_combo.addItem("✒️ Authors", "authors")
        self.cloud_source_combo.addItem("👥 Characters", "characters")
        source_layout.addWidget(self.cloud_source_combo)
        source_layout.addStretch()
        layout.addLayout(source_layout)

        self.cloud_view = QGraphicsView()
        self.cloud_scene = QGraphicsScene()
        self.cloud_view.setScene(self.cloud_scene)
        layout.addWidget(self.cloud_view)

        controls_group = QGroupBox("Customization")
        controls_layout = QVBoxLayout(controls_group)

        row1_layout = QHBoxLayout()
        row1_layout.addWidget(QLabel("Max Words:"))
        self.max_words_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_words_slider.setRange(10, 300)
        self.max_words_slider.setValue(100)
        self.max_words_spinbox = QSpinBox()
        self.max_words_spinbox.setRange(10, 300)
        self.max_words_spinbox.setValue(100)
        self.max_words_slider.valueChanged.connect(self.max_words_spinbox.setValue)
        self.max_words_spinbox.valueChanged.connect(self.max_words_slider.setValue)
        row1_layout.addWidget(self.max_words_slider)
        row1_layout.addWidget(self.max_words_spinbox)
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(QLabel("Size Variance:"))
        self.scaling_slider = QSlider(Qt.Orientation.Horizontal)
        self.scaling_slider.setRange(0, 100)
        self.scaling_slider.setValue(50)
        self.scaling_label = QLabel("0.50")
        self.scaling_slider.valueChanged.connect(lambda v: self.scaling_label.setText(f"{v/100:.2f}"))
        row2_layout.addWidget(self.scaling_slider)
        row2_layout.addWidget(self.scaling_label)
        row3_layout = QHBoxLayout()
        row3_layout.addWidget(QLabel("Color Theme:"))
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(
            ["viridis", "plasma", "inferno", "magma", "cividis", "coolwarm", "spring", "Pastel1"]
        )
        row3_layout.addWidget(self.colormap_combo)
        self.bg_button = QPushButton("🌙 Dark Mode")
        self.bg_button.setCheckable(True)
        row3_layout.addWidget(self.bg_button)
        row4_layout = QHBoxLayout()
        self.mask_button = QPushButton("🖼️ Apply Image Mask...")
        self.remove_mask_button = QPushButton("🚫 Remove Mask")
        self.remove_mask_button.setEnabled(False)
        row4_layout.addWidget(self.mask_button)
        row4_layout.addWidget(self.remove_mask_button)
        row4_layout.addStretch()
        self.save_cloud_button = QPushButton("💾 Export Image...")
        row4_layout.addWidget(self.save_cloud_button)
        controls_layout.addLayout(row1_layout)
        controls_layout.addLayout(row2_layout)
        controls_layout.addLayout(row3_layout)
        controls_layout.addLayout(row4_layout)
        layout.addWidget(controls_group)

        self.cloud_source_combo.currentIndexChanged.connect(self._update_word_cloud_image)
        self.max_words_slider.valueChanged.connect(self._on_slider_value_changed)
        self.scaling_slider.valueChanged.connect(self._on_slider_value_changed)
        self.colormap_combo.currentIndexChanged.connect(self._update_word_cloud_image)
        self.bg_button.toggled.connect(self._update_word_cloud_image)
        self.mask_button.clicked.connect(self._select_mask_image)
        self.remove_mask_button.clicked.connect(self._remove_mask)
        self.save_cloud_button.clicked.connect(self._start_export_process)

    def _populate_overview_tab(self):
        self._populate_reread_stats()
        self._create_activity_chart()

    def _populate_analysis_tab(self):
        self._populate_analysis_table(self.authors_table, self.analysis_data.get("authors", []))
        self._populate_analysis_table(self.fandoms_table, self.analysis_data.get("fandoms", []))
        self._populate_analysis_table(self.tags_table, self.analysis_data.get("tags", []))
        self._populate_analysis_table(self.relationships_table, self.analysis_data.get("relationships", []))
        self._populate_analysis_table(self.characters_table, self.analysis_data.get("characters", []))

    def _populate_wordcloud_tab(self):
        self._update_word_cloud_image()

    def _clear_layout(self, layout: Optional[QLayout]):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                else:
                    sub_layout = item.layout()
                    if sub_layout:
                        self._clear_layout(sub_layout)

    def _populate_reread_stats(self) -> None:
        self._clear_layout(self.reread_layout)
        top_fics = get_reread_statistics(limit=5)
        if not top_fics:
            self.reread_layout.addWidget(QLabel("<i>Start revisiting fics to see your favorites here!</i>"))
            return
        icons = ["🥇", "🥈", "🥉", "4.", "5."]
        for i, fic in enumerate(top_fics):
            icon = icons[i] if i < len(icons) else f"{i+1}."
            label_text = f"<b>{icon} {fic.get('title', 'N/A')}</b> by {fic.get('author', 'N/A')} ({fic.get('visit_count', 0)} visits)"  # noqa: E501
            label = QLabel(label_text)
            if i < 3:
                label.setStyleSheet("padding: 5px; font-size: 14px;")
            self.reread_layout.addWidget(label)
        self.reread_layout.addStretch()

    def _create_analysis_table_widget(self) -> QTableWidget:
        table = QTableWidget()
        headers = ["Name", "Total Score (TWS)", "Intensity (AWS)", "Unique Fics"]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSortingEnabled(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        return table

    def _populate_analysis_table(self, table: QTableWidget, data: List[Dict[str, Any]]) -> None:
        table.setSortingEnabled(False)
        table.clearContents()
        table.setRowCount(len(data))
        for row, item in enumerate(data):
            table.setItem(row, 0, QTableWidgetItem(str(item.get("name"))))
            table.setItem(row, 1, NumericTableWidgetItem(str(item.get("tws"))))
            table.setItem(row, 2, NumericTableWidgetItem(str(item.get("aws"))))
            table.setItem(row, 3, NumericTableWidgetItem(str(item.get("fic_count"))))
        table.setSortingEnabled(True)
        table.sortByColumn(1, Qt.SortOrder.DescendingOrder)

    def _setup_activity_chart_controls(self, parent_layout: QVBoxLayout):
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("<b>Show Data For:</b>"))
        self.view_filter_combo = QComboBox()
        self.view_filter_combo.addItems(["All Entries", "My Library", "My History"])
        controls_layout.addWidget(self.view_filter_combo)
        controls_layout.addSpacing(20)
        controls_layout.addWidget(QLabel("<b>Group By Date Of:</b>"))
        self.date_filter_combo = QComboBox()
        self.date_filter_combo.addItems(["Fic Last Updated", "Date Added to App", "My Last Visit (from History)"])
        controls_layout.addWidget(self.date_filter_combo)
        controls_layout.addStretch()
        parent_layout.addLayout(controls_layout)
        self.chart_layout = QVBoxLayout()
        parent_layout.addLayout(self.chart_layout)
        self.view_filter_combo.currentIndexChanged.connect(self._create_activity_chart)
        self.date_filter_combo.currentIndexChanged.connect(self._create_activity_chart)

    def _create_activity_chart(self) -> None:
        view_filter_map = {0: "all", 1: "library", 2: "history"}
        view_choice = view_filter_map.get(self.view_filter_combo.currentIndex(), "all")
        date_filter_map = {0: "date_updated", 1: "date_added", 2: "last_visit_date"}
        date_choice = date_filter_map.get(self.date_filter_combo.currentIndex(), "date_updated")
        data = get_activity_by_month(view_filter=view_choice, date_field=date_choice)

        self._clear_layout(self.chart_layout)

        if not data:
            self.chart_layout.addWidget(QLabel("<i>No data available for the selected filters.</i>"))
            return

        months, counts = zip(*data)
        fig = Figure(figsize=(10, 5), dpi=100)
        ax = fig.add_subplot(111)
        ax.bar(months, counts, color="#007acc")
        ax.set_title(f"Fics Per Month (Grouped by {self.date_filter_combo.currentText()})")
        ax.set_ylabel("Number of Fics")
        ax.tick_params(axis="x", labelrotation=45)
        fig.tight_layout()
        canvas = FigureCanvas(fig)
        self.chart_layout.addWidget(canvas)

    def _on_slider_value_changed(self):
        self.word_cloud_debounce_timer.start()

    def _select_mask_image(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Mask Image", "", "Images (*.png *.jpg *.jpeg)")
        if filepath:
            try:
                self.current_mask_array = np.array(Image.open(filepath))
                self.remove_mask_button.setEnabled(True)
                self._update_word_cloud_image()
            except Exception as e:
                logger.error(f"Error loading mask image: {e}")
                self.current_mask_array = None

    def _remove_mask(self):
        self.current_mask_array = None
        self.remove_mask_button.setEnabled(False)
        self._update_word_cloud_image()

    def _update_word_cloud_image(self):
        self.cloud_scene.clear()
        entity_key = self.cloud_source_combo.currentData()
        source_data = self.analysis_data.get(entity_key, [])
        if not source_data:
            self.cloud_scene.addText("No data to display for this category.")
            return

        frequencies = {item["name"]: item["tws"] for item in source_data}
        if not frequencies:
            self.cloud_scene.addText("No data to display for this category.")
            return

        wc = WordCloud(
            width=1200,
            height=800,
            scale=2,
            background_color="black" if self.bg_button.isChecked() else "white",
            colormap=self.colormap_combo.currentText(),
            max_words=self.max_words_slider.value(),
            mask=self.current_mask_array,
            contour_width=1,
            contour_color="steelblue",
            relative_scaling=self.scaling_slider.value() / 100.0,
        ).generate_from_frequencies(frequencies)

        self.last_generated_cloud_image = wc.to_image()
        buf = io.BytesIO()
        self.last_generated_cloud_image.save(buf, format="PNG")
        pixmap = QPixmap.fromImage(QImage.fromData(buf.getvalue()))
        self.cloud_scene.addPixmap(pixmap)
        self.cloud_view.fitInView(self.cloud_scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _start_export_process(self):

        if self.export_thread and self.export_thread.isRunning():
            QMessageBox.warning(self, "In Progress", "An export is already running. Please wait.")
            return
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Word Cloud", "my_word_cloud.png", "4K PNG Image (*.png);;Vector Image (*.svg)"
        )
        if not filepath:
            return
        entity_key = self.cloud_source_combo.currentData()
        source_data = self.analysis_data.get(entity_key, [])
        frequencies = {item["name"]: item["tws"] for item in source_data}
        is_png = selected_filter == "4K PNG Image (*.png)"
        options = {
            "width": 3840 if is_png else 1200,
            "height": 2160 if is_png else 800,
            "scale": 1,
            "background_color": "black" if self.bg_button.isChecked() else "white",
            "colormap": self.colormap_combo.currentText(),
            "max_words": self.max_words_slider.value(),
            "mask": self.current_mask_array,
            "contour_width": 1,
            "contour_color": "steelblue",
            "relative_scaling": self.scaling_slider.value() / 100.0,
        }
        self.export_thread = QThread()
        self.export_worker = ExportWorker(frequencies, options, filepath, "png" if is_png else "svg")
        self.export_worker.moveToThread(self.export_thread)
        self.export_thread.started.connect(self.export_worker.run)
        self.export_worker.finished.connect(self._on_export_finished)
        self.export_worker.error.connect(self._on_export_error)
        self.export_worker.finished.connect(self.export_thread.quit)
        self.export_worker.finished.connect(self.export_worker.deleteLater)
        self.export_thread.finished.connect(self.export_thread.deleteLater)
        self.wait_dialog = QDialog(self)
        self.wait_dialog.setWindowTitle("Processing...")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Generating high-quality export in the background..."))
        self.wait_dialog.setLayout(layout)
        self.wait_dialog.setModal(False)
        self.wait_dialog.show()
        self.export_thread.start()

    def _on_export_finished(self, filepath: str):
        if self.wait_dialog:
            self.wait_dialog.close()
        QMessageBox.information(self, "Success", f"Image successfully exported to:\n{filepath}")

    def _on_export_error(self, error_message: str):
        if self.wait_dialog:
            self.wait_dialog.close()
        QMessageBox.critical(self, "Error", f"Failed to export image.\n\nError: {error_message}")
