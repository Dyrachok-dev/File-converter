import sys
import os
import zipfile
import tarfile

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QProgressBar,
    QMessageBox, QTabWidget, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPainter, QLinearGradient, QColor


# ==========================================
# Ультра-тёмный анимированный фон
# ==========================================
class UltraDarkGradientWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gradient_step = 0.0

        # Анимация (~60 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gradient)
        QTimer.singleShot(100, lambda: self.timer.start(16)) # <- Строка с lambda-функцией

    def update_gradient(self):
        self.gradient_step += 0.0015
        if self.gradient_step > 1.0:
            self.gradient_step = 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        gradient = QLinearGradient(0, 0, w, h)
        t = self.gradient_step

        v1 = int(4 + 8 * t)
        v2 = int(18 - 8 * t)
        v3 = int(10 + 6 * t)

        c1 = QColor(v1, v1, v1)
        c2 = QColor(v2, v2, v2)
        c3 = QColor(v3, v3, v3)

        gradient.setColorAt(0.0, c1)
        gradient.setColorAt(0.5, c2)
        gradient.setColorAt(1.0, c3)

        painter.fillRect(self.rect(), gradient)


# ==========================================
# Поток для фоновой конвертации
# ==========================================
class ConversionThread(QThread):
    finished_signal = Signal(bool, str)

    def __init__(self, input_path, target_format, category):
        super().__init__()
        self.input_path = input_path
        self.target_format = target_format.lower()
        self.category = category

    def run(self):
        try:
            base_path, ext = os.path.splitext(self.input_path)
            ext = ext.lower()
            output_path = f"{base_path}_converted.{self.target_format}"

            # 1. ИЗОБРАЖЕНИЯ (Импорт только по требованию)
            if self.category == "image":
                try:
                    from PIL import Image
                except ImportError:
                    raise Exception("Установите Pillow: pip install pillow")

                with Image.open(self.input_path) as img:
                    if img.mode in ("RGBA", "P") and self.target_format in ("jpg", "jpeg", "bmp"):
                        img = img.convert("RGB")
                    img.save(output_path)

            # 2. МЕДИА (Импорт только по требованию)
            elif self.category == "media":
                try:
                    from moviepy.editor import VideoFileClip, AudioFileClip
                except ImportError:
                    raise Exception("Для медиа установите moviepy: pip install moviepy")

                if self.target_format in ["mp3", "wav", "ogg", "flac", "aac", "m4a"]:
                    clip = AudioFileClip(self.input_path)
                    clip.write_audiofile(output_path)
                    clip.close()
                elif self.target_format in ["mp4", "avi", "mkv", "webm", "wmv", "flv"]:
                    clip = VideoFileClip(self.input_path)
                    clip.write_videofile(output_path)
                    clip.close()

            # 3. ДОКУМЕНТЫ И КНИГИ
            elif self.category == "doc":
                if ext == ".docx" and self.target_format == "pdf":
                    try:
                        from docx2pdf import convert as docx2pdf_convert
                    except ImportError:
                        raise Exception("Установите docx2pdf для конвертации DOCX в PDF.")
                    docx2pdf_convert(self.input_path, output_path)

                elif ext in [".txt", ".md", ".html", ".json"] and self.target_format in ["txt", "md", "html"]:
                    with open(self.input_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(content)
                else:
                    raise Exception(f"Конвертация из {ext} в {self.target_format} требует внешних утилит.")

            # 4. ТАБЛИЦЫ И ДАННЫЕ (Импорт только по требованию)
            elif self.category == "data":
                try:
                    import pandas as pd
                except ImportError:
                    raise Exception("Установите pandas: pip install pandas openpyxl pyarrow")

                if ext == ".csv":
                    df = pd.read_csv(self.input_path)
                elif ext in [".xlsx", ".xls"]:
                    df = pd.read_excel(self.input_path)
                elif ext == ".json":
                    df = pd.read_json(self.input_path)
                elif ext == ".parquet":
                    df = pd.read_parquet(self.input_path)
                else:
                    raise Exception("Неподдерживаемый исходный формат таблицы.")

                if self.target_format == "csv":
                    df.to_csv(output_path, index=False)
                elif self.target_format == "xlsx":
                    df.to_excel(output_path, index=False)
                elif self.target_format == "json":
                    df.to_json(output_path, orient="records", force_ascii=False, indent=4)
                elif self.target_format == "html":
                    df.to_html(output_path, index=False)
                elif self.target_format == "parquet":
                    df.to_parquet(output_path, index=False)

            # 5. АРХИВЫ (Перепаковка)
            elif self.category == "archive":
                if self.target_format == "zip":
                    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        zipf.write(self.input_path, os.path.basename(self.input_path))
                elif self.target_format in ["tar", "gz"]:
                    mode = "w:gz" if self.target_format == "gz" else "w"
                    with tarfile.open(output_path, mode) as tar:
                        tar.add(self.input_path, arcname=os.path.basename(self.input_path))

            self.finished_signal.emit(True, output_path)

        except Exception as e:
            self.finished_signal.emit(False, str(e))


# ==========================================
# Главный интерфейс приложения
# ==========================================
class DarkConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Dark File Converter Pro")
        self.resize(850, 600)
        self.setMinimumSize(700, 500)

        self.selected_file = ""

        # Живой глубокий тёмный фон
        self.bg_widget = UltraDarkGradientWidget(self)
        self.setCentralWidget(self.bg_widget)

        root_layout = QHBoxLayout(self.bg_widget)
        root_layout.setContentsMargins(20, 20, 20, 20)

        central_container = QWidget()
        central_container.setMaximumWidth(800)
        container_layout = QVBoxLayout(central_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        glass_card = QFrame()
        glass_card.setObjectName("glassCard")
        glass_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        card_layout = QVBoxLayout(glass_card)
        card_layout.setContentsMargins(35, 35, 35, 35)
        card_layout.setSpacing(22)

        title_label = QLabel("FILE CONVERTER")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(QWidget(), "ИЗОБРАЖЕНИЯ")
        self.tabs.addTab(QWidget(), "МЕДИА")
        self.tabs.addTab(QWidget(), "ДОКУМЕНТЫ")
        self.tabs.addTab(QWidget(), "ТАБЛИЦЫ")
        self.tabs.addTab(QWidget(), "АРХИВЫ")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        card_layout.addWidget(self.tabs)

        file_frame = QFrame()
        file_frame.setObjectName("fileFrame")
        file_layout = QHBoxLayout(file_frame)

        self.file_label = QLabel("Файл не выбран")
        self.file_label.setObjectName("fileLabel")
        self.file_label.setWordWrap(True)
        file_layout.addWidget(self.file_label, stretch=1)

        btn_browse = QPushButton("ОБЗОР")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(btn_browse)

        card_layout.addWidget(file_frame)

        format_layout = QHBoxLayout()
        format_label = QLabel("ФОРМАТ НАЗНАЧЕНИЯ:")
        format_label.setStyleSheet("color: #888888; font-weight: bold; font-size: 11px; letter-spacing: 1px;")

        self.combo_formats = QComboBox()
        self.combo_formats.setMinimumWidth(150)

        format_layout.addWidget(format_label)
        format_layout.addWidget(self.combo_formats)
        format_layout.addStretch()

        card_layout.addLayout(format_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        card_layout.addWidget(self.progress_bar)

        self.btn_convert = QPushButton("КОНВЕРТИРОВАТЬ")
        self.btn_convert.setObjectName("btnConvert")
        self.btn_convert.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_convert.clicked.connect(self.start_conversion)
        card_layout.addWidget(self.btn_convert)

        container_layout.addWidget(glass_card)
        root_layout.addWidget(central_container)

        self.apply_styles()
        self.update_formats_list()

    def get_current_category(self):
        index = self.tabs.currentIndex()
        categories = ["image", "media", "doc", "data", "archive"]
        return categories[index]

    def on_tab_changed(self):
        self.selected_file = ""
        self.file_label.setText("Файл не выбран")
        self.update_formats_list()

    def update_formats_list(self):
        self.combo_formats.clear()
        category = self.get_current_category()

        if category == "image":
            self.combo_formats.addItems(["PNG", "JPG", "WEBP", "BMP", "ICO", "TIFF", "GIF", "TGA"])
        elif category == "media":
            self.combo_formats.addItems(
                ["MP3", "WAV", "OGG", "FLAC", "AAC", "M4A", "MP4", "AVI", "MKV", "WEBM", "WMV", "FLV"])
        elif category == "doc":
            self.combo_formats.addItems(["PDF", "TXT", "MD", "HTML", "DOCX", "EPUB", "FB2"])
        elif category == "data":
            self.combo_formats.addItems(["CSV", "XLSX", "JSON", "XML", "PARQUET", "HTML"])
        elif category == "archive":
            self.combo_formats.addItems(["ZIP", "TAR", "GZ", "7Z"])

    def browse_file(self):
        category = self.get_current_category()

        if category == "image":
            file_filter = "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.ico *.gif *.tga)"
        elif category == "media":
            file_filter = "Медиа файлы (*.mp4 *.avi *.mkv *.webm *.wmv *.flv *.mp3 *.wav *.ogg *.flac *.aac *.m4a)"
        elif category == "doc":
            file_filter = "Документы (*.docx *.pdf *.txt *.md *.html *.epub *.fb2)"
        elif category == "data":
            file_filter = "Таблицы и данные (*.xlsx *.xls *.csv *.json *.xml *.parquet)"
        elif category == "archive":
            file_filter = "Архивы (*.zip *.tar *.gz *.7z *.rar)"

        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл", "", file_filter)
        if file_path:
            self.selected_file = file_path
            self.file_label.setText(f"📄 {os.path.basename(file_path)}")

    def start_conversion(self):
        if not self.selected_file:
            QMessageBox.warning(self, "Ошибка", "Выберите файл перед запуском!")
            return

        target_format = self.combo_formats.currentText()
        category = self.get_current_category()

        self.btn_convert.setEnabled(False)
        self.progress_bar.show()

        self.thread = ConversionThread(self.selected_file, target_format, category)
        self.thread.finished_signal.connect(self.on_conversion_finished)
        self.thread.start()

    def on_conversion_finished(self, success, result_message):
        self.progress_bar.hide()
        self.btn_convert.setEnabled(True)

        if success:
            QMessageBox.information(self, "Успех", f"Файл успешно сохранен:\n{result_message}")
        else:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при конвертации:\n{result_message}")

    def apply_styles(self):
        self.setStyleSheet("""
            #glassCard {
                background-color: rgba(10, 10, 12, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
            }
            #titleLabel {
                font-size: 20px;
                font-weight: 900;
                color: #ffffff;
                letter-spacing: 5px;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: rgba(255, 255, 255, 0.03);
                color: #666666;
                padding: 10px 14px;
                border-radius: 8px;
                margin-right: 4px;
                font-weight: bold;
                font-size: 11px;
                letter-spacing: 1px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #000000;
            }
            #fileFrame {
                background-color: #000000;
                border: 1px dashed rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                padding: 12px;
            }
            #fileLabel {
                color: #dddddd;
                font-size: 13px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            #btnConvert {
                background-color: #ffffff;
                color: #000000;
                border: none;
                border-radius: 10px;
                padding: 15px;
                font-size: 13px;
                font-weight: 900;
                letter-spacing: 3px;
            }
            #btnConvert:hover {
                background-color: #cccccc;
            }
            #btnConvert:disabled {
                background-color: #222222;
                color: #555555;
            }
            QComboBox {
                background-color: #000000;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QProgressBar {
                border: none;
                background-color: #000000;
                height: 4px;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #ffffff;
                border-radius: 2px;
            }
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DarkConverterApp()
    window.show()
    sys.exit(app.exec())