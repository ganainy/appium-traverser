from PySide6.QtWidgets import (
    QSpinBox,
    QComboBox,
    QDialog,
    QVBoxLayout,
    QWidget,
    QLabel,
    QProgressBar,
)
from PySide6.QtCore import Qt


class NoScrollSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class NoScrollComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class BusyDialog(QDialog):
    """Simple reusable modal overlay with a message and indeterminate progress.

    Shows a semi-transparent backdrop over the parent window with a centered
    container displaying a message and an indeterminate progress bar.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        # Frameless and translucent background for overlay effect
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Full-size overlay layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Centered container with rounded corners
        container = QWidget(self)
        container.setObjectName("busyContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 24, 24, 24)
        container_layout.setSpacing(12)

        self.message_label = QLabel("Working...", container)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = QProgressBar(container)
        self.progress.setRange(0, 0)  # Indeterminate

        container_layout.addWidget(self.message_label)
        container_layout.addWidget(self.progress)
        outer_layout.addWidget(container)

        # Styling: dimmed background and white card
        self.setStyleSheet(
            """
            QDialog { background-color: rgba(0, 0, 0, 120); }
            #busyContainer { background: white; border-radius: 8px; }
            QLabel { font-size: 14px; }
            """
        )

    def set_message(self, msg: str) -> None:
        try:
            self.message_label.setText(str(msg))
        except Exception:
            pass

    def show_for_parent(self, parent_widget: QWidget) -> None:
        """Resize overlay to cover the parent and show it centered."""
        try:
            if parent_widget is not None:
                # Position overlay to cover the parent window area
                self.setGeometry(parent_widget.geometry())
        except Exception:
            pass
        self.show()
