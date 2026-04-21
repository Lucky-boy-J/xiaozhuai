"""设置对话框"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QSpinBox, QPushButton, QGroupBox,
    QDoubleSpinBox, QComboBox, QLineEdit, QFormLayout,
)
from PySide6.QtCore import Qt
import yaml


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(460, 500)
        self._cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # ── LLM 参数 ──
        llm_group = QGroupBox("LLM 推理参数")
        llm_form = QFormLayout(llm_group)

        self._temp = QDoubleSpinBox()
        self._temp.setRange(0.0, 2.0)
        self._temp.setSingleStep(0.05)
        self._temp.setValue(self._cfg["models"]["llm"]["temperature"])
        llm_form.addRow("Temperature", self._temp)

        self._top_p = QDoubleSpinBox()
        self._top_p.setRange(0.0, 1.0)
        self._top_p.setSingleStep(0.05)
        self._top_p.setValue(self._cfg["models"]["llm"]["top_p"])
        llm_form.addRow("Top-P", self._top_p)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(64, 4096)
        self._max_tokens.setSingleStep(64)
        self._max_tokens.setValue(self._cfg["models"]["llm"]["max_tokens"])
        llm_form.addRow("Max Tokens", self._max_tokens)

        self._gpu_layers = QSpinBox()
        self._gpu_layers.setRange(0, 999)
        self._gpu_layers.setValue(self._cfg["models"]["llm"]["n_gpu_layers"])
        llm_form.addRow("GPU Layers", self._gpu_layers)

        layout.addWidget(llm_group)

        # ── 模型路径 ──
        path_group = QGroupBox("模型路径")
        path_form = QFormLayout(path_group)

        self._llm_path = QLineEdit(self._cfg["models"]["llm"]["path"])
        path_form.addRow("LLM (.gguf)", self._llm_path)

        self._asr_path = QLineEdit(self._cfg["models"]["asr"]["local_path"])
        path_form.addRow("ASR 路径", self._asr_path)

        self._tts_path = QLineEdit(self._cfg["models"]["tts"]["local_path"])
        path_form.addRow("TTS 路径", self._tts_path)

        layout.addWidget(path_group)

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_cancel = QPushButton("取消")
        btn_save.clicked.connect(self._save)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _save(self):
        cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
        cfg["models"]["llm"]["temperature"]  = self._temp.value()
        cfg["models"]["llm"]["top_p"]        = self._top_p.value()
        cfg["models"]["llm"]["max_tokens"]   = self._max_tokens.value()
        cfg["models"]["llm"]["n_gpu_layers"] = self._gpu_layers.value()
        cfg["models"]["llm"]["path"]         = self._llm_path.text()
        cfg["models"]["asr"]["local_path"]   = self._asr_path.text()
        cfg["models"]["tts"]["local_path"]   = self._tts_path.text()
        with open("config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True)
        self.accept()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog, QGroupBox, QWidget {
                background: #13131F; color: #E0E0F0;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QGroupBox {
                border: 1px solid #2E2E4E; border-radius: 8px;
                margin-top: 8px; padding: 12px;
                font-weight: bold; color: #A78BFA;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QLineEdit, QDoubleSpinBox, QSpinBox {
                background: #1A1A2E; border: 1px solid #2E2E4E;
                border-radius: 6px; padding: 4px 8px; color: #E0E0F0;
            }
            QPushButton {
                background: #7C3AED; color: white; border: none;
                border-radius: 8px; padding: 8px 20px; font-size: 13px;
            }
            QPushButton:hover { background: #6D28D9; }
        """)
