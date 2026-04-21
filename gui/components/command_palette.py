from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QListWidget,
    QListWidgetItem, QLabel
)
from PySide6.QtCore import Qt, Signal


# 指令表：shortcut 为快捷别名，输入 /s 空格直接触发
COMMANDS = [
    {        
         "icon": "🔎", "name": "联网搜索", "shortcut": "w",        
         "desc": "搜索后回答",        
         "prompt": "__SEARCH__:{text}",   # 特殊标记，controller 识别        
         "search": True,                  # 标记为搜索指令    
    },
    {
        "icon": "🌐", "name": "翻译",     "shortcut": "t",
        "desc": "翻译成中/英文",
        "prompt": "请将以下内容翻译成中文，如果已是中文则翻译成英文，只输出翻译结果：\n\n{text}"
    },
    {
        "icon": "✍️", "name": "润色",     "shortcut": "r",
        "desc": "优化文字表达",
        "prompt": "请对以下文字进行润色，保持原意，使其更流畅自然，只输出润色后的结果：\n\n{text}"
    },
    {
        "icon": "📝", "name": "总结",     "shortcut": "s",
        "desc": "提炼核心要点",
        "prompt": "请对以下内容进行简洁总结，提炼核心要点：\n\n{text}"
    },
    {
        "icon": "🔍", "name": "解释",     "shortcut": "e",
        "desc": "通俗解释概念",
        "prompt": "请用通俗易懂的语言解释以下内容：\n\n{text}"
    },
    {
        "icon": "💻", "name": "解释代码", "shortcut": "ec",
        "desc": "逐行解析代码逻辑",
        "prompt": "请详细解释以下代码的逻辑和功能：\n\n{text}"
    },
    {
        "icon": "🐛", "name": "找Bug",    "shortcut": "b",
        "desc": "检查代码问题",
        "prompt": "请检查以下代码是否存在bug或问题，并给出修复建议：\n\n{text}"
    },
    {
        "icon": "📧", "name": "写邮件",   "shortcut": "m",
        "desc": "生成正式邮件",
        "prompt": "请根据以下要点，帮我写一封正式的邮件：\n\n{text}"
    },
    {
        "icon": "🎯", "name": "续写",     "shortcut": "c",
        "desc": "接着往下写",
        "prompt": "请接着以下内容继续写，保持风格一致：\n\n{text}"
    },
    {
        "icon": "🔄", "name": "换个说法", "shortcut": "p",
        "desc": "用不同方式表达",
        "prompt": "请用完全不同的表达方式重新描述以下内容，保持意思不变：\n\n{text}"
    },
    {
        "icon": "❓", "name": "深入分析", "shortcut": "a",
        "desc": "深入探讨这个话题",
        "prompt": "请深入分析以下内容，并提出值得思考的问题：\n\n{text}"
    },
]

# 快捷别名索引，方便 O(1) 查找
SHORTCUT_MAP = {cmd["shortcut"]: cmd for cmd in COMMANDS}


class CommandPalette(QFrame):
    """
    快捷指令浮层，由 InputBar 直接管理，
    不使用 Popup 窗口，避免焦点被抢走。
    """
    command_selected = Signal(str)   # prompt 模板

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("command_palette")
        # 不抢焦点，不作为独立窗口
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._filtered = list(COMMANDS)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        hint = QLabel("  ↑↓ 选择  Enter 确认  Esc 关闭")
        hint.setObjectName("palette_hint")
        hint.setFixedHeight(24)
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.setObjectName("palette_list")
        self._list.setFocusPolicy(Qt.NoFocus)   # 绝对不抢焦点
        self._list.setMouseTracking(True)
        self._list.itemClicked.connect(self._on_clicked)
        layout.addWidget(self._list)

        self.setFixedWidth(320)
        self._refresh("")

    def _refresh(self, keyword: str):
        self._list.clear()
        kw = keyword.lower().strip()
        self._filtered = [
            c for c in COMMANDS
            if kw == ""
            or kw in c["name"].lower()
            or kw in c["shortcut"].lower()
            or kw in c["desc"].lower()
        ]
        for cmd in self._filtered:
            label = f"  {cmd['icon']}  {cmd['name']}  /{cmd['shortcut']}    {cmd['desc']}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, cmd["prompt"])
            item.setSizeHint(__import__('PySide6.QtCore', fromlist=['QSize']).QSize(300, 40))
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        # 高度自适应，最多显示 8 条
        count = min(self._list.count(), 8)
        self._list.setFixedHeight(max(count * 40, 40))
        self.adjustSize()

    def filter(self, keyword: str) -> bool:
        """过滤列表，返回是否还有结果"""
        self._refresh(keyword)
        return self._list.count() > 0

    def move_up(self):
        cur = self._list.currentRow()
        self._list.setCurrentRow(max(0, cur - 1))

    def move_down(self):
        cur = self._list.currentRow()
        self._list.setCurrentRow(min(self._list.count() - 1, cur + 1))

    def confirm(self) -> bool:
        item = self._list.currentItem()
        if item:
            self.command_selected.emit(item.data(Qt.UserRole))
            self.hide()
            return True
        return False

    def _on_clicked(self, item: QListWidgetItem):
        self.command_selected.emit(item.data(Qt.UserRole))
        self.hide()
