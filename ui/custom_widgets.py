from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QLabel,
    QProgressBar,
    QSplashScreen,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


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


class LoadingSplashScreen(QSplashScreen):
    """Splash screen shown during UI initialization."""
    
    def __init__(self, pixmap=None, parent=None):
        """Initialize the splash screen.
        
        Args:
            pixmap: Optional pixmap for the splash screen. If None, creates a simple text-based splash.
            parent: Parent widget (usually None for splash screens).
        """
        if pixmap is None:
            # Create a simple pixmap with text
            from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
            
            # Create a pixmap for the splash
            pixmap = QPixmap(600, 300)
            # Use opaque background instead of transparent for better visibility
            pixmap.fill(QColor("#1f2937"))
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw background with rounded corners effect
            painter.fillRect(pixmap.rect(), QColor("#1f2937"))
            
            # Draw text
            painter.setPen(QColor("#FFFFFF"))
            font = QFont()
            font.setPointSize(24)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Appium Traverser")
            
            # Draw subtitle
            font.setPointSize(12)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor("#9CA3AF"))
            subtitle_rect = pixmap.rect()
            subtitle_rect.setTop(subtitle_rect.top() + 60)
            painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignCenter, "Loading interface...")
            
            painter.end()
        
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint 
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
        )
        # Ensure splash is always on top and visible
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        
    def show_message(self, message: str):
        """Show a message on the splash screen."""
        from PySide6.QtGui import QColor
        self.showMessage(
            message,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
            QColor("#FFFFFF")
        )


class BusyDialog(QDialog):
    """Modern, polished loading overlay with improved visual design.

    Shows a semi-transparent backdrop over the parent window with a centered
    container displaying a message and an animated indeterminate progress bar.
    The overlay properly blocks all UI interactions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        # Frameless and translucent background for overlay effect
        # Remove WindowStaysOnTopHint so it doesn't show when alt-tabbing away
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint 
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Store reference to parent for disabling widgets
        self._parent_widget = parent
        self._disabled_widgets = []
        self._should_be_visible = False  # Track if dialog should be visible
        self._is_initializing = False  # Prevent event filter from hiding during initialization
        self._is_closing = False  # Track if we're explicitly closing (vs just hiding for focus)

        # Full-size overlay layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Centered container with rounded corners and shadow effect
        container = QWidget(self)
        container.setObjectName("busyContainer")
        container.setMinimumWidth(300)
        container.setMaximumWidth(400)
        container.setVisible(True)  # Ensure container is visible
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(32, 32, 32, 32)
        container_layout.setSpacing(20)

        # Message label with better typography
        self.message_label = QLabel("Working...", container)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setObjectName("busyMessage")
        
        # Progress bar with modern styling
        self.progress = QProgressBar(container)
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.setObjectName("busyProgress")
        self.progress.setMinimumHeight(6)
        self.progress.setTextVisible(False)  # Hide text for cleaner look

        container_layout.addWidget(self.message_label)
        container_layout.addWidget(self.progress)
        outer_layout.addWidget(container)
        
        # Ensure all widgets are visible
        self.setVisible(True)
        container.setVisible(True)
        self.message_label.setVisible(True)
        self.progress.setVisible(True)

        # Dark mode styling to match the rest of the UI
        self.setStyleSheet(
            """
            QDialog { 
                background-color: rgba(0, 0, 0, 200); 
            }
            #busyContainer { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1f2937, stop:1 #111827);
                border-radius: 12px;
                border: 1px solid #374151;
            }
            #busyMessage { 
                font-size: 16px; 
                font-weight: 500;
                color: #FFFFFF;
                padding: 8px;
            }
            #busyProgress {
                border: none;
                border-radius: 3px;
                background-color: #374151;
                text-align: center;
            }
            #busyProgress::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:0.5 #60a5fa, stop:1 #3b82f6);
                border-radius: 3px;
            }
            """
        )

    def set_message(self, msg: str) -> None:
        """Update the loading message."""
        try:
            self.message_label.setText(str(msg))
        except Exception:
            pass
    
    def close_dialog(self):
        """Properly close the dialog and reset state."""
        self._is_closing = True  # Mark that we're explicitly closing
        self._should_be_visible = False
        
        # Always use fallback method to ensure ALL widgets are re-enabled
        # This is more reliable than relying on the stored list
        if self._parent_widget:
            try:
                from PySide6.QtWidgets import (
                    QPushButton, QComboBox, QSpinBox, QLineEdit, 
                    QCheckBox, QRadioButton, QSlider, QTextEdit
                )
                
                interactive_types = (
                    QPushButton, QComboBox, QSpinBox, QLineEdit,
                    QCheckBox, QRadioButton, QSlider, QTextEdit
                )
                
                # Find and enable ALL disabled interactive widgets in the parent
                def enable_all_widgets(widget):
                    count = 0
                    if isinstance(widget, interactive_types):
                        if not widget.isEnabled():
                            widget.setEnabled(True)
                            widget.update()  # Force visual update
                            count += 1
                    for child in widget.findChildren(QWidget):
                        if isinstance(child, interactive_types):
                            if not child.isEnabled():
                                child.setEnabled(True)
                                child.update()  # Force visual update
                                count += 1
                    return count
                
                enabled_count = enable_all_widgets(self._parent_widget)
                if enabled_count > 0:
                    import logging
                    logging.debug(f"Re-enabled {enabled_count} widgets when closing dialog")
            except Exception as e:
                import logging
                logging.debug(f"Error in widget re-enabling: {e}")
        
        # Also try the stored list method as backup
        self._enable_parent_widgets()
        
        # Remove event filter
        if self._parent_widget:
            try:
                self._parent_widget.removeEventFilter(self)
            except Exception:
                pass
        
        self.hide()
        
        # Force a repaint/update of the parent window to ensure widgets are visually enabled
        if self._parent_widget:
            try:
                self._parent_widget.update()
                QApplication.processEvents()
            except Exception:
                pass
        
        self._is_closing = False  # Reset flag

    def show_for_parent(self, parent_widget: QWidget) -> None:
        """Resize overlay to cover the parent and show it centered."""
        try:
            if parent_widget is not None:
                # Position overlay to cover the parent window area
                # Use the parent's geometry, but convert to global coordinates if needed
                parent_geom = parent_widget.geometry()
                if isinstance(parent_widget, QWidget):
                    # Get the global position of the parent
                    global_pos = parent_widget.mapToGlobal(parent_widget.rect().topLeft())
                    parent_geom.moveTopLeft(global_pos)
                self.setGeometry(parent_geom)
        except Exception:
            pass
        # Ensure dialog is visible and raised
        self.setVisible(True)
        self.show()
        self.raise_()
        self.activateWindow()
    
    def resizeEvent(self, event):
        """Update geometry when parent window is resized."""
        super().resizeEvent(event)
        if self._parent_widget and self.isVisible():
            try:
                parent_geom = self._parent_widget.geometry()
                if isinstance(self._parent_widget, QWidget):
                    global_pos = self._parent_widget.mapToGlobal(self._parent_widget.rect().topLeft())
                    parent_geom.moveTopLeft(global_pos)
                self.setGeometry(parent_geom)
            except Exception:
                pass
    
    def showEvent(self, event):
        """Override showEvent to disable parent widgets when shown."""
        super().showEvent(event)
        self._should_be_visible = True  # Mark that dialog should be visible
        self._is_initializing = True  # Set flag to prevent immediate hiding
        self._disable_parent_widgets()
        # Ensure dialog is raised and visible
        self.raise_()
        self.activateWindow()
        # Connect to parent window's state changes to hide when parent loses focus
        if self._parent_widget:
            try:
                from PySide6.QtCore import QEvent, QTimer
                # Install event filter on parent to detect focus changes
                self._parent_widget.installEventFilter(self)
                # Clear initialization flag after a short delay to allow dialog to fully show
                QTimer.singleShot(100, lambda: setattr(self, '_is_initializing', False))
            except Exception:
                pass
    
    def hideEvent(self, event):
        """Override hideEvent to re-enable parent widgets when hidden."""
        super().hideEvent(event)
        # Only re-enable widgets if we're actually closing (not just hiding due to focus loss)
        # If _is_closing is True, widgets were already re-enabled in close_dialog()
        if not self._should_be_visible and not self._is_closing:
            self._enable_parent_widgets()
            # Remove event filter when actually closing
            if self._parent_widget:
                try:
                    self._parent_widget.removeEventFilter(self)
                except Exception:
                    pass
    
    def eventFilter(self, obj, event):
        """Filter events from parent window to hide/show dialog based on parent focus."""
        if obj == self._parent_widget:
            # Don't process events during initialization to prevent immediate hiding
            if self._is_initializing:
                return super().eventFilter(obj, event)
            
            try:
                from PySide6.QtCore import QEvent
                # Hide dialog when parent window is minimized or loses focus
                if event.type() == QEvent.Type.WindowStateChange:
                    # Check if window is minimized
                    if self._parent_widget.isMinimized():
                        if self.isVisible():
                            self._should_be_visible = True
                            self.hide()
                    elif not self._parent_widget.isMinimized() and self._should_be_visible:
                        # Window restored, show dialog again if it should be visible
                        self.show()
                        self.raise_()
                        self._should_be_visible = False
                elif event.type() == QEvent.Type.WindowDeactivate:
                    # Hide when window loses focus (e.g., alt-tab)
                    # But only if dialog is actually visible and not during initialization
                    if self.isVisible() and not self._is_initializing:
                        self._should_be_visible = True
                        self.hide()
                elif event.type() == QEvent.Type.WindowActivate:
                    # Show again when window regains focus
                    if self._should_be_visible and not self._parent_widget.isMinimized():
                        self.show()
                        self.raise_()
                        self._should_be_visible = False
            except Exception:
                pass
        return super().eventFilter(obj, event)
    
    def _disable_parent_widgets(self):
        """Disable all interactive widgets in the parent window."""
        if not self._parent_widget:
            return
        
        try:
            # Find all interactive widgets and disable them
            from PySide6.QtWidgets import (
                QPushButton, QComboBox, QSpinBox, QLineEdit, 
                QCheckBox, QRadioButton, QSlider, QTextEdit
            )
            
            interactive_types = (
                QPushButton, QComboBox, QSpinBox, QLineEdit,
                QCheckBox, QRadioButton, QSlider, QTextEdit
            )
            
            def find_widgets(widget):
                widgets = []
                if isinstance(widget, interactive_types):
                    if widget.isEnabled():
                        widgets.append(widget)
                for child in widget.findChildren(QWidget):
                    if isinstance(child, interactive_types):
                        if child.isEnabled():
                            widgets.append(child)
                return widgets
            
            self._disabled_widgets = find_widgets(self._parent_widget)
            for widget in self._disabled_widgets:
                widget.setEnabled(False)
                
        except Exception as e:
            # Silently fail if there's an issue
            import logging
            logging.debug(f"Error disabling widgets: {e}")
    
    def _enable_parent_widgets(self):
        """Re-enable all widgets that were disabled."""
        try:
            # Make a copy of the list to avoid issues if it's modified during iteration
            widgets_to_enable = list(self._disabled_widgets)
            enabled_count = 0
            
            for widget in widgets_to_enable:
                try:
                    if widget and hasattr(widget, 'setEnabled'):
                        widget.setEnabled(True)
                        enabled_count += 1
                except Exception as e:
                    import logging
                    logging.debug(f"Error enabling widget: {e}")
            
            # If we didn't enable any widgets from the list, try to find and enable all disabled widgets
            # This is a fallback in case the list wasn't populated correctly
            if enabled_count == 0 and self._parent_widget:
                try:
                    from PySide6.QtWidgets import (
                        QPushButton, QComboBox, QSpinBox, QLineEdit, 
                        QCheckBox, QRadioButton, QSlider, QTextEdit
                    )
                    
                    interactive_types = (
                        QPushButton, QComboBox, QSpinBox, QLineEdit,
                        QCheckBox, QRadioButton, QSlider, QTextEdit
                    )
                    
                    # Find all interactive widgets and enable them
                    def find_and_enable_widgets(widget):
                        count = 0
                        if isinstance(widget, interactive_types):
                            if not widget.isEnabled():
                                widget.setEnabled(True)
                                count += 1
                        for child in widget.findChildren(QWidget):
                            if isinstance(child, interactive_types):
                                if not child.isEnabled():
                                    child.setEnabled(True)
                                    count += 1
                        return count
                    
                    fallback_count = find_and_enable_widgets(self._parent_widget)
                    if fallback_count > 0:
                        import logging
                        logging.debug(f"Fallback: Enabled {fallback_count} widgets that were disabled")
                except Exception as e:
                    import logging
                    logging.debug(f"Error in fallback widget enabling: {e}")
            
            self._disabled_widgets.clear()
        except Exception as e:
            import logging
            logging.debug(f"Error enabling widgets: {e}")
            # Even if there's an error, clear the list to prevent stuck state
            self._disabled_widgets.clear()
            # Try fallback one more time
            if self._parent_widget:
                try:
                    from PySide6.QtWidgets import QWidget
                    for widget in self._parent_widget.findChildren(QWidget):
                        if hasattr(widget, 'setEnabled') and not widget.isEnabled():
                            widget.setEnabled(True)
                except Exception:
                    pass
