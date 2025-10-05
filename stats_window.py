import io
from typing import Any, Dict, List, Optional, Tuple

import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from wordcloud import WordCloud

from database import (
    calculate_base_stats,
    get_data_for_charts,
    get_frequencies_for_wordclouds,
)

try:
    font_list = [
        "Meiryo",
        "MS Gothic",
        "Arial Unicode MS",
        "Hiragino Sans",
        "Noto Sans CJK JP",
        "DejaVu Sans",
    ]
    mpl.rcParams["font.family"] = next(font for font in font_list if font in mpl.font_manager.get_font_names())
    mpl.rcParams["axes.unicode_minus"] = False
except StopIteration:
    print("WARNING: No extended Unicode font found for matplotlib.")


class StatsWindow(QDialog):
    stats: Dict[str, int]
    chart_data: Dict[str, Any]
    wordcloud_freqs: Dict[str, Dict[str, int]]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Your Reading Stats")
        self.setGeometry(300, 300, 900, 700)
        main_layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Show data for: Read/Commented Fics", "Show data for: All Fics"])
        filter_layout.addWidget(QLabel("<b>Data Filter:</b>"))
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        main_layout.addLayout(filter_layout)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.filter_combo.currentIndexChanged.connect(self._update_all_tabs)
        self._update_all_tabs()

    def _update_all_tabs(self) -> None:
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        chart_filter = "lette" if self.filter_combo.currentIndex() == 0 else "tutte"
        self.stats = calculate_base_stats()
        self.chart_data = get_data_for_charts(chart_filter)

        from database import get_data_for_publication_year_chart

        self.publication_year_data = get_data_for_publication_year_chart(chart_filter)

        self.wordcloud_freqs = get_frequencies_for_wordclouds(chart_filter)
        self._create_summary_tab()
        self._create_content_tab()
        self._create_tags_wordcloud_tab()
        self._create_rel_chars_wordcloud_tab()

    def _create_summary_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        stats_text = f"""
        <b>General Summary (not affected by filter):</b><br>
        - Total Fics: {self.stats.get("total_fics", 0)}<br>
        - Read: {self.stats.get("fics_read", 0)} | Commented: {self.stats.get("fics_commented", 0)} | To Read: {self.stats.get("fics_to_read", 0)}<br>
        - Total Words Read: {self.stats.get("total_words_read", 0):,} words
        """  # noqa: E501
        layout.addWidget(QLabel(stats_text))
        status_breakdown = self.chart_data.get("status_breakdown")
        if status_breakdown:
            status_chart = self._create_pie_chart(status_breakdown, "Status Breakdown")
            layout.addWidget(status_chart)
        self.tabs.addTab(tab, "Summary")

    def _create_tags_wordcloud_tab(self) -> None:
        panel = self._create_wordcloud_panel("Tags", self.wordcloud_freqs.get("tags", {}))
        self.tabs.addTab(panel, "Tags")

    def _create_rel_chars_wordcloud_tab(self) -> None:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.addWidget(self._create_wordcloud_panel("Relationships", self.wordcloud_freqs.get("relationships", {})))
        layout.addWidget(self._create_wordcloud_panel("Characters", self.wordcloud_freqs.get("characters", {})))
        self.tabs.addTab(tab, "Relationships & Characters")

    def _create_pie_chart(self, data: List[Tuple[str, int]], title: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        labels, values = [item[0] for item in data], [item[1] for item in data]
        fig = Figure(figsize=(5, 4), dpi=100)
        fig.subplots_adjust(left=0.1, right=0.6)
        ax = fig.add_subplot(111)
        wedges, texts, autotexts = ax.pie(
            values,
            labels=[str(v) for v in values],
            autopct=lambda pct: f"{pct:.1f}%",
            startangle=90,
            pctdistance=0.8,
            textprops={"color": "w"},
        )  # type: ignore[misc]
        for label in texts:
            label.set_visible(False)
        ax.axis("equal")
        ax.legend(wedges, labels, title="Legend", loc="center left", bbox_to_anchor=(1.1, 0.5))
        canvas = FigureCanvas(fig)
        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(20, 20),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="w"),
            arrowprops=dict(arrowstyle="->"),
        )
        annot.set_visible(False)

        def hover(event: Any) -> None:
            vis = annot.get_visible()
            if event.inaxes == ax:
                for i, w in enumerate(wedges):
                    cont, _ = w.contains(event)
                    if cont:
                        value = int(w.get_label())
                        label_text = labels[i]
                        annot.set_text(f"{label_text}\nValue: {value}")
                        annot.set_visible(True)
                        fig.canvas.draw_idle()
                        return
            if vis:
                annot.set_visible(False)
                fig.canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", hover)
        layout.addWidget(canvas)
        return widget

    def _create_bar_chart(self, data: List[Tuple[str, int]], title: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(f"<b>{title}</b>"))

        if not data:
            layout.addWidget(QLabel("<i>No data available for this chart.</i>"))
            return widget

        labels = [item[0] for item in data]
        values = [item[1] for item in data]

        fig = Figure(figsize=(6, 5), dpi=100)
        ax = fig.add_subplot(111)

        ax.bar(labels, values, color="#007acc")

        ax.set_ylabel("Number of Fics")
        ax.set_title(title, pad=20)

        ax.tick_params(axis="x", labelrotation=45)
        ax.grid(axis="y", linestyle="--", alpha=0.7)

        fig.tight_layout()

        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)
        return widget

    def _create_content_tab(self) -> None:
        tab_widget = QWidget()
        main_layout = QHBoxLayout(tab_widget)

        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout(left_column_widget)

        top_fandoms = self.chart_data.get("top_fandoms")
        if top_fandoms:
            pie_fandoms = self._create_pie_chart(top_fandoms, "Top 5 Fandoms")
            left_column_layout.addWidget(pie_fandoms)

        top_categories = self.chart_data.get("top_categories")
        if top_categories:
            pie_categories = self._create_pie_chart(top_categories, "Category Breakdown")
            left_column_layout.addWidget(pie_categories)

        main_layout.addWidget(left_column_widget, 1)

        if self.publication_year_data:
            bar_chart_widget = self._create_bar_chart(self.publication_year_data, "Fics by Publication Year")
            main_layout.addWidget(bar_chart_widget, 2)

        self.tabs.addTab(tab_widget, "Content Analysis")

    def _create_wordcloud_panel(self, title: str, frequencies: Dict[str, int]) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        view, scene = QGraphicsView(), QGraphicsScene()
        view.setScene(scene)
        options_layout = QHBoxLayout()
        color_combo = QComboBox()
        color_combo.addItems(["viridis", "plasma", "inferno", "magma", "cividis", "Greys", "Blues", "Reds", "Pastel1"])
        bg_button = QPushButton("Black Background")
        bg_button.setCheckable(True)
        options_layout.addWidget(QLabel("Colors:"))
        options_layout.addWidget(color_combo)
        options_layout.addWidget(bg_button)
        options_layout.addStretch()
        controls_layout = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(5)
        slider.setMaximum(50)
        slider.setValue(25)
        spinbox = QSpinBox()
        spinbox.setMinimum(5)
        spinbox.setMaximum(50)
        spinbox.setValue(25)
        save_button = QPushButton("Save Image")
        controls_layout.addWidget(QLabel("Terms:"))
        controls_layout.addWidget(slider)
        controls_layout.addWidget(spinbox)
        controls_layout.addStretch()
        controls_layout.addWidget(save_button)
        slider.valueChanged.connect(spinbox.setValue)
        spinbox.valueChanged.connect(slider.setValue)
        last_cloud: List[Optional[Any]] = [None]

        def update_cloud() -> None:
            terms = dict(sorted(frequencies.items(), key=lambda item: item[1], reverse=True)[: slider.value()])
            scene.clear()
            if not terms:
                last_cloud[0] = None
                return
            bg = "black" if bg_button.isChecked() else "white"
            cm = color_combo.currentText()
            wc = WordCloud(
                width=800, height=600, scale=2, background_color=bg, colormap=cm, relative_scaling=0.5
            ).generate_from_frequencies(terms)
            image = wc.to_image()
            last_cloud[0] = image
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            pixmap = QPixmap.fromImage(QImage.fromData(buf.getvalue()))
            scene.addPixmap(pixmap)
            view.fitInView(scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

        def save_cloud() -> None:
            image_to_save = last_cloud[0]
            if image_to_save:
                fp, _ = QFileDialog.getSaveFileName(
                    self, "Save Word Cloud", f"wordcloud_{title.lower().replace(' ', '_')}.png", "PNG Files (*.png)"
                )
                if fp:
                    try:
                        image_to_save.save(fp)
                        QMessageBox.information(self, "Success", f"Image saved to:\n{fp}")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Could not save image.\nError: {e}")
            else:
                QMessageBox.warning(self, "No Image", "No word cloud to save.")

        slider.valueChanged.connect(update_cloud)
        color_combo.currentTextChanged.connect(update_cloud)
        bg_button.toggled.connect(update_cloud)
        save_button.clicked.connect(save_cloud)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        layout.addLayout(options_layout)
        layout.addWidget(view)
        layout.addLayout(controls_layout)
        update_cloud()
        return panel
