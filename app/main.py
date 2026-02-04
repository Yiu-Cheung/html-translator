#!/usr/bin/env python3
"""
HTML Translation Desktop App
Main entry point
"""

import sys
from pathlib import Path

# Add app directory to path
app_dir = Path(__file__).parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.core.config import AppConfig
from app.core.project_manager import setup_default_projects
from app.ui.main_window import MainWindow


def main():
    """Main entry point"""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName('HTML Translator')
    app.setOrganizationName('HTML Translation')

    # Load configuration
    config = AppConfig.load()

    # Setup default projects if needed
    setup_default_projects(config.projects_dir)

    # Create and show main window
    window = MainWindow(config)
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
