"""
Main Application Window
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QStatusBar, QLabel,
    QComboBox, QPushButton, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QGroupBox, QFrame, QToolBar, QSizePolicy, QCheckBox,
    QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView, QSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QMutex, QMutexLocker, QMetaObject, Q_ARG
from PySide6.QtGui import QAction, QFont, QColor, QTextCharFormat, QSyntaxHighlighter
from pathlib import Path
from typing import Optional, List
import re
import queue
import threading
import traceback
import json

from ..core.config import AppConfig, SUPPORTED_LANGUAGES
from ..core.project_manager import ProjectManager, Project
from ..core.translator import TranslationEngine, TranslationResult
from .glossary_editor import GlossaryEditor

# Debug mode flag - set to True for verbose logging
DEBUG = False


class HTMLHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for HTML code"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Tag format
        self.tag_format = QTextCharFormat()
        self.tag_format.setForeground(QColor('#569CD6'))

        # Attribute format
        self.attr_format = QTextCharFormat()
        self.attr_format.setForeground(QColor('#9CDCFE'))

        # String format
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor('#CE9178'))

        # Comment format
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor('#6A9955'))

        # Patterns
        self.rules = [
            # Tags
            (re.compile(r'<[/!]?\w+'), self.tag_format),
            (re.compile(r'>'), self.tag_format),
            (re.compile(r'/>'), self.tag_format),
            # Attributes
            (re.compile(r'\b\w+(?==)'), self.attr_format),
            # Strings
            (re.compile(r'"[^"]*"'), self.string_format),
            (re.compile(r"'[^']*'"), self.string_format),
        ]

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class TranslationWorker(QThread):
    """Single-threaded background worker for translation"""
    progress = Signal(int, int, str)  # current, total, filename
    file_done = Signal(object)  # TranslationResult
    error = Signal(str, str)  # filename, error
    finished_all = Signal(dict)  # final stats

    def __init__(self, engine: TranslationEngine, files: List[str],
                 target_lang: str, output_base: str, input_base: str,
                 include_lang_folder: bool = True, include_parent_folder: bool = True):
        super().__init__()
        self.engine = engine
        self.files = files
        self.target_lang = target_lang
        self.output_base = output_base
        self.input_base = input_base
        self.include_lang_folder = include_lang_folder
        self.include_parent_folder = include_parent_folder
        self._stop = False

    def stop(self):
        self._stop = True
        self.engine.stop()

    def _build_output_path(self, file_path: str) -> str:
        """Build output path respecting output settings"""
        output_dir = Path(self.output_base)

        # Add language folder if enabled
        if self.include_lang_folder:
            output_dir = output_dir / self.target_lang

        # Calculate relative path
        try:
            rel_path = Path(file_path).relative_to(self.input_base)
            if not self.include_parent_folder:
                # Strip the first component (source folder name)
                if len(rel_path.parts) > 1:
                    rel_path = Path(*rel_path.parts[1:])
                else:
                    rel_path = Path(rel_path.name)
        except ValueError:
            rel_path = Path(file_path).name

        final_path = str(output_dir / rel_path)
        print(f'[TranslationWorker] Output path: {final_path} (lang_folder={self.include_lang_folder}, parent_folder={self.include_parent_folder})')
        return final_path

    def run(self):
        total = len(self.files)
        stats = {'success': 0, 'errors': 0, 'new': 0}

        for i, file_path in enumerate(self.files):
            if self._stop:
                break

            self.progress.emit(i + 1, total, file_path)

            try:
                output_path = self._build_output_path(file_path)

                result = self.engine.translate_file(file_path, self.target_lang, output_path)
                self.file_done.emit(result)

                if result.success:
                    stats['success'] += 1
                    stats['new'] += result.stats.new_chunks
                else:
                    stats['errors'] += 1
                    self.error.emit(file_path, result.error_message)

            except Exception as e:
                stats['errors'] += 1
                self.error.emit(file_path, str(e))

        self.finished_all.emit(stats)


class WorkerThread(threading.Thread):
    """Individual worker thread for multi-threaded translation"""
    def __init__(self, worker_id, file_queue, engine, target_lang, output_base, input_base,
                 progress_callback, result_callback, error_callback, stop_event,
                 include_lang_folder: bool = True, include_parent_folder: bool = True):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.file_queue = file_queue
        self.engine = engine
        self.target_lang = target_lang
        self.output_base = output_base
        self.input_base = input_base
        self.progress_callback = progress_callback
        self.result_callback = result_callback
        self.error_callback = error_callback
        self.stop_event = stop_event
        self.include_lang_folder = include_lang_folder
        self.include_parent_folder = include_parent_folder

    def _build_output_path(self, file_path: str) -> str:
        """Build output path respecting output settings"""
        output_dir = Path(self.output_base)

        # Add language folder if enabled
        if self.include_lang_folder:
            output_dir = output_dir / self.target_lang

        # Calculate relative path
        try:
            rel_path = Path(file_path).relative_to(self.input_base)
            if not self.include_parent_folder:
                # Strip the first component (source folder name)
                if len(rel_path.parts) > 1:
                    rel_path = Path(*rel_path.parts[1:])
                else:
                    rel_path = Path(rel_path.name)
        except ValueError:
            rel_path = Path(file_path).name

        final_path = str(output_dir / rel_path)
        print(f'[Worker {self.worker_id}] Output path: {final_path} (lang_folder={self.include_lang_folder}, parent_folder={self.include_parent_folder})')
        return final_path

    def run(self):
        print(f'[Worker {self.worker_id}] Started (output_base={self.output_base}, lang_folder={self.include_lang_folder}, parent_folder={self.include_parent_folder})')
        while not self.stop_event.is_set():
            try:
                # Get file from queue with timeout
                try:
                    file_path = self.file_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if file_path is None:  # Poison pill to stop worker
                    break

                print(f'[Worker {self.worker_id}] Processing: {file_path}')

                try:
                    # Calculate output path using settings
                    output_path = self._build_output_path(file_path)

                    # Translate file
                    result = self.engine.translate_file(file_path, self.target_lang, output_path)

                    # Callback with result
                    self.result_callback(result)

                except Exception as e:
                    error_trace = traceback.format_exc()
                    print(f'[Worker {self.worker_id}] Error processing {file_path}:')
                    print(error_trace)
                    self.error_callback(file_path, f'{str(e)}\n{error_trace}')

                finally:
                    self.file_queue.task_done()

            except Exception as e:
                error_trace = traceback.format_exc()
                print(f'[Worker {self.worker_id}] Fatal error:')
                print(error_trace)
                break

        print(f'[Worker {self.worker_id}] Stopped')


class MultiThreadedTranslationWorker(QThread):
    """Multi-threaded background worker for translation with configurable worker count"""
    progress = Signal(int, int, str)  # current, total, filename
    file_done = Signal(object)  # TranslationResult
    error = Signal(str, str)  # filename, error
    finished_all = Signal(dict)  # final stats

    def __init__(self, engine: TranslationEngine, files: List[str],
                 target_lang: str, output_base: str, input_base: str, worker_count: int = 3,
                 include_lang_folder: bool = True, include_parent_folder: bool = True):
        super().__init__()
        self.engine = engine
        self.files = files
        self.target_lang = target_lang
        self.output_base = output_base
        self.input_base = input_base
        self.worker_count = max(1, min(10, worker_count))  # Clamp between 1-10
        self.include_lang_folder = include_lang_folder
        self.include_parent_folder = include_parent_folder
        self._stop_event = threading.Event()
        self.file_queue = queue.Queue()
        self.result_queue = queue.Queue()  # Queue for results from workers
        self.workers = []
        self.stats_lock = threading.Lock()
        self.stats = {'success': 0, 'errors': 0, 'new': 0}
        self.files_processed = 0

    def stop(self):
        print(f'[MultiWorker] Stop requested')
        self._stop_event.set()
        self.engine.stop()

        # Add poison pills to stop all workers
        for _ in range(self.worker_count):
            self.file_queue.put(None)

    def _on_file_done(self, result):
        """Callback to queue result (called from worker thread)"""
        self.result_queue.put(('result', result))

    def _on_error(self, file_path, error_msg):
        """Callback to queue error (called from worker thread)"""
        self.result_queue.put(('error', (file_path, error_msg)))

    def run(self):
        print(f'[MultiWorker] Starting with {self.worker_count} workers for {len(self.files)} files')
        print(f'[MultiWorker] Output settings: base={self.output_base}, lang_folder={self.include_lang_folder}, parent_folder={self.include_parent_folder}')

        # Add all files to queue
        for file_path in self.files:
            self.file_queue.put(file_path)

        # Create worker threads
        for i in range(self.worker_count):
            worker = WorkerThread(
                worker_id=i,
                file_queue=self.file_queue,
                engine=self.engine,
                target_lang=self.target_lang,
                output_base=self.output_base,
                input_base=self.input_base,
                progress_callback=lambda: None,  # Not used
                result_callback=self._on_file_done,
                error_callback=self._on_error,
                stop_event=self._stop_event,
                include_lang_folder=self.include_lang_folder,
                include_parent_folder=self.include_parent_folder
            )
            worker.start()
            self.workers.append(worker)

        # Process results from queue and emit signals (in QThread context)
        while not self._stop_event.is_set():
            # Process all available results
            while not self.result_queue.empty():
                try:
                    msg_type, data = self.result_queue.get_nowait()

                    if msg_type == 'result':
                        result = data
                        with self.stats_lock:
                            self.files_processed += 1
                            if result.success:
                                self.stats['success'] += 1
                                self.stats['new'] += result.stats.new_chunks
                            else:
                                self.stats['errors'] += 1

                        # Emit signals from QThread context (thread-safe)
                        self.progress.emit(self.files_processed, len(self.files), result.input_path)
                        self.file_done.emit(result)

                    elif msg_type == 'error':
                        file_path, error_msg = data
                        with self.stats_lock:
                            self.files_processed += 1
                            self.stats['errors'] += 1
                        self.progress.emit(self.files_processed, len(self.files), file_path)
                        self.error.emit(file_path, error_msg)

                except queue.Empty:
                    break

            # Check if all files processed
            if self.files_processed >= len(self.files):
                break

            # Sleep briefly to avoid busy-waiting
            self.msleep(50)  # Check every 50ms

        # Stop all workers
        self._stop_event.set()
        for _ in range(self.worker_count):
            self.file_queue.put(None)  # Poison pill

        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=2.0)

        print(f'[MultiWorker] Completed.')
        print(f'[MultiWorker] Files processed: {self.files_processed}/{len(self.files)}')
        print(f'[MultiWorker] Stats: {self.stats}')

        # Check for skipped files
        total_outcomes = self.stats['success'] + self.stats['errors']
        if total_outcomes < len(self.files):
            print(f'[MultiWorker] WARNING: {len(self.files) - total_outcomes} files may have been skipped!')

        self.finished_all.emit(self.stats)


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.project_manager = ProjectManager(config.projects_dir)
        self.current_project: Optional[Project] = None
        self.translation_engine: Optional[TranslationEngine] = None
        self.worker: Optional[TranslationWorker] = None

        # Editor state tracking
        self.current_translated_path: Optional[str] = None
        self.translated_modified: bool = False
        self.translation_in_progress: bool = False
        self.current_glossary_path: Optional[str] = None

        # Translation progress tracking
        self.total_source_files: int = 0
        self.already_translated_count: int = 0
        self.retranslate_file_count: int = 0  # 0 = normal translation, >0 = retranslate specific count

        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()
        self.load_last_project()

        # Auto-load last input directory if it exists
        if self.config.last_input_dir:
            last_dir = Path(self.config.last_input_dir)
            if last_dir.exists() and last_dir.is_dir():
                print(f'[UI] Auto-loading last input directory: {last_dir}')
                self.load_folder(str(last_dir))
            else:
                print(f'[UI] Last input directory no longer exists: {last_dir}')

        # Sync splitter sizes after UI is laid out
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.sync_splitter_sizes)

    def setup_ui(self):
        """Setup the main UI layout"""
        self.setWindowTitle('HTML Translator')
        self.resize(self.config.window_width, self.config.window_height)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Left panel
        left_panel = self.create_left_panel()
        self.main_splitter.addWidget(left_panel)

        # Right panel
        right_panel = self.create_right_panel()
        self.main_splitter.addWidget(right_panel)

        # Set splitter sizes
        self.main_splitter.setSizes(self.config.splitter_sizes)

    def create_left_panel(self) -> QWidget:
        """Create the left panel with project and file controls"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # Project selection
        project_group = QGroupBox('Project')
        project_layout = QVBoxLayout(project_group)

        self.project_combo = QComboBox()
        self.project_combo.currentTextChanged.connect(self.on_project_changed)
        project_layout.addWidget(self.project_combo)

        layout.addWidget(project_group)

        # File trees (dynamic height - uses remaining space)
        trees_group = QGroupBox('Files')
        trees_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        trees_layout = QVBoxLayout(trees_group)

        # Horizontal splitter for source and translated trees
        tree_splitter = QSplitter(Qt.Horizontal)

        # Source files tree
        source_panel = QWidget()
        source_panel_layout = QVBoxLayout(source_panel)
        source_panel_layout.setContentsMargins(0, 0, 0, 0)

        source_label = QLabel('Source Files')
        source_label.setStyleSheet('font-weight: bold;')
        source_panel_layout.addWidget(source_label)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(['Files'])
        self.file_tree.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.file_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Enable multi-select
        self.file_tree.itemClicked.connect(self.on_file_selected)
        self.file_tree.currentItemChanged.connect(self.on_file_selected_keyboard)
        self.file_tree.itemSelectionChanged.connect(self.on_source_tree_selection_changed)
        self.file_tree.itemExpanded.connect(self.on_source_item_expanded)
        self.file_tree.itemCollapsed.connect(self.on_source_item_collapsed)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_file_context_menu)
        source_panel_layout.addWidget(self.file_tree)

        tree_splitter.addWidget(source_panel)

        # Translated files tree
        translated_panel = QWidget()
        translated_panel_layout = QVBoxLayout(translated_panel)
        translated_panel_layout.setContentsMargins(0, 0, 0, 0)

        translated_label = QLabel('Translated Files')
        translated_label.setStyleSheet('font-weight: bold;')
        translated_panel_layout.addWidget(translated_label)

        self.translated_tree = QTreeWidget()
        self.translated_tree.setHeaderLabels(['Files'])
        self.translated_tree.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.translated_tree.itemSelectionChanged.connect(self.on_translated_tree_selection_changed)
        self.translated_tree.itemClicked.connect(self.on_translated_file_clicked)
        self.translated_tree.itemExpanded.connect(self.on_translated_item_expanded)
        self.translated_tree.itemCollapsed.connect(self.on_translated_item_collapsed)
        self.translated_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.translated_tree.customContextMenuRequested.connect(self.show_translated_tree_context_menu)
        translated_panel_layout.addWidget(self.translated_tree)

        tree_splitter.addWidget(translated_panel)

        # Set equal sizes for both trees
        tree_splitter.setSizes([150, 150])

        trees_layout.addWidget(tree_splitter)

        # Button layout with proportional widths: 25%, 25%, 50%
        btn_layout = QHBoxLayout()
        self.btn_select_folder = QPushButton('Select Source Folder')
        self.btn_select_folder.clicked.connect(self.select_folder)
        btn_layout.addWidget(self.btn_select_folder, 1)  # 25% width

        self.btn_select_files = QPushButton('Select Files')
        self.btn_select_files.clicked.connect(self.select_files)
        btn_layout.addWidget(self.btn_select_files, 1)  # 25% width

        self.btn_refresh = QPushButton('Refresh')
        self.btn_refresh.clicked.connect(self.refresh_trees)
        btn_layout.addWidget(self.btn_refresh, 2)  # 50% width

        trees_layout.addLayout(btn_layout)

        layout.addWidget(trees_group)

        # Target language
        lang_group = QGroupBox('Target Language')
        lang_layout = QVBoxLayout(lang_group)

        self.lang_combo = QComboBox()
        for code, name in SUPPORTED_LANGUAGES.items():
            self.lang_combo.addItem(f'{name} ({code})', code)

        # Set from config, fallback to zh-TW if saved value doesn't exist
        saved_lang = self.config.target_lang
        # Handle legacy 'zh' -> 'zh-TW' migration
        if saved_lang == 'zh':
            saved_lang = 'zh-TW'
            self.config.target_lang = 'zh-TW'
            self.config.save()

        # Block signals while setting initial value to avoid premature save
        self.lang_combo.blockSignals(True)

        # Find and set the index for the saved language
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == saved_lang:
                self.lang_combo.setCurrentIndex(i)
                break

        self.lang_combo.blockSignals(False)

        # Connect signal after setting initial value
        self.lang_combo.currentIndexChanged.connect(self.on_target_lang_changed)
        print(f'[UI] Language combo signal connected. Current: {self.lang_combo.currentData()}')
        lang_layout.addWidget(self.lang_combo)

        layout.addWidget(lang_group)

        # Glossary info (moved under Target Language)
        glossary_group = QGroupBox('Glossary')
        glossary_layout = QVBoxLayout(glossary_group)

        self.glossary_label = QLabel('0 terms')
        glossary_layout.addWidget(self.glossary_label)

        # Glossary selection dropdown
        glossary_select_layout = QHBoxLayout()

        self.glossary_combo = QComboBox()
        self.glossary_combo.setMinimumWidth(120)
        self.glossary_combo.currentIndexChanged.connect(self.on_glossary_selected)
        glossary_select_layout.addWidget(self.glossary_combo)

        self.btn_edit_glossary = QPushButton('Edit')
        self.btn_edit_glossary.clicked.connect(self.edit_glossary)
        glossary_select_layout.addWidget(self.btn_edit_glossary)

        glossary_layout.addLayout(glossary_select_layout)

        self.chk_case_sensitive = QCheckBox('Case Sensitive')
        self.chk_case_sensitive.setChecked(self.config.case_sensitive_glossary)
        self.chk_case_sensitive.stateChanged.connect(self.on_case_sensitive_changed)
        glossary_layout.addWidget(self.chk_case_sensitive)

        # Translation mode selection
        mode_layout = QHBoxLayout()
        mode_label = QLabel('Translation Mode:')
        mode_layout.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem('Glossary Reference (Default)', 'glossary_reference')
        self.mode_combo.addItem('Glossary Placeholder', 'glossary_placeholder')
        self.mode_combo.addItem('Full Context Reference', 'full_context')
        self.mode_combo.setToolTip(
            'Glossary Reference: Provide glossary as reference for each chunk (recommended)\n'
            'Glossary Placeholder: Replace terms with placeholders during translation\n'
            'Full Context Reference: Include full glossary in prompt'
        )
        # Set current mode (default to glossary_reference)
        current_mode = getattr(self.config, 'translation_mode', 'glossary_reference')
        if current_mode == 'full_context' or getattr(self.config, 'direct_translate_mode', False):
            current_mode = 'full_context'
        index = self.mode_combo.findData(current_mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)
        self.mode_combo.currentIndexChanged.connect(self.on_translation_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()

        glossary_layout.addLayout(mode_layout)

        # Worker count configuration
        worker_layout = QHBoxLayout()
        worker_label = QLabel('Worker Threads:')
        worker_layout.addWidget(worker_label)

        self.worker_spinbox = QSpinBox()
        self.worker_spinbox.setMinimum(1)
        self.worker_spinbox.setMaximum(10)
        self.worker_spinbox.setValue(self.config.worker_count)
        self.worker_spinbox.setToolTip('Number of parallel translation workers (1-10)')
        self.worker_spinbox.valueChanged.connect(self.on_worker_count_changed)
        worker_layout.addWidget(self.worker_spinbox)
        worker_layout.addStretch()

        glossary_layout.addLayout(worker_layout)

        layout.addWidget(glossary_group)

        # Model selection
        model_group = QGroupBox('AI Model')
        model_layout = QVBoxLayout(model_group)

        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        model_layout.addWidget(self.model_combo)

        self.btn_refresh_models = QPushButton('Refresh Models')
        self.btn_refresh_models.clicked.connect(self.refresh_models)
        model_layout.addWidget(self.btn_refresh_models)

        layout.addWidget(model_group)

        # Translation controls
        control_group = QGroupBox('Translation')
        control_layout = QVBoxLayout(control_group)

        # Split translate buttons
        translate_btn_layout = QHBoxLayout()

        self.btn_translate_rest = QPushButton('Translate Rest')
        self.btn_translate_rest.setStyleSheet('font-weight: bold; padding: 10px;')
        self.btn_translate_rest.clicked.connect(self.start_translation_rest)
        self.btn_translate_rest.setToolTip('Translate only files that have not been translated yet')
        translate_btn_layout.addWidget(self.btn_translate_rest)

        self.btn_retranslate_all = QPushButton('Re-Translate All')
        self.btn_retranslate_all.setStyleSheet('font-weight: bold; padding: 10px;')
        self.btn_retranslate_all.clicked.connect(self.start_retranslate_all)
        self.btn_retranslate_all.setToolTip('Re-translate all files (optionally clear existing translations)')
        translate_btn_layout.addWidget(self.btn_retranslate_all)

        control_layout.addLayout(translate_btn_layout)

        self.btn_stop = QPushButton('Stop')
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_translation)
        control_layout.addWidget(self.btn_stop)

        # Auto-refresh preview toggle
        self.chk_auto_refresh = QCheckBox('Auto-refresh Preview')
        self.chk_auto_refresh.setChecked(self.config.auto_refresh_preview)
        self.chk_auto_refresh.stateChanged.connect(self.on_auto_refresh_changed)
        control_layout.addWidget(self.chk_auto_refresh)

        layout.addWidget(control_group)

        return panel

    def create_right_panel(self) -> QWidget:
        """Create the right panel with preview, search results, and progress"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main vertical splitter for preview and search results
        main_splitter = QSplitter(Qt.Vertical)

        # Preview area (top half)
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_splitter = QSplitter(Qt.Horizontal)

        # Original HTML
        original_widget = QWidget()
        original_layout = QVBoxLayout(original_widget)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_label = QLabel('Original')
        original_label.setStyleSheet('font-weight: bold;')
        original_layout.addWidget(original_label)
        self.original_file_label = QLabel('')
        self.original_file_label.setStyleSheet('color: #0066cc; font-size: 11px; text-decoration: underline;')
        self.original_file_label.setWordWrap(True)
        self.original_file_label.setCursor(Qt.PointingHandCursor)
        self.original_file_label.mousePressEvent = lambda e: self.open_file_folder(self.original_file_label.toolTip())
        original_layout.addWidget(self.original_file_label)

        self.original_text = QTextEdit()
        self.original_text.setReadOnly(True)
        self.original_text.setFont(QFont('Consolas', 10))
        self.original_text.setContextMenuPolicy(Qt.CustomContextMenu)
        self.original_text.customContextMenuRequested.connect(self.show_original_context_menu)
        self.original_highlighter = HTMLHighlighter(self.original_text.document())
        original_layout.addWidget(self.original_text)
        self.preview_splitter.addWidget(original_widget)

        # Translated HTML (editable)
        translated_widget = QWidget()
        translated_layout = QVBoxLayout(translated_widget)
        translated_layout.setContentsMargins(0, 0, 0, 0)

        # Header with label
        self.translated_label = QLabel('Translated')
        self.translated_label.setStyleSheet('font-weight: bold;')
        translated_layout.addWidget(self.translated_label)
        self.translated_file_label = QLabel('')
        self.translated_file_label.setStyleSheet('color: #0066cc; font-size: 11px; text-decoration: underline;')
        self.translated_file_label.setWordWrap(True)
        self.translated_file_label.setCursor(Qt.PointingHandCursor)
        self.translated_file_label.mousePressEvent = lambda e: self.open_file_folder(self.translated_file_label.toolTip())
        translated_layout.addWidget(self.translated_file_label)

        self.translated_text = QTextEdit()
        self.translated_text.setReadOnly(False)  # Editable
        self.translated_text.setFont(QFont('Consolas', 10))
        self.translated_text.textChanged.connect(self.on_translated_text_changed)
        self.translated_highlighter = HTMLHighlighter(self.translated_text.document())
        translated_layout.addWidget(self.translated_text)
        self.preview_splitter.addWidget(translated_widget)

        preview_layout.addWidget(self.preview_splitter)
        main_splitter.addWidget(preview_widget)

        # Search Results area (bottom half)
        search_results_widget = QWidget()
        search_results_layout = QVBoxLayout(search_results_widget)
        search_results_layout.setContentsMargins(0, 0, 0, 0)

        # Search and Replace section - Split to align with Original and Translated
        search_replace_splitter = QSplitter(Qt.Horizontal)

        # LEFT: Search in Original files (aligned with Original preview)
        original_search_widget = QWidget()
        original_search_layout = QVBoxLayout(original_search_widget)
        original_search_layout.setContentsMargins(0, 0, 0, 0)
        original_search_layout.setSpacing(4)

        # Find in original row
        original_find_row = QHBoxLayout()
        original_find_row.addWidget(QLabel('Find in Original:'))
        self.original_search_field = QLineEdit()
        self.original_search_field.setPlaceholderText('Search in original files...')
        self.original_search_field.returnPressed.connect(self.find_in_all_original_files)
        original_find_row.addWidget(self.original_search_field)
        self.btn_find_all_original = QPushButton('Find in All Source Files')
        self.btn_find_all_original.clicked.connect(self.find_in_all_original_files)
        original_find_row.addWidget(self.btn_find_all_original)
        original_search_layout.addLayout(original_find_row)

        search_replace_splitter.addWidget(original_search_widget)

        # RIGHT: Search and Replace in Translated files (aligned with Translated preview)
        translated_search_widget = QWidget()
        translated_search_layout = QVBoxLayout(translated_search_widget)
        translated_search_layout.setContentsMargins(0, 0, 0, 0)
        translated_search_layout.setSpacing(4)

        # Find in translated row
        translated_find_row = QHBoxLayout()
        translated_find_row.addWidget(QLabel('Find in Translated:'))
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText('Search text...')
        self.search_field.returnPressed.connect(self.find_in_translated)
        translated_find_row.addWidget(self.search_field)
        self.btn_find = QPushButton('Find')
        self.btn_find.setFixedWidth(60)
        self.btn_find.clicked.connect(self.find_in_translated)
        translated_find_row.addWidget(self.btn_find)
        self.btn_find_all = QPushButton('Find in All Files')
        self.btn_find_all.clicked.connect(self.find_in_all_files)
        translated_find_row.addWidget(self.btn_find_all)
        translated_search_layout.addLayout(translated_find_row)

        # Replace row
        replace_row = QHBoxLayout()
        replace_row.addWidget(QLabel('Replace:'))
        self.replace_field = QLineEdit()
        self.replace_field.setPlaceholderText('Replace with...')
        replace_row.addWidget(self.replace_field)
        self.btn_replace = QPushButton('Replace')
        self.btn_replace.setFixedWidth(60)
        self.btn_replace.clicked.connect(self.replace_in_translated)
        replace_row.addWidget(self.btn_replace)
        self.btn_replace_all = QPushButton('Replace All')
        self.btn_replace_all.clicked.connect(self.replace_all_in_translated)
        replace_row.addWidget(self.btn_replace_all)
        self.btn_replace_all_files = QPushButton('Replace in All Files')
        self.btn_replace_all_files.clicked.connect(self.replace_in_all_files)
        replace_row.addWidget(self.btn_replace_all_files)
        translated_search_layout.addLayout(replace_row)

        search_replace_splitter.addWidget(translated_search_widget)

        # Set initial sizes (equal split)
        search_replace_splitter.setSizes([400, 400])

        # Sync search splitter sizes with preview splitter
        self.preview_splitter.splitterMoved.connect(
            lambda pos, index: search_replace_splitter.setSizes(self.preview_splitter.sizes())
        )
        search_replace_splitter.splitterMoved.connect(
            lambda pos, index: self.preview_splitter.setSizes(search_replace_splitter.sizes())
        )

        self.search_replace_splitter = search_replace_splitter
        search_results_layout.addWidget(search_replace_splitter)

        # Search results list
        self.search_results_label = QLabel('Search Results')
        self.search_results_label.setStyleSheet('font-weight: bold;')
        search_results_layout.addWidget(self.search_results_label)

        self.search_results_list = QListWidget()
        self.search_results_list.setFont(QFont('Consolas', 9))
        self.search_results_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.search_results_list.itemDoubleClicked.connect(self.on_search_result_clicked)
        self.search_results_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.search_results_list.customContextMenuRequested.connect(self.show_search_results_context_menu)
        search_results_layout.addWidget(self.search_results_list)

        main_splitter.addWidget(search_results_widget)

        # Set splitter sizes (50% each)
        main_splitter.setSizes([300, 300])

        layout.addWidget(main_splitter, stretch=2)

        # Progress area
        progress_group = QGroupBox('Translation Status')
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel('Ready')
        progress_layout.addWidget(self.progress_label)

        layout.addWidget(progress_group)

        return panel

    def setup_menu(self):
        """Setup the menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('&File')

        open_folder_action = QAction('Open Folder...', self)
        open_folder_action.setShortcut('Ctrl+O')
        open_folder_action.triggered.connect(self.select_folder)
        file_menu.addAction(open_folder_action)

        save_action = QAction('Save Translation', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_translated_file)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Project menu
        project_menu = menubar.addMenu('&Project')

        new_project_action = QAction('New Project...', self)
        new_project_action.triggered.connect(self.new_project)
        project_menu.addAction(new_project_action)

        delete_project_action = QAction('Delete Project...', self)
        delete_project_action.triggered.connect(self.delete_project)
        project_menu.addAction(delete_project_action)

        # Tools menu
        tools_menu = menubar.addMenu('&Tools')

        edit_glossary_action = QAction('Edit Glossary...', self)
        edit_glossary_action.setShortcut('Ctrl+G')
        edit_glossary_action.triggered.connect(self.edit_glossary)
        tools_menu.addAction(edit_glossary_action)

        # Settings menu
        settings_menu = menubar.addMenu('&Settings')

        output_settings_action = QAction('Output Settings...', self)
        output_settings_action.triggered.connect(self.show_output_settings)
        settings_menu.addAction(output_settings_action)

        # Help menu
        help_menu = menubar.addMenu('&Help')

        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = self.statusBar()

        self.status_label = QLabel('Ready')
        self.status_bar.addWidget(self.status_label, stretch=1)

        self.ollama_status = QLabel('Ollama: Checking...')
        self.status_bar.addPermanentWidget(self.ollama_status)

    def sync_splitter_sizes(self):
        """Sync search splitter sizes with preview splitter after UI is laid out"""
        if hasattr(self, 'preview_splitter') and hasattr(self, 'search_replace_splitter'):
            sizes = self.preview_splitter.sizes()
            if sum(sizes) > 0:  # Only sync if splitter has been laid out
                self.search_replace_splitter.setSizes(sizes)

    def get_output_directory(self, target_lang: str = None, include_source_folder: bool = True) -> Path:
        """
        Get the output directory path based on current settings.

        Args:
            target_lang: Target language code (uses current if None)
            include_source_folder: Whether to append the source folder name to the path

        Returns:
            Path object for the output directory
        """
        if target_lang is None:
            target_lang = self.lang_combo.currentData()

        # Start with base output directory
        # Use custom output root if set, otherwise use default 'output' folder
        if self.config.custom_output_root and self.config.custom_output_root.strip():
            output_dir = Path(self.config.custom_output_root)
        else:
            app_dir = Path(__file__).parent.parent
            output_dir = app_dir / 'output'

        # Add language code folder if enabled
        if self.config.include_lang_code_folder:
            output_dir = output_dir / target_lang

        # Add source folder name if enabled and requested
        if include_source_folder and self.config.include_parent_folder:
            if self.file_tree.topLevelItemCount() > 0:
                first_item = self.file_tree.topLevelItem(0)
                input_base = first_item.data(0, Qt.UserRole)
                if input_base:
                    folder_name = Path(input_base).name
                    output_dir = output_dir / folder_name

        return output_dir

    def load_last_project(self):
        """Load the last used project"""
        # Refresh project list
        projects = self.project_manager.list_projects()

        # Block signals during population to prevent multiple triggers
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItems(projects)

        print(f'[UI] Available projects: {projects}')
        print(f'[UI] Last project from config: {self.config.last_project}')

        # Select the project to load
        selected_project = None
        if self.config.last_project in projects:
            print(f'[UI] Loading last project: {self.config.last_project}')
            selected_project = self.config.last_project
            self.project_combo.setCurrentText(self.config.last_project)
        elif 'lineage2' in projects:
            print(f'[UI] Fallback to lineage2')
            selected_project = 'lineage2'
            self.project_combo.setCurrentText('lineage2')
        elif projects:
            print(f'[UI] Fallback to first project: {projects[0]}')
            selected_project = projects[0]
            self.project_combo.setCurrentText(projects[0])

        # Unblock signals and manually trigger project load
        self.project_combo.blockSignals(False)

        # Manually trigger project change to ensure it loads
        if selected_project:
            print(f'[UI] Manually triggering project load for: {selected_project}')
            self.on_project_changed(selected_project)

    @Slot(str)
    def on_project_changed(self, project_name: str):
        """Handle project selection change"""
        if not project_name:
            return

        print(f'[UI] Project changed to: {project_name}')

        try:
            self.current_project = self.project_manager.load_project(project_name)
            self.config.last_project = project_name
            self.config.save()
            print(f'[UI] Project loaded and saved to config')

            # Initialize translation engine (glossary will be loaded when selected from dropdown)
            project_path = self.project_manager.current_project_path
            self.translation_engine = TranslationEngine({
                'project_path': str(project_path),
                'project_name': project_name,
                'glossary_path': '',  # Will be set when glossary is selected
                'ollama_host': self.config.ollama.host,
                'ollama_port': self.config.ollama.port,
                'ollama_model': self.config.ollama.model,
                'case_sensitive_glossary': self.config.case_sensitive_glossary,
                'direct_translate_mode': self.config.direct_translate_mode,
                'translation_mode': getattr(self.config, 'translation_mode', 'glossary_reference'),
            })

            # Update UI
            glossary_count = self.current_project.statistics.glossary_terms
            self.glossary_label.setText(f'{glossary_count} terms')

            # Populate glossary dropdown
            self.populate_glossary_combo()

            # Check Ollama connection, auto-start if needed
            if self.translation_engine.check_connection():
                self.ollama_status.setText(f'Ollama: Connected ({self.config.ollama.model})')
                self.ollama_status.setStyleSheet('color: green;')
                # Check and download required models
                self.ensure_required_models()
            else:
                # Try to auto-start Ollama
                self.ollama_status.setText('Ollama: Starting...')
                self.ollama_status.setStyleSheet('color: orange;')
                if self.auto_start_ollama():
                    self.ollama_status.setText(f'Ollama: Connected ({self.config.ollama.model})')
                    self.ollama_status.setStyleSheet('color: green;')
                else:
                    self.ollama_status.setText('Ollama: Disconnected')
                    self.ollama_status.setStyleSheet('color: red;')


            self.status_label.setText(f'Loaded project: {project_name}')

            # Refresh available models
            self.refresh_models()

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load project: {e}')

    def auto_start_ollama(self) -> bool:
        """Try to auto-start Ollama and wait for it to be ready"""
        import subprocess
        import time
        import platform

        try:
            print('[Ollama] Attempting to auto-start Ollama...')

            # Start Ollama based on platform
            if platform.system() == 'Windows':
                # Try to start Ollama serve in background
                subprocess.Popen(
                    ['ollama', 'serve'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                # macOS/Linux
                subprocess.Popen(
                    ['ollama', 'serve'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            # Wait for Ollama to be ready (up to 10 seconds)
            for i in range(20):
                time.sleep(0.5)
                if self.translation_engine and self.translation_engine.check_connection():
                    print(f'[Ollama] Started successfully after {(i+1)*0.5:.1f}s')
                    # Check and download required models
                    self.ensure_required_models()
                    return True

            print('[Ollama] Failed to start within timeout')
            return False

        except FileNotFoundError:
            print('[Ollama] Ollama executable not found')
            return False
        except Exception as e:
            print(f'[Ollama] Auto-start failed: {e}')
            return False

    def ensure_required_models(self):
        """Check and download required Ollama models if not present"""
        import subprocess
        import platform

        required_models = ['gemma3:4b', 'qwen3-vl:4b-instruct']

        if not self.translation_engine:
            return

        # Get list of installed models
        installed_models = self.translation_engine.provider.get_available_models()
        installed_names = [m['name'] for m in installed_models]

        for model in required_models:
            # Check if model is installed (handle tag variations)
            model_base = model.split(':')[0]
            is_installed = any(model in name or name.startswith(model_base + ':') for name in installed_names)

            if not is_installed:
                print(f'[Ollama] Model {model} not found, downloading...')
                self.ollama_status.setText(f'Downloading {model}...')
                self.ollama_status.setStyleSheet('color: orange;')
                # Force UI update
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()

                try:
                    # Run ollama pull
                    if platform.system() == 'Windows':
                        result = subprocess.run(
                            ['ollama', 'pull', model],
                            capture_output=True,
                            text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                    else:
                        result = subprocess.run(
                            ['ollama', 'pull', model],
                            capture_output=True,
                            text=True
                        )

                    if result.returncode == 0:
                        print(f'[Ollama] Successfully downloaded {model}')
                    else:
                        print(f'[Ollama] Failed to download {model}: {result.stderr}')

                except Exception as e:
                    print(f'[Ollama] Error downloading {model}: {e}')
            else:
                print(f'[Ollama] Model {model} already installed')

    def refresh_models(self):
        """Refresh available Ollama models"""
        if not self.translation_engine:
            return

        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        models = self.translation_engine.provider.get_available_models()
        current_model = self.config.ollama.model

        for model in models:
            name = model['name']
            size = model.get('size', '')
            display = f"{name} ({size})" if size else name
            self.model_combo.addItem(display, name)

        # Set current model
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == current_model:
                self.model_combo.setCurrentIndex(i)
                break

        self.model_combo.blockSignals(False)

        if models:
            self.status_label.setText(f'Found {len(models)} Ollama models')

    @Slot(str)
    def on_model_changed(self, display_text: str):
        """Handle model selection change"""
        if not display_text:
            return

        model_name = self.model_combo.currentData()
        if not model_name:
            return

        # Update config
        self.config.ollama.model = model_name
        self.config.save()

        # Update translation engine
        if self.translation_engine:
            self.translation_engine.provider.set_model(model_name)
            self.ollama_status.setText(f'Ollama: Connected ({model_name})')
            self.status_label.setText(f'Switched to model: {model_name}')

    def select_folder(self):
        """Open folder selection dialog"""
        folder = QFileDialog.getExistingDirectory(
            self, 'Select Source Folder',
            self.config.last_input_dir or str(Path.home())
        )
        if folder:
            print(f'[UI] Folder selected: {folder}')
            self.config.last_input_dir = folder
            self.config.save()
            print(f'[UI] Last input dir saved to config')
            self.load_folder(folder)

    def select_files(self):
        """Open file selection dialog"""
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Select HTML Files',
            self.config.last_input_dir or str(Path.home()),
            'HTML Files (*.htm *.html)'
        )
        if files:
            self.config.last_input_dir = str(Path(files[0]).parent)
            self.config.save()
            self.load_files(files)

    def _has_translated_file(self, source_file_path: str) -> bool:
        """Check if a translated file exists for the given source file"""
        try:
            # Get target language
            target_lang = self.lang_combo.currentData()
            if not target_lang:
                return False

            # Get output directory using settings
            output_dir = self.get_output_directory(target_lang, include_source_folder=True)

            if not output_dir.exists():
                return False

            # Determine input base directory
            if self.file_tree.topLevelItemCount() == 0:
                return False

            first_item = self.file_tree.topLevelItem(0)
            input_base = first_item.data(0, Qt.UserRole)
            if not input_base:
                return False

            input_base_path = Path(input_base)
            if not input_base_path.is_dir():
                input_base_path = input_base_path.parent

            source_path = Path(source_file_path)

            # Calculate relative path (from input_base, not parent, since output_dir includes parent)
            try:
                rel_path = source_path.relative_to(input_base_path)
            except ValueError:
                rel_path = source_path.name

            output_path = output_dir / rel_path

            return output_path.exists()

        except Exception as e:
            print(f'[UI] Error checking translated file: {e}')
            return False

    def load_folder(self, folder: str):
        """Load files from a folder into the tree with proper nested structure"""
        self.file_tree.clear()
        folder_path = Path(folder)

        root = QTreeWidgetItem(self.file_tree, [folder_path.name])
        root.setData(0, Qt.UserRole, str(folder_path))

        # Build nested folder structure
        folder_items = {(): root}  # Map of path parts tuple to QTreeWidgetItem

        all_files = sorted(folder_path.rglob('*.htm')) + sorted(folder_path.rglob('*.html'))

        # First pass: collect all folders and files by parent
        folders_by_parent = {}  # parent_key -> set of folder names
        files_by_parent = {}    # parent_key -> list of (name, full_path)

        for file_path in all_files:
            rel_path = file_path.relative_to(folder_path)
            parts = rel_path.parts

            # Collect folders
            for i in range(len(parts) - 1):
                parent_key = parts[:i] if i > 0 else ()
                folder_name = parts[i]
                if parent_key not in folders_by_parent:
                    folders_by_parent[parent_key] = set()
                folders_by_parent[parent_key].add(folder_name)

            # Collect files
            parent_key = parts[:-1] if len(parts) > 1 else ()
            if parent_key not in files_by_parent:
                files_by_parent[parent_key] = []
            files_by_parent[parent_key].append((parts[-1], file_path))

        # Second pass: create tree items - folders first (sorted), then files (sorted)
        def create_children(parent_key, parent_item):
            # Create folders first (sorted alphabetically, case-insensitive)
            if parent_key in folders_by_parent:
                for folder_name in sorted(folders_by_parent[parent_key], key=str.lower):
                    folder_key = parent_key + (folder_name,)
                    if folder_key not in folder_items:
                        folder_item = QTreeWidgetItem(parent_item, [folder_name])
                        folder_item.setData(0, Qt.UserRole, str(folder_path / '/'.join(folder_key)))
                        folder_items[folder_key] = folder_item
                        # Recursively create children for this folder
                        create_children(folder_key, folder_item)

            # Create files (sorted alphabetically, case-insensitive)
            if parent_key in files_by_parent:
                for file_name, full_path in sorted(files_by_parent[parent_key], key=lambda x: x[0].lower()):
                    # Check if translated file exists
                    has_translation = self._has_translated_file(str(full_path))
                    display_name = f'✓ {file_name}' if has_translation else file_name
                    file_item = QTreeWidgetItem(parent_item, [display_name])
                    file_item.setData(0, Qt.UserRole, str(full_path))
                    if has_translation:
                        file_item.setForeground(0, Qt.GlobalColor.darkGreen)

        # Start from root
        create_children((), root)

        # Default: collapse all, only expand root
        self.file_tree.collapseAll()
        root.setExpanded(True)

        # Populate translated tree
        self.populate_translated_tree()

    def refresh_trees(self):
        """Refresh both source and translated trees"""
        # Refresh translated tree to show current output files
        self.populate_translated_tree()
        self.status_label.setText('Trees refreshed')

    def populate_translated_tree(self):
        """Populate translated tree with existing translated files"""
        self.translated_tree.clear()

        # Get target language
        target_lang = self.lang_combo.currentData()
        if not target_lang:
            return

        # Get input base to mirror structure
        if self.file_tree.topLevelItemCount() == 0:
            return

        first_item = self.file_tree.topLevelItem(0)
        input_base = first_item.data(0, Qt.UserRole)
        if not input_base or not Path(input_base).is_dir():
            return

        input_base_path = Path(input_base)

        # Get output directory using settings (includes parent folder if enabled)
        translated_folder = self.get_output_directory(target_lang, include_source_folder=True)

        if not translated_folder.exists():
            return

        # Use the actual translated folder name for display
        # This reflects the output settings (parent folder included or not)
        display_name = translated_folder.name

        # Create root item with actual output folder name
        root = QTreeWidgetItem(self.translated_tree, [display_name])
        root.setData(0, Qt.UserRole, str(translated_folder))

        # Build folder structure
        folder_items = {(): root}

        all_files = sorted(translated_folder.rglob('*.htm')) + sorted(translated_folder.rglob('*.html'))

        # Collect folders and files
        folders_by_parent = {}
        files_by_parent = {}

        for file_path in all_files:
            try:
                rel_path = file_path.relative_to(translated_folder)
                parts = rel_path.parts

                # Collect folders
                for i in range(len(parts) - 1):
                    parent_key = parts[:i] if i > 0 else ()
                    folder_name = parts[i]
                    if parent_key not in folders_by_parent:
                        folders_by_parent[parent_key] = set()
                    folders_by_parent[parent_key].add(folder_name)

                # Collect files
                parent_key = parts[:-1] if len(parts) > 1 else ()
                if parent_key not in files_by_parent:
                    files_by_parent[parent_key] = []
                # Store both source path (for syncing) and translated path (for explorer)
                source_path = input_base_path / rel_path
                translated_path = file_path
                files_by_parent[parent_key].append((parts[-1], str(source_path), str(translated_path)))
            except ValueError:
                continue

        # Create tree items
        def create_children(parent_key, parent_item):
            # Create folders first (sorted alphabetically, case-insensitive)
            if parent_key in folders_by_parent:
                for folder_name in sorted(folders_by_parent[parent_key], key=str.lower):
                    folder_key = parent_key + (folder_name,)
                    if folder_key not in folder_items:
                        folder_item = QTreeWidgetItem(parent_item, [folder_name])
                        # Set folder path for context menu
                        folder_path = translated_folder / '/'.join(folder_key)
                        folder_item.setData(0, Qt.UserRole, str(folder_path))
                        folder_items[folder_key] = folder_item
                        create_children(folder_key, folder_item)

            # Create files (sorted alphabetically, case-insensitive)
            if parent_key in files_by_parent:
                for file_name, source_path, translated_path in sorted(files_by_parent[parent_key], key=lambda x: x[0].lower()):
                    file_item = QTreeWidgetItem(parent_item, [file_name])
                    file_item.setData(0, Qt.UserRole, source_path)  # Store source path for syncing
                    file_item.setData(0, Qt.UserRole + 1, translated_path)  # Store translated path for explorer

        create_children((), root)

        # Collapse all, expand root
        self.translated_tree.collapseAll()
        root.setExpanded(True)

    def add_translated_file_to_tree(self, source_file_path: str):
        """Update source tree to show checkmark when translation completes"""
        if DEBUG:
            print(f'[UI] Adding checkmark for: {source_file_path}')

        # Update checkmark in source tree (live update)
        def find_item(parent, path):
            for i in range(parent.childCount()):
                child = parent.child(i)
                child_path = child.data(0, Qt.UserRole)
                if child_path == path:
                    return child
                result = find_item(child, path)
                if result:
                    return result
            return None

        # Search for item in source tree
        root = self.file_tree.invisibleRootItem()
        item = find_item(root, source_file_path)

        if item:
            # Add checkmark to source file (live update)
            file_name = Path(source_file_path).name
            current_text = item.text(0)
            if DEBUG:
                print(f'[UI] Found item in tree. Current text: "{current_text}"')
            if not current_text.startswith('✓'):
                item.setText(0, f'✓ {file_name}')
                item.setForeground(0, Qt.GlobalColor.darkGreen)
                if DEBUG:
                    print(f'[UI] Checkmark added: ✓ {file_name}')
            elif DEBUG:
                print(f'[UI] Checkmark already exists')
        else:
            print(f'[UI] WARNING: Item not found in tree for path: {source_file_path}')

        # Add to translated tree efficiently
        self._add_single_file_to_translated_tree(source_file_path)

    def _add_single_file_to_translated_tree(self, source_file_path: str):
        """Add a single file to translated tree without repopulating entire tree"""
        if self.translated_tree.topLevelItemCount() == 0:
            # Tree not initialized, do full population
            self.populate_translated_tree()
            return

        # Get target language
        target_lang = self.lang_combo.currentData()
        if not target_lang:
            return

        # Get output directory using settings
        output_dir = self.get_output_directory(target_lang, include_source_folder=True)

        if not output_dir.exists():
            return

        # Get input base
        first_item = self.file_tree.topLevelItem(0)
        input_base = first_item.data(0, Qt.UserRole)
        if not input_base or not Path(input_base).is_dir():
            return

        input_base_path = Path(input_base)
        source_path = Path(source_file_path)

        try:
            # Calculate relative path from input base (not parent, since output_dir includes parent)
            rel_path = source_path.relative_to(input_base_path)
        except ValueError:
            # If not relative, just repopulate
            self.populate_translated_tree()
            return

        # Check if translated file exists
        output_file = output_dir / rel_path
        if not output_file.exists():
            return

        # Find or create the parent folder structure in translated tree
        parts = rel_path.parts

        # Navigate to parent folder
        current_item = self.translated_tree.topLevelItem(0)  # Root folder
        for folder_name in parts[:-1]:  # Skip file name only
            # Find folder
            found = False
            for i in range(current_item.childCount()):
                child = current_item.child(i)
                if child.text(0) == folder_name:
                    current_item = child
                    found = True
                    break

            if not found:
                # Create folder
                new_folder = QTreeWidgetItem(current_item, [folder_name])
                current_item = new_folder

        # Check if file already exists
        file_name = parts[-1]
        for i in range(current_item.childCount()):
            child = current_item.child(i)
            if child.text(0) == file_name or child.text(0) == f'✓ {file_name}':
                # File already exists, just update it
                child.setText(0, file_name)
                child.setData(0, Qt.UserRole, source_file_path)
                return

        # Add new file
        file_item = QTreeWidgetItem(current_item, [file_name])
        file_item.setData(0, Qt.UserRole, source_file_path)

    def load_files(self, files: List[str]):
        """Load specific files into the tree"""
        self.file_tree.clear()

        for file_path in files:
            # Check if translated file exists
            has_translation = self._has_translated_file(file_path)
            file_name = Path(file_path).name
            display_name = f'✓ {file_name}' if has_translation else file_name
            item = QTreeWidgetItem(self.file_tree, [display_name])
            item.setData(0, Qt.UserRole, file_path)
            if has_translation:
                item.setForeground(0, Qt.GlobalColor.darkGreen)

        # Populate translated tree
        self.populate_translated_tree()

    def expand_all_folders(self):
        """Expand all folders (source tree only, translated tree syncs automatically)"""
        self.file_tree.expandAll()

    def collapse_all_folders(self):
        """Collapse all folders (source tree only, translated tree syncs automatically)"""
        self.file_tree.collapseAll()
        # Keep root expanded
        if self.file_tree.topLevelItemCount() > 0:
            self.file_tree.topLevelItem(0).setExpanded(True)

    def on_file_selected(self, item: QTreeWidgetItem, column: int):
        """Handle file selection in tree"""
        file_path = item.data(0, Qt.UserRole)
        if file_path and Path(file_path).is_file():
            # Auto-save before switching to another file
            if self.translated_modified and self.current_translated_path:
                self.save_translated_file()
            self.preview_file(file_path)

    def on_file_selected_keyboard(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        """Handle file selection via keyboard (arrow keys)"""
        if current:
            self.on_file_selected(current, 0)

    def on_source_tree_selection_changed(self):
        """Sync selection from source tree to translated tree"""
        selected_items = self.file_tree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        file_path = item.data(0, Qt.UserRole)
        if not file_path:
            return

        # Find corresponding item in translated tree
        self.sync_translated_tree_selection(file_path)

    def on_translated_tree_selection_changed(self):
        """Sync selection from translated tree to source tree"""
        selected_items = self.translated_tree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        file_path = item.data(0, Qt.UserRole)
        if not file_path:
            return

        # Find corresponding item in source tree
        self.sync_source_tree_selection(file_path)

    def on_translated_file_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle translated file click - preview the file"""
        file_path = item.data(0, Qt.UserRole)
        if file_path and Path(file_path).is_file():
            # Auto-save before switching
            if self.translated_modified and self.current_translated_path:
                self.save_translated_file()
            self.preview_file(file_path)

    def on_source_item_expanded(self, item: QTreeWidgetItem):
        """Sync folder expansion from source to translated tree"""
        self.sync_folder_expansion(item, True, self.file_tree, self.translated_tree)

    def on_source_item_collapsed(self, item: QTreeWidgetItem):
        """Sync folder collapse from source to translated tree"""
        self.sync_folder_expansion(item, False, self.file_tree, self.translated_tree)

    def on_translated_item_expanded(self, item: QTreeWidgetItem):
        """Sync folder expansion from translated to source tree"""
        self.sync_folder_expansion(item, True, self.translated_tree, self.file_tree)

    def on_translated_item_collapsed(self, item: QTreeWidgetItem):
        """Sync folder collapse from translated to source tree"""
        self.sync_folder_expansion(item, False, self.translated_tree, self.file_tree)

    def sync_folder_expansion(self, item: QTreeWidgetItem, expanded: bool, source_tree: QTreeWidget, target_tree: QTreeWidget):
        """Sync folder expansion/collapse between trees"""
        # Get the folder path or name
        folder_text = item.text(0).replace('✓ ', '')  # Remove checkmark if present

        # Find corresponding folder in target tree
        def find_folder(parent, text):
            for i in range(parent.childCount()):
                child = parent.child(i)
                child_text = child.text(0).replace('✓ ', '')
                if child_text == text:
                    return child
                result = find_folder(child, text)
                if result:
                    return result
            return None

        # Block signals to prevent infinite loop
        target_tree.blockSignals(True)

        corresponding = find_folder(target_tree.invisibleRootItem(), folder_text)
        if corresponding:
            corresponding.setExpanded(expanded)

        target_tree.blockSignals(False)

    def sync_translated_tree_selection(self, source_file_path: str):
        """Select corresponding file in translated tree"""
        # Block signals to avoid infinite loop
        self.translated_tree.blockSignals(True)

        # Find the item in translated tree with matching path
        def find_item(parent, path):
            for i in range(parent.childCount()):
                child = parent.child(i)
                child_path = child.data(0, Qt.UserRole)
                if child_path == path:
                    return child
                result = find_item(child, path)
                if result:
                    return result
            return None

        # Search from root
        item = find_item(self.translated_tree.invisibleRootItem(), source_file_path)
        if item:
            self.translated_tree.setCurrentItem(item)
            self.translated_tree.scrollToItem(item)

        self.translated_tree.blockSignals(False)

    def sync_source_tree_selection(self, translated_file_path: str):
        """Select corresponding file in source tree"""
        # Block signals to avoid infinite loop
        self.file_tree.blockSignals(True)

        # Find the item in source tree with matching path
        def find_item(parent, path):
            for i in range(parent.childCount()):
                child = parent.child(i)
                child_path = child.data(0, Qt.UserRole)
                if child_path == path:
                    return child
                result = find_item(child, path)
                if result:
                    return result
            return None

        # Search from root
        item = find_item(self.file_tree.invisibleRootItem(), translated_file_path)
        if item:
            self.file_tree.setCurrentItem(item)
            self.file_tree.scrollToItem(item)

        self.file_tree.blockSignals(False)

    def preview_file(self, file_path: str):
        """Show file preview with translated version if exists"""
        try:
            # Show original
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.original_text.setPlainText(content)
            self.original_file_label.setText(file_path)
            self.original_file_label.setToolTip(file_path)

            # Get target language and output directory using settings
            target_lang = self.lang_combo.currentData()
            output_dir = self.get_output_directory(target_lang, include_source_folder=True)

            # Try to find relative path from input base
            if self.file_tree.topLevelItemCount() > 0:
                first_item = self.file_tree.topLevelItem(0)
                input_base = first_item.data(0, Qt.UserRole)
                if input_base and Path(input_base).is_dir():
                    try:
                        rel_path = Path(file_path).relative_to(Path(input_base))
                    except ValueError:
                        rel_path = Path(file_path).name
                else:
                    rel_path = Path(file_path).name
            else:
                rel_path = Path(file_path).name

            translated_path = output_dir / rel_path

            # Block signals while loading to avoid triggering textChanged
            self.translated_text.blockSignals(True)

            if translated_path.exists():
                with open(translated_path, 'r', encoding='utf-8') as f:
                    translated_content = f.read()
                self.translated_text.setPlainText(translated_content)
                self.current_translated_path = str(translated_path)
                self.translated_file_label.setText(str(translated_path))
                self.translated_file_label.setToolTip(str(translated_path))
                # Keep read-only if translation is in progress
                if not self.translation_in_progress:
                    self.translated_text.setReadOnly(False)
            else:
                self.translated_text.setPlainText('(No translation yet)')
                self.current_translated_path = None
                self.translated_file_label.setText(str(translated_path) + ' (not created)')
                self.translated_file_label.setToolTip(str(translated_path))
                self.translated_text.setReadOnly(True)

            # Keep signals blocked if translation is in progress
            if not self.translation_in_progress:
                self.translated_text.blockSignals(False)

            # Reset modification state
            self.translated_modified = False
            self.update_translated_label()

        except Exception as e:
            self.original_text.setPlainText(f'Error loading file: {e}')

    def open_file_folder(self, file_path: str):
        """Open the folder containing the file in file explorer"""
        if not file_path:
            return
        import subprocess
        import platform

        path = Path(file_path)
        folder = path.parent if path.is_file() or not path.exists() else path

        if platform.system() == 'Windows':
            subprocess.run(['explorer', str(folder)])
        elif platform.system() == 'Darwin':
            subprocess.run(['open', str(folder)])
        else:
            subprocess.run(['xdg-open', str(folder)])

    def open_target_folder(self):
        """Open the target/translated output folder in file explorer"""
        # Get target language
        target_lang = self.lang_combo.currentData()
        if not target_lang:
            QMessageBox.warning(self, 'Warning', 'Please select a target language.')
            return

        # Get the full output directory with lang code and parent folder
        output_dir = self.get_output_directory(target_lang, include_source_folder=True)

        # Create directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Open in file explorer
        import subprocess
        import platform

        if platform.system() == 'Windows':
            subprocess.run(['explorer', str(output_dir)])
        elif platform.system() == 'Darwin':
            subprocess.run(['open', str(output_dir)])
        else:
            subprocess.run(['xdg-open', str(output_dir)])

    def show_original_context_menu(self, position):
        """Show context menu for original text with translate option"""
        menu = self.original_text.createStandardContextMenu()

        # Add separator and translate option
        menu.addSeparator()

        translate_action = QAction('Translate Selection', self)
        translate_action.setEnabled(self.original_text.textCursor().hasSelection())
        translate_action.triggered.connect(self.translate_selection)
        menu.addAction(translate_action)

        menu.exec_(self.original_text.mapToGlobal(position))

    def translate_selection(self, skip_cache: bool = False):
        """Translate the selected text in the original panel"""
        cursor = self.original_text.textCursor()
        if not cursor.hasSelection():
            self.status_label.setText('No text selected')
            return

        selected_text = cursor.selectedText()
        if not selected_text.strip():
            self.status_label.setText('No text selected')
            return

        if not self.translation_engine:
            QMessageBox.warning(self, 'Warning', 'Please select a project first.')
            return

        target_lang = self.lang_combo.currentData()

        self.status_label.setText(f'Translating: {selected_text[:50]}...')
        self.btn_translate_rest.setEnabled(False)
        self.btn_retranslate_all.setEnabled(False)

        try:
            # Translate the selection
            translated = self.translation_engine.translate_text(selected_text, target_lang)

            # Show result in a dialog with editable text
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton

            dialog = QDialog(self)
            dialog.setWindowTitle('Translation Result')
            dialog.setMinimumSize(500, 400)

            layout = QVBoxLayout(dialog)

            # Original text (read-only)
            layout.addWidget(QLabel('Original:'))
            original_edit = QTextEdit()
            original_edit.setPlainText(selected_text)
            original_edit.setReadOnly(True)
            original_edit.setMaximumHeight(100)
            layout.addWidget(original_edit)

            # Translated text (editable)
            layout.addWidget(QLabel('Translated (editable):'))
            translated_edit = QTextEdit()
            translated_edit.setPlainText(translated)
            layout.addWidget(translated_edit)

            # Buttons
            btn_layout = QHBoxLayout()
            copy_btn = QPushButton('Copy Translation')
            glossary_btn = QPushButton('Add to Glossary')
            close_btn = QPushButton('Close')

            btn_layout.addWidget(copy_btn)
            btn_layout.addWidget(glossary_btn)
            btn_layout.addStretch()
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)

            result_action = {'action': None}

            def on_copy():
                result_action['action'] = 'copy'
                dialog.accept()

            def on_glossary():
                result_action['action'] = 'glossary'
                dialog.accept()

            copy_btn.clicked.connect(on_copy)
            glossary_btn.clicked.connect(on_glossary)
            close_btn.clicked.connect(dialog.reject)

            dialog.exec()

            # Get the edited translation
            edited_translation = translated_edit.toPlainText()

            if result_action['action'] == 'copy':
                from PySide6.QtWidgets import QApplication
                QApplication.clipboard().setText(edited_translation)
                self.status_label.setText('Translation copied to clipboard')
            elif result_action['action'] == 'glossary':
                self.add_to_glossary(selected_text, edited_translation)
            else:
                self.status_label.setText('Translation complete')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Translation failed: {e}')
            self.status_label.setText('Translation failed')
        finally:
            self.btn_translate_rest.setEnabled(True)
            self.btn_retranslate_all.setEnabled(True)

    def show_file_context_menu(self, position):
        """Show context menu for file tree"""
        item = self.file_tree.itemAt(position)
        if not item:
            return

        file_path = item.data(0, Qt.UserRole)
        if not file_path:
            return

        # Get all selected items
        selected_items = self.file_tree.selectedItems()
        selected_count = len(selected_items)

        menu = QMenu(self)

        # Determine context: single file, multiple files, or folder
        if selected_count == 1:
            if Path(file_path).is_dir():
                # Single folder selected
                retranslate_action = QAction('Re-translate All in Folder', self)
                retranslate_action.triggered.connect(lambda: self.retranslate_folder(item))
                menu.addAction(retranslate_action)
            else:
                # Single file selected
                retranslate_action = QAction('Re-translate', self)
                retranslate_action.triggered.connect(lambda: self.retranslate_file(item))
                menu.addAction(retranslate_action)
        else:
            # Multiple items selected
            retranslate_action = QAction(f'Re-translate All ({selected_count} items)', self)
            retranslate_action.triggered.connect(lambda: self.retranslate_selected_items(selected_items))
            menu.addAction(retranslate_action)

        menu.addSeparator()

        # Open in Explorer option (use clicked item's path)
        open_explorer_action = QAction('Open in Explorer', self)
        open_explorer_action.triggered.connect(lambda: self.open_file_folder(file_path))
        menu.addAction(open_explorer_action)

        menu.addSeparator()

        # Expand/Collapse options
        expand_all_action = QAction('Expand All', self)
        expand_all_action.triggered.connect(self.expand_all_folders)
        menu.addAction(expand_all_action)

        collapse_all_action = QAction('Collapse All', self)
        collapse_all_action.triggered.connect(self.collapse_all_folders)
        menu.addAction(collapse_all_action)

        menu.exec_(self.file_tree.viewport().mapToGlobal(position))

    def show_translated_tree_context_menu(self, position):
        """Show context menu for translated file tree"""
        item = self.translated_tree.itemAt(position)
        if not item:
            return

        # For files, use UserRole+1 (translated path), for folders use UserRole
        translated_path = item.data(0, Qt.UserRole + 1)
        if not translated_path:
            translated_path = item.data(0, Qt.UserRole)  # Fallback for folders

        menu = QMenu(self)

        # Open in Explorer option (only if we have a path)
        if translated_path:
            open_explorer_action = QAction('Open in Explorer', self)
            open_explorer_action.triggered.connect(lambda: self.open_file_folder(translated_path))
            menu.addAction(open_explorer_action)
            menu.addSeparator()

        # Expand/Collapse options (always available)
        expand_all_action = QAction('Expand All', self)
        expand_all_action.triggered.connect(self.expand_all_folders)
        menu.addAction(expand_all_action)

        collapse_all_action = QAction('Collapse All', self)
        collapse_all_action.triggered.connect(self.collapse_all_folders)
        menu.addAction(collapse_all_action)

        menu.exec_(self.translated_tree.viewport().mapToGlobal(position))

    def show_search_results_context_menu(self, position):
        """Show context menu for search results list"""
        selected_items = self.search_results_list.selectedItems()
        if not selected_items:
            return

        menu = QMenu(self)

        # Retranslate option
        if len(selected_items) == 1:
            retranslate_action = QAction('Retranslate', self)
        else:
            retranslate_action = QAction(f'Retranslate ({len(selected_items)} files)', self)
        retranslate_action.triggered.connect(self.retranslate_search_results)
        menu.addAction(retranslate_action)

        menu.addSeparator()

        # Open in Explorer option (only for single selection)
        if len(selected_items) == 1:
            item = selected_items[0]
            data = item.data(Qt.UserRole)
            if data and isinstance(data, dict):
                file_path = data.get('file_path')
                if file_path:
                    open_explorer_action = QAction('Open in Explorer', self)
                    open_explorer_action.triggered.connect(lambda fp=file_path: self.open_file_folder(fp))
                    menu.addAction(open_explorer_action)

        menu.exec_(self.search_results_list.viewport().mapToGlobal(position))

    def retranslate_search_results(self):
        """Retranslate files from search results selection"""
        selected_items = self.search_results_list.selectedItems()
        if not selected_items:
            return

        if not self.translation_engine:
            QMessageBox.warning(self, 'Warning', 'Please select a project first.')
            return

        # Collect unique source file paths
        source_files = set()
        target_lang = self.lang_combo.currentData()
        output_dir = self.get_output_directory(target_lang, include_source_folder=True)

        for item in selected_items:
            data = item.data(Qt.UserRole)
            if not data or not isinstance(data, dict):
                continue

            file_path = data.get('file_path')
            is_original = data.get('is_original', True)

            if not file_path:
                continue

            if is_original:
                # Source file - use directly
                if Path(file_path).is_file():
                    source_files.add(file_path)
            else:
                # Translated file - find corresponding source file
                try:
                    translated_path = Path(file_path)
                    rel_path = translated_path.relative_to(output_dir)

                    # Get input base from file tree
                    if self.file_tree.topLevelItemCount() > 0:
                        first_item = self.file_tree.topLevelItem(0)
                        input_base = first_item.data(0, Qt.UserRole)
                        if input_base:
                            # output_dir includes parent folder, so rel_path is from input_base
                            source_path = Path(input_base) / rel_path
                            if source_path.is_file():
                                source_files.add(str(source_path))
                except (ValueError, TypeError):
                    continue

        if not source_files:
            QMessageBox.warning(self, 'Warning', 'No valid files selected.')
            return

        # Translate the files
        self._translate_files_force(list(source_files), skip_cache=True)

    def retranslate_file(self, item: QTreeWidgetItem):
        """Re-translate a single file, bypassing cache"""
        file_path = item.data(0, Qt.UserRole)
        if not file_path or not Path(file_path).is_file():
            return

        if not self.translation_engine:
            QMessageBox.warning(self, 'Warning', 'Please select a project first.')
            return

        # Translate the file with cache bypass
        self._translate_files_force([file_path], skip_cache=True)

    def retranslate_folder(self, item: QTreeWidgetItem):
        """Re-translate all files in a folder, bypassing cache"""
        files = []
        self.collect_files(item, files)

        if not files:
            return

        if not self.translation_engine:
            QMessageBox.warning(self, 'Warning', 'Please select a project first.')
            return

        # Translate all files with cache bypass
        self._translate_files_force(files, skip_cache=True)

    def retranslate_selected_items(self, selected_items: list):
        """Re-translate all selected files and folders, bypassing cache"""
        if not self.translation_engine:
            QMessageBox.warning(self, 'Warning', 'Please select a project first.')
            return

        files = []
        for item in selected_items:
            file_path = item.data(0, Qt.UserRole)
            if not file_path:
                continue

            path = Path(file_path)
            if path.is_file():
                files.append(file_path)
            elif path.is_dir():
                # Collect all files from folder
                self.collect_files(item, files)

        if not files:
            QMessageBox.warning(self, 'Warning', 'No valid files in selection.')
            return

        # Remove duplicates while preserving order
        files = list(dict.fromkeys(files))

        # Translate all files with cache bypass
        self._translate_files_force(files, skip_cache=True)

    def _translate_files_force(self, files: List[str], skip_cache: bool = False):
        """Force translate files (used by right-click retranslate)"""
        target_lang = self.lang_combo.currentData()
        # Use base output directory - worker adds target_lang and file structure
        if self.config.custom_output_root and self.config.custom_output_root.strip():
            output_dir = self.config.custom_output_root
        else:
            app_dir = Path(__file__).parent.parent
            output_dir = str(app_dir / 'output')

        # Determine input base directory
        if self.file_tree.topLevelItemCount() > 0:
            first_item = self.file_tree.topLevelItem(0)
            input_base = first_item.data(0, Qt.UserRole)
            if input_base and Path(input_base).is_dir():
                input_base = str(Path(input_base).parent)
            elif input_base:
                input_base = str(Path(input_base).parent.parent)
            else:
                input_base = str(Path(files[0]).parent.parent)
        else:
            input_base = str(Path(files[0]).parent.parent)

        # Setup UI
        self.btn_translate_rest.setEnabled(False)
        self.btn_retranslate_all.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_stop.setStyleSheet('background-color: #ff4444; color: white;')

        # Track retranslate count for smart status display
        self.retranslate_file_count = len(files)
        self.progress_bar.setMaximum(self.retranslate_file_count)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f'Re-translating {self.retranslate_file_count} file(s)...')

        # Ensure current translation mode is set
        current_mode = self.mode_combo.currentData()
        self.translation_engine.set_translation_mode(current_mode)

        # Start worker
        self.translation_engine.reset_stop()
        print(f'[Translation] Starting with {self.config.worker_count} worker threads')
        self.worker = MultiThreadedTranslationWorker(
            self.translation_engine, files, target_lang, output_dir, input_base, self.config.worker_count,
            include_lang_folder=self.config.include_lang_code_folder,
            include_parent_folder=self.config.include_parent_folder
        )
        self.worker.progress.connect(self.on_translation_progress)
        self.worker.file_done.connect(self.on_file_translated)
        self.worker.error.connect(self.on_translation_error)
        self.worker.finished_all.connect(self.on_translation_finished)
        self.worker.start()

    def start_translation_rest(self):
        """Translate only files that haven't been translated yet"""
        if not self.translation_engine:
            QMessageBox.warning(self, 'Warning', 'Please select a project first.')
            return

        # Get selected files
        files = []
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            self.collect_files(item, files)

        if not files:
            QMessageBox.warning(self, 'Warning', 'Please select files to translate.')
            return

        # Get target language and output directory
        target_lang = self.lang_combo.currentData()
        if self.config.custom_output_root and self.config.custom_output_root.strip():
            output_dir = Path(self.config.custom_output_root)
        else:
            app_dir = Path(__file__).parent.parent
            output_dir = app_dir / 'output'

        # Determine input base directory
        if self.file_tree.topLevelItemCount() > 0:
            first_item = self.file_tree.topLevelItem(0)
            input_base = first_item.data(0, Qt.UserRole)
            if input_base and Path(input_base).is_dir():
                input_base = str(Path(input_base).parent)
            elif input_base:
                input_base = str(Path(input_base).parent.parent)
            else:
                input_base = str(Path(files[0]).parent.parent)
        else:
            input_base = str(Path(files[0]).parent.parent)

        # Filter out files that already have translations
        files_to_translate = []
        for file_path in files:
            try:
                rel_path = Path(file_path).relative_to(input_base)
            except ValueError:
                rel_path = Path(file_path).name
            output_path = output_dir / target_lang / rel_path

            # Only add if translated file doesn't exist
            if not output_path.exists():
                files_to_translate.append(file_path)

        if not files_to_translate:
            QMessageBox.information(self, 'Info', 'All files have already been translated.')
            return

        print(f'[Translation] Found {len(files_to_translate)} files to translate out of {len(files)} total')

        # Start translation with filtered files
        self._start_translation_worker(files_to_translate, target_lang, str(output_dir), input_base)

    def start_retranslate_all(self):
        """Re-translate all files, optionally clearing existing translations"""
        if not self.translation_engine:
            QMessageBox.warning(self, 'Warning', 'Please select a project first.')
            return

        # Get selected files
        files = []
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            self.collect_files(item, files)

        if not files:
            QMessageBox.warning(self, 'Warning', 'Please select files to translate.')
            return

        # Ask if user wants to clear existing translated files
        reply = QMessageBox.question(
            self, 'Clear Existing Translations?',
            'Do you want to delete all existing translated files before re-translating?\n\n'
            'Yes: Delete and re-translate all\n'
            'No: Overwrite existing translations',
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )

        if reply == QMessageBox.Cancel:
            return

        # Get target language and output directory
        target_lang = self.lang_combo.currentData()
        if self.config.custom_output_root and self.config.custom_output_root.strip():
            output_dir = Path(self.config.custom_output_root)
        else:
            app_dir = Path(__file__).parent.parent
            output_dir = app_dir / 'output'

        # Determine input base directory
        if self.file_tree.topLevelItemCount() > 0:
            first_item = self.file_tree.topLevelItem(0)
            input_base = first_item.data(0, Qt.UserRole)
            if input_base and Path(input_base).is_dir():
                input_base = str(Path(input_base).parent)
            elif input_base:
                input_base = str(Path(input_base).parent.parent)
            else:
                input_base = str(Path(files[0]).parent.parent)
        else:
            input_base = str(Path(files[0]).parent.parent)

        # Clear existing files if user chose Yes
        if reply == QMessageBox.Yes:
            output_lang_dir = output_dir / target_lang
            if output_lang_dir.exists():
                import shutil
                try:
                    shutil.rmtree(output_lang_dir)
                    print(f'[Translation] Cleared existing translations at {output_lang_dir}')
                except Exception as e:
                    QMessageBox.warning(self, 'Warning', f'Failed to clear existing files: {e}')

        # Start translation with all files
        print(f'[Translation] Re-translating all {len(files)} files')
        self._start_translation_worker(files, target_lang, str(output_dir), input_base, is_retranslate_all=True)

    def _start_translation_worker(self, files: List[str], target_lang: str, output_dir: str, input_base: str, is_retranslate_all: bool = False):
        """Common method to start translation worker (used by buttons)"""
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Reset retranslate count - this is button-based translation, not right-click
        self.retranslate_file_count = 0

        # Setup UI for translation
        self.btn_translate_rest.setEnabled(False)
        self.btn_retranslate_all.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_stop.setStyleSheet('background-color: #ff4444; color: white;')

        # Count total source files and already translated for accurate progress
        self.total_source_files, translated_count = self.count_source_and_translated_files()
        if is_retranslate_all:
            self.already_translated_count = 0  # Retranslating all, so start from 0
        else:
            self.already_translated_count = translated_count  # Count existing translations
        self.progress_bar.setMaximum(self.total_source_files)
        self.progress_bar.setValue(self.already_translated_count)

        # Mark translation as in progress and disable editing
        self.translation_in_progress = True
        self.translated_text.setReadOnly(True)
        self.translated_text.blockSignals(True)
        print('[UI] Translation started - disabled editing on translated preview')

        # Ensure current translation mode is set
        current_mode = self.mode_combo.currentData()
        self.translation_engine.set_translation_mode(current_mode)

        # Start worker
        self.translation_engine.reset_stop()
        print(f'[Translation] Starting with {self.config.worker_count} worker threads')
        self.worker = MultiThreadedTranslationWorker(
            self.translation_engine, files, target_lang, output_dir, input_base, self.config.worker_count,
            include_lang_folder=self.config.include_lang_code_folder,
            include_parent_folder=self.config.include_parent_folder
        )
        self.worker.progress.connect(self.on_translation_progress)
        self.worker.file_done.connect(self.on_file_translated)
        self.worker.error.connect(self.on_translation_error)
        self.worker.finished_all.connect(self.on_translation_finished)
        self.worker.start()

    def collect_files(self, item: QTreeWidgetItem, files: List[str]):
        """Recursively collect file paths from tree item"""
        path = item.data(0, Qt.UserRole)
        if path and Path(path).is_file():
            files.append(path)

        for i in range(item.childCount()):
            self.collect_files(item.child(i), files)

    def count_source_and_translated_files(self) -> tuple:
        """Count total source files and already translated files"""
        # Count all source files
        all_source_files = []
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            self.collect_files(item, all_source_files)

        total_source = len(all_source_files)

        # Count translated files
        translated_count = 0
        for file_path in all_source_files:
            if self._has_translated_file(file_path):
                translated_count += 1

        return total_source, translated_count

    def stop_translation(self):
        """Stop the translation process"""
        if self.worker:
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.btn_stop.setStyleSheet('')
            self.progress_label.setText('Stopping...')

            # Mark translation as stopped and re-enable editing
            self.translation_in_progress = False
            # Re-load current file to restore proper read-only state
            selected_items = self.file_tree.selectedItems()
            if selected_items:
                file_path = selected_items[0].data(0, Qt.UserRole)
                if file_path:
                    self.preview_file(file_path)
            print('[UI] Translation stopped - re-enabled editing on translated preview')

    @Slot(int, int, str)
    def on_translation_progress(self, current: int, _total: int, filename: str):
        """Handle translation progress update"""
        if self.retranslate_file_count > 0:
            # Right-click retranslate mode - show exact selected file count
            self.progress_bar.setValue(current)
            self.progress_label.setText(f'Re-translating: {Path(filename).name} ({current}/{self.retranslate_file_count})')
        else:
            # Normal translation mode (buttons) - show total progress
            actual_current = self.already_translated_count + current
            self.progress_bar.setValue(actual_current)
            self.progress_label.setText(f'Translating: {Path(filename).name} ({actual_current}/{self.total_source_files})')

    @Slot(object)
    def on_file_translated(self, result: TranslationResult):
        """Handle file translation complete"""
        print(f'[UI] File translated: {result.input_path}')

        # Add file to translated tree and update checkmark in source tree
        self.add_translated_file_to_tree(result.input_path)

        # Update preview and select file in tree if auto-refresh is enabled
        auto_refresh = self.chk_auto_refresh.isChecked()
        if DEBUG:
            print(f'[UI] Auto-refresh enabled: {auto_refresh}')

        if auto_refresh:
            if DEBUG:
                print(f'[UI] Updating preview for {Path(result.input_path).name}')
            self.original_text.setPlainText(result.original_html)
            self.translated_text.setPlainText(result.translated_html)

            # Auto-scroll to the completed file in tree
            self.select_file_in_tree(result.input_path)

    @Slot(str, str)
    def on_translation_error(self, filename: str, error: str):
        """Handle translation error"""
        self.status_label.setText(f'Error: {filename} - {error}')

    @Slot(dict)
    def on_translation_finished(self, stats: dict):
        """Handle translation complete"""
        self.btn_translate_rest.setEnabled(True)
        self.btn_retranslate_all.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet('')

        # Show completion message based on operation type
        if self.retranslate_file_count > 0:
            self.progress_label.setText(
                f"Re-translate complete! {self.retranslate_file_count} file(s): Success: {stats['success']}, Errors: {stats['errors']}"
            )
        else:
            self.progress_label.setText(
                f"Complete! Success: {stats['success']}, Errors: {stats['errors']}"
            )

        # Reset retranslate tracking
        self.retranslate_file_count = 0

        # Mark translation as complete and re-enable editing
        self.translation_in_progress = False
        # Re-load current file to restore proper read-only state
        selected_items = self.file_tree.selectedItems()
        if selected_items:
            file_path = selected_items[0].data(0, Qt.UserRole)
            if file_path:
                self.preview_file(file_path)
        print('[UI] Translation finished - re-enabled editing on translated preview')

    def new_project(self):
        """Create a new project"""
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, 'New Project', 'Project name:')
        if ok and name:
            try:
                self.project_manager.create_project(name)
                self.load_last_project()
                self.project_combo.setCurrentText(name)
                QMessageBox.information(self, 'Success', f'Project "{name}" created.')
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to create project: {e}')

    def delete_project(self):
        """Delete a project"""
        current = self.project_combo.currentText()
        if current in ['default']:
            QMessageBox.warning(self, 'Warning', 'Cannot delete system project.')
            return

        reply = QMessageBox.question(
            self, 'Confirm Delete',
            f'Delete project "{current}"? This cannot be undone.',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.project_manager.delete_project(current)
                self.load_last_project()
                QMessageBox.information(self, 'Success', f'Project "{current}" deleted.')
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to delete project: {e}')

    def get_glossary_folder(self) -> Path:
        """Get the glossary folder path (projects/{project_name}/glossary)"""
        if not self.current_project or not self.project_manager.current_project_path:
            return None
        glossary_dir = self.project_manager.current_project_path / 'glossary'
        glossary_dir.mkdir(exist_ok=True)
        return glossary_dir

    def populate_glossary_combo(self):
        """Populate the glossary dropdown with available glossary files"""
        self.glossary_combo.blockSignals(True)
        self.glossary_combo.clear()

        glossary_dir = self.get_glossary_folder()
        if not glossary_dir:
            self.glossary_combo.blockSignals(False)
            return

        # Add empty option
        self.glossary_combo.addItem('(None)', None)

        # Find all JSON files in the glossary folder
        glossary_files = sorted(glossary_dir.glob('*.json'))
        for glossary_file in glossary_files:
            # Show filename without extension
            display_name = glossary_file.stem
            self.glossary_combo.addItem(display_name, str(glossary_file))

        # Restore the previously selected glossary
        selected_index = 0  # Default to "(None)"
        if self.current_project:
            selected_filename = getattr(self.current_project.settings, 'selected_glossary', '')
            if selected_filename:
                # Find the matching glossary in the combo box
                for i in range(1, self.glossary_combo.count()):
                    glossary_path = self.glossary_combo.itemData(i)
                    if glossary_path and Path(glossary_path).name == selected_filename:
                        selected_index = i
                        break

        if selected_index == 0 and self.glossary_combo.count() > 1:
            # No saved selection or not found, auto-select first glossary
            selected_index = 1

        # Set the selection before unblocking signals
        self.glossary_combo.setCurrentIndex(selected_index)

        self.glossary_combo.blockSignals(False)

        # Manually trigger selection to load the glossary
        if selected_index > 0:
            self.on_glossary_selected(selected_index)

    def on_glossary_selected(self, _index: int):
        """Handle glossary selection from dropdown"""
        if not self.current_project:
            return

        glossary_path = self.glossary_combo.currentData()
        if not glossary_path:
            # None selected - clear glossary
            return

        try:
            # Validate the file is valid JSON
            with open(glossary_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                QMessageBox.warning(self, 'Warning', 'Invalid glossary format.')
                return

            # Store the selected glossary path
            self.current_glossary_path = glossary_path

            # Save the selected glossary filename to project settings
            glossary_filename = Path(glossary_path).name
            if self.current_project:
                self.current_project.settings.selected_glossary = glossary_filename
                self.project_manager.save_current_project()

            # Reload glossary with the selected path
            if self.translation_engine:
                self.translation_engine.reload_glossary(glossary_path)

            term_count = len(data)
            self.status_label.setText(f'Glossary loaded: {term_count:,} terms')
            self.glossary_label.setText(f'{term_count:,} terms')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load glossary: {e}')

    def edit_glossary(self):
        """Open glossary editor"""
        if not self.current_project:
            QMessageBox.warning(self, 'Warning', 'Please select a project first.')
            return

        glossary_path = self.current_glossary_path
        if not glossary_path or not Path(glossary_path).exists():
            QMessageBox.warning(self, 'Warning', 'Please select a glossary file first.')
            return

        editor = GlossaryEditor(glossary_path, self, case_sensitive=self.config.case_sensitive_glossary)
        editor.glossary_changed.connect(self.on_glossary_changed)
        editor.exec()

    def on_glossary_changed(self):
        """Handle glossary changes - reload in translation engine"""
        if self.translation_engine and self.current_glossary_path:
            self.translation_engine.reload_glossary(self.current_glossary_path)

        # Update glossary term count in UI
        if self.current_glossary_path and Path(self.current_glossary_path).exists():
            try:
                with open(self.current_glossary_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    count = len(data) if isinstance(data, dict) else 0
                    self.glossary_label.setText(f'{count:,} terms')
            except:
                pass

    def add_to_glossary(self, original: str, translated: str):
        """Add a term to the current glossary"""
        if not self.current_project:
            QMessageBox.warning(self, 'Warning', 'Please select a project first.')
            return

        glossary_path = self.current_glossary_path
        if not glossary_path or not Path(glossary_path).exists():
            QMessageBox.warning(self, 'Warning', 'Please select a glossary file first.')
            return

        try:
            # Load existing glossary
            if Path(glossary_path).exists():
                with open(glossary_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}

            # Add the new term
            original = original.strip()
            translated = translated.strip()

            if original in data:
                # Ask if user wants to overwrite
                reply = QMessageBox.question(
                    self, 'Term Exists',
                    f'"{original}" already exists in glossary.\n\nCurrent: {data[original]}\nNew: {translated}\n\nOverwrite?',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            data[original] = translated

            # Save glossary
            with open(glossary_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Reload glossary
            self.on_glossary_changed()

            self.status_label.setText(f'Added to glossary: {original} → {translated}')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to add to glossary: {e}')

    def on_case_sensitive_changed(self, state: int):
        """Handle case sensitivity toggle"""
        case_sensitive = state == 2  # Qt.Checked = 2
        self.config.case_sensitive_glossary = case_sensitive
        self.config.save()

        if self.translation_engine:
            self.translation_engine.set_case_sensitive_glossary(case_sensitive)

        mode = 'case-sensitive' if case_sensitive else 'case-insensitive'
        self.status_label.setText(f'Glossary matching: {mode}')

    def on_translation_mode_changed(self, _index: int):
        """Handle translation mode change"""
        mode = self.mode_combo.currentData()
        self.config.translation_mode = mode
        # Keep backward compatibility
        self.config.direct_translate_mode = (mode == 'full_context')
        self.config.save()

        if self.translation_engine:
            self.translation_engine.set_translation_mode(mode)

        mode_names = {'glossary_reference': 'Glossary Reference', 'glossary_placeholder': 'Glossary Placeholder', 'full_context': 'Full Context Reference'}
        self.status_label.setText(f'Translation mode: {mode_names.get(mode, mode)}')

    def on_auto_refresh_changed(self, state: int):
        """Handle auto-refresh preview toggle"""
        auto_refresh = state == 2  # Qt.Checked = 2
        self.config.auto_refresh_preview = auto_refresh
        self.config.save()

    def on_target_lang_changed(self, index: int):
        """Handle target language selection change"""
        target_lang = self.lang_combo.currentData()
        if target_lang:
            print(f'[Config] Target language changed to: {target_lang}')
            self.config.target_lang = target_lang
            self.config.save()
            self.status_label.setText(f'Target language: {SUPPORTED_LANGUAGES.get(target_lang, target_lang)}')
            # Repopulate translated tree for new language
            self.populate_translated_tree()

    def on_worker_count_changed(self, value: int):
        """Handle worker count change"""
        print(f'[Config] Worker count changed to: {value}')
        self.config.worker_count = value
        self.config.save()
        self.status_label.setText(f'Worker threads: {value}')

    def on_translated_text_changed(self):
        """Handle changes to the translated text editor"""
        if not self.current_translated_path:
            return
        if not self.translated_modified:
            self.translated_modified = True
            self.update_translated_label()

    def update_translated_label(self):
        """Update the translated label to show modification status"""
        if self.translated_modified:
            self.translated_label.setText('Translated *')
            self.translated_label.setStyleSheet('font-weight: bold; color: #e67e22;')
        else:
            self.translated_label.setText('Translated')
            self.translated_label.setStyleSheet('font-weight: bold;')

    def save_translated_file(self):
        """Save the edited translated file"""
        if not self.current_translated_path:
            self.status_label.setText('No file to save')
            return

        try:
            # Ensure directory exists
            Path(self.current_translated_path).parent.mkdir(parents=True, exist_ok=True)

            # Save content
            content = self.translated_text.toPlainText()
            with open(self.current_translated_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.translated_modified = False
            self.update_translated_label()
            self.status_label.setText(f'Saved: {Path(self.current_translated_path).name}')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save file: {e}')

    def find_in_translated(self):
        """Find text in the translated file (from bottom search bar)"""
        search_text = self.search_field.text()
        if not search_text:
            self.status_label.setText('Enter search text')
            return

        # Get current cursor position to search from
        cursor = self.translated_text.textCursor()

        # Search from current position
        found = self.translated_text.find(search_text)

        if not found:
            # Wrap around to beginning
            cursor.movePosition(cursor.MoveOperation.Start)
            self.translated_text.setTextCursor(cursor)
            found = self.translated_text.find(search_text)

            if not found:
                self.status_label.setText(f'"{search_text}" not found')
                return
            else:
                self.status_label.setText(f'Wrapped to beginning')
        else:
            self.status_label.setText(f'Found: "{search_text}"')

    def replace_in_translated(self):
        """Replace current selection in translated file"""
        search_text = self.search_field.text()
        replace_text = self.replace_field.text()

        if not search_text:
            self.status_label.setText('Enter search text')
            return

        cursor = self.translated_text.textCursor()

        # Check if current selection matches search text
        if cursor.hasSelection() and cursor.selectedText() == search_text:
            # Replace the selection
            cursor.insertText(replace_text)
            self.status_label.setText(f'Replaced 1 occurrence')
            # Find next
            self.find_in_translated()
        else:
            # Find first
            self.find_in_translated()

    def replace_all_in_translated(self):
        """Replace all occurrences in current translated file"""
        search_text = self.search_field.text()
        replace_text = self.replace_field.text()

        if not search_text:
            self.status_label.setText('Enter search text')
            return

        content = self.translated_text.toPlainText()
        count = content.count(search_text)

        if count == 0:
            self.status_label.setText(f'"{search_text}" not found')
            return

        new_content = content.replace(search_text, replace_text)

        # Block signals to avoid triggering textChanged multiple times
        self.translated_text.blockSignals(True)
        self.translated_text.setPlainText(new_content)
        self.translated_text.blockSignals(False)

        # Mark as modified
        self.translated_modified = True
        self.update_translated_label()

        self.status_label.setText(f'Replaced {count} occurrences')

    def replace_in_all_files(self):
        """Replace in all translated files"""
        search_text = self.search_field.text()
        replace_text = self.replace_field.text()

        if not search_text:
            self.status_label.setText('Enter search text')
            return

        # Get output directory using settings
        target_lang = self.lang_combo.currentData()
        output_dir = self.get_output_directory(target_lang, include_source_folder=False)

        if not output_dir.exists():
            self.status_label.setText('No translated files found')
            return

        # Confirm action
        reply = QMessageBox.question(
            self, 'Confirm Replace All',
            f'Replace "{search_text}" with "{replace_text}" in all translated files?\n\n'
            f'This will modify all .htm and .html files in:\n{output_dir}',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Save current file first if modified
        if self.translated_modified and self.current_translated_path:
            self.save_translated_file()

        # Find all translated files
        translated_files = list(output_dir.rglob('*.htm')) + list(output_dir.rglob('*.html'))

        total_count = 0
        files_modified = 0

        for file_path in translated_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                count = content.count(search_text)
                if count > 0:
                    new_content = content.replace(search_text, replace_text)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    total_count += count
                    files_modified += 1
            except Exception as e:
                self.status_label.setText(f'Error in {file_path.name}: {e}')
                continue

        self.status_label.setText(f'Replaced {total_count} occurrences in {files_modified} files')

        # Reload current file if it was modified
        if self.current_translated_path and Path(self.current_translated_path).exists():
            self.translated_text.blockSignals(True)
            with open(self.current_translated_path, 'r', encoding='utf-8') as f:
                self.translated_text.setPlainText(f.read())
            self.translated_text.blockSignals(False)
            self.translated_modified = False
            self.update_translated_label()

    def find_in_all_original_files(self):
        """Find search text in all original/source files and show results"""
        search_text = self.original_search_field.text()
        if not search_text:
            self.status_label.setText('Enter search text for original files')
            return

        # Get all source files from the tree
        source_files = []

        def collect_files(parent_item):
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                file_path = item.data(0, Qt.UserRole)
                if file_path and Path(file_path).is_file():
                    source_files.append(Path(file_path))
                collect_files(item)

        collect_files(self.file_tree.invisibleRootItem())

        if not source_files:
            self.status_label.setText('No source files found')
            self.search_results_list.clear()
            self.search_results_label.setText('Search Results (0)')
            return

        # Clear previous results
        self.search_results_list.clear()

        total_matches = 0
        files_with_matches = 0

        # Get base directory for relative paths
        if source_files:
            base_dir = source_files[0].parent
            while base_dir.parent != base_dir:
                if all(f.is_relative_to(base_dir) for f in source_files):
                    break
                base_dir = base_dir.parent

        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                file_matches = 0
                for line_num, line in enumerate(lines, 1):
                    if search_text in line:
                        file_matches += 1
                        total_matches += 1

                        # Get relative path for display
                        try:
                            rel_path = file_path.relative_to(base_dir)
                        except ValueError:
                            rel_path = file_path.name

                        # Create list item with file path and line preview
                        preview = line.strip()[:80]
                        if len(line.strip()) > 80:
                            preview += '...'

                        item = QListWidgetItem(f'[Source] {rel_path}:{line_num}  {preview}')
                        item.setData(Qt.UserRole, {
                            'file_path': str(file_path),
                            'line_num': line_num,
                            'search_text': search_text,
                            'is_original': True
                        })
                        self.search_results_list.addItem(item)

                if file_matches > 0:
                    files_with_matches += 1

            except Exception as e:
                continue

        self.search_results_label.setText(f'Search Results ({total_matches} matches in {files_with_matches} source files)')
        self.status_label.setText(f'Found {total_matches} matches in {files_with_matches} source files')

    def find_in_all_files(self):
        """Find search text in all translated files and show results"""
        search_text = self.search_field.text()
        if not search_text:
            self.status_label.setText('Enter search text')
            return

        # Get output directory using settings
        target_lang = self.lang_combo.currentData()
        output_dir = self.get_output_directory(target_lang, include_source_folder=False)

        if not output_dir.exists():
            self.status_label.setText('No translated files found')
            self.search_results_list.clear()
            self.search_results_label.setText('Search Results (0)')
            return

        # Clear previous results
        self.search_results_list.clear()

        # Find all translated files
        translated_files = list(output_dir.rglob('*.htm')) + list(output_dir.rglob('*.html'))

        total_matches = 0
        files_with_matches = 0

        for file_path in translated_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                file_matches = 0
                for line_num, line in enumerate(lines, 1):
                    if search_text in line:
                        file_matches += 1
                        total_matches += 1

                        # Get relative path for display
                        try:
                            rel_path = file_path.relative_to(output_dir)
                        except ValueError:
                            rel_path = file_path.name

                        # Create list item with file path and line preview
                        preview = line.strip()[:80]
                        if len(line.strip()) > 80:
                            preview += '...'

                        item = QListWidgetItem(f'[Translated] {rel_path}:{line_num}  {preview}')
                        item.setData(Qt.UserRole, {
                            'file_path': str(file_path),
                            'line_num': line_num,
                            'search_text': search_text,
                            'is_original': False
                        })
                        self.search_results_list.addItem(item)

                if file_matches > 0:
                    files_with_matches += 1

            except Exception as e:
                continue

        self.search_results_label.setText(f'Search Results ({total_matches} matches in {files_with_matches} translated files)')
        self.status_label.setText(f'Found {total_matches} matches in {files_with_matches} translated files')

    def on_search_result_clicked(self, item: QListWidgetItem):
        """Handle click on search result - open file and go to line"""
        data = item.data(Qt.UserRole)
        if not data:
            return

        file_path = data['file_path']
        line_num = data['line_num']
        search_text = data['search_text']
        is_original = data.get('is_original', False)

        try:
            # Load the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if is_original:
                # This is an original/source file - load into original text editor
                self.original_text.setPlainText(content)

                # Go to the specific line in original
                cursor = self.original_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                for _ in range(line_num - 1):
                    cursor.movePosition(cursor.MoveOperation.Down)
                cursor.movePosition(cursor.MoveOperation.StartOfLine)
                self.original_text.setTextCursor(cursor)

                # Find and highlight the search text in red
                self.highlight_search_text(self.original_text, search_text)

                # Select in source tree
                self.select_file_in_tree(file_path)

                # Try to load corresponding translated file
                target_lang = self.lang_combo.currentData()
                output_dir = self.get_output_directory(target_lang, include_source_folder=True)

                if self.file_tree.topLevelItemCount() > 0:
                    first_item = self.file_tree.topLevelItem(0)
                    input_base = first_item.data(0, Qt.UserRole)
                    if input_base:
                        input_base_path = Path(input_base)
                        if input_base_path.is_dir():
                            try:
                                rel_path = Path(file_path).relative_to(input_base_path)
                                translated_path = output_dir / rel_path

                                if translated_path.exists():
                                    with open(translated_path, 'r', encoding='utf-8') as f:
                                        self.translated_text.blockSignals(True)
                                        self.translated_text.setPlainText(f.read())
                                        self.translated_text.blockSignals(False)
                                        self.current_translated_path = str(translated_path)
                                        self.translated_modified = False
                                        self.update_translated_label()
                            except Exception:
                                pass

                self.status_label.setText(f'Opened source: {Path(file_path).name}:{line_num}')

            else:
                # This is a translated file - load into translated text editor
                # Auto-save current file if modified
                if self.translated_modified and self.current_translated_path:
                    self.save_translated_file()

                self.translated_text.blockSignals(True)
                self.translated_text.setPlainText(content)
                self.translated_text.blockSignals(False)

                self.current_translated_path = file_path
                self.translated_modified = False
                self.update_translated_label()

                # Find the corresponding original file and display it
                target_lang = self.lang_combo.currentData()
                output_dir = self.get_output_directory(target_lang, include_source_folder=True)

                try:
                    rel_path = Path(file_path).relative_to(output_dir)
                    if self.file_tree.topLevelItemCount() > 0:
                        first_item = self.file_tree.topLevelItem(0)
                        input_base = first_item.data(0, Qt.UserRole)
                        if input_base:
                            input_base_path = Path(input_base)
                            if input_base_path.is_dir():
                                # output_dir includes parent folder, so rel_path is from input_base
                                original_path = input_base_path / rel_path
                            else:
                                original_path = input_base_path.parent / rel_path

                            if original_path.exists():
                                with open(original_path, 'r', encoding='utf-8') as f:
                                    self.original_text.setPlainText(f.read())
                                self.select_file_in_tree(str(original_path))
                except Exception:
                    pass  # Keep current original text if we can't find the file

                # Go to the specific line in translated
                cursor = self.translated_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                for _ in range(line_num - 1):
                    cursor.movePosition(cursor.MoveOperation.Down)
                cursor.movePosition(cursor.MoveOperation.StartOfLine)
                self.translated_text.setTextCursor(cursor)

                # Find and highlight the search text in red
                self.highlight_search_text(self.translated_text, search_text)

                self.status_label.setText(f'Opened translated: {Path(file_path).name}:{line_num}')

        except Exception as e:
            self.status_label.setText(f'Error opening file: {e}')

    def highlight_search_text(self, text_edit, search_text: str):
        """Highlight search text in red in the text editor"""
        # First find the text to position cursor
        if not text_edit.find(search_text):
            return

        # Get current cursor with selection
        cursor = text_edit.textCursor()

        # Create extra selection with red background
        from PySide6.QtWidgets import QTextEdit
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(255, 100, 100))  # Light red background
        selection.format.setForeground(QColor(0, 0, 0))  # Black text
        selection.cursor = cursor

        # Apply the extra selection
        text_edit.setExtraSelections([selection])

        # Clear the regular selection so only the red highlight shows
        cursor.clearSelection()
        text_edit.setTextCursor(cursor)

    def select_file_in_tree(self, file_path: str) -> bool:
        """Find and select a file in the source tree. Returns True if found."""
        file_path_obj = Path(file_path)

        def search_tree_items(parent_item, depth=0):
            """Recursively search tree items"""
            if depth > 10:  # Prevent infinite recursion
                return False

            count = parent_item.childCount() if hasattr(parent_item, 'childCount') else self.file_tree.topLevelItemCount()

            for i in range(count):
                item = parent_item.child(i) if hasattr(parent_item, 'child') else self.file_tree.topLevelItem(i)
                item_path = item.data(0, Qt.UserRole)

                if item_path:
                    item_path_obj = Path(item_path)
                    # Check if paths match
                    if item_path_obj == file_path_obj or item_path_obj.resolve() == file_path_obj.resolve():
                        # Found it! Select and scroll to it
                        self.file_tree.setCurrentItem(item)
                        self.file_tree.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                        return True

                # Search children recursively
                if item.childCount() > 0:
                    if search_tree_items(item, depth + 1):
                        return True

            return False

        # Start search from root
        return search_tree_items(self.file_tree)


    def show_output_settings(self):
        """Show output settings dialog"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                                        QCheckBox, QDialogButtonBox, QLabel, QPushButton)

        dialog = QDialog(self)
        dialog.setWindowTitle('Output Settings')
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)

        # Custom output root group
        root_group = QGroupBox('Custom Output Root Folder')
        root_layout = QVBoxLayout(root_group)

        # Show current custom root
        if self.config.custom_output_root and self.config.custom_output_root.strip():
            root_info = QLabel(f'Current: {self.config.custom_output_root}')
            root_info.setWordWrap(True)
            root_info.setStyleSheet('color: #2196F3; padding: 5px;')
        else:
            root_info = QLabel('Using default output folder')
            root_info.setStyleSheet('color: #666; padding: 5px;')

        root_layout.addWidget(root_info)

        # Buttons for custom root
        root_btn_layout = QHBoxLayout()

        # Select folder button
        select_root_btn = QPushButton('Select Folder...')

        def select_custom_root():
            current = self.config.custom_output_root if self.config.custom_output_root else str(Path(__file__).parent.parent / 'output')
            selected_dir = QFileDialog.getExistingDirectory(
                dialog,
                'Select Custom Output Root Folder',
                current,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if selected_dir:
                self.config.custom_output_root = selected_dir
                self.config.save()
                root_info.setText(f'Current: {selected_dir}')
                root_info.setStyleSheet('color: #2196F3; padding: 5px;')
                reset_root_btn.setEnabled(True)

        select_root_btn.clicked.connect(select_custom_root)
        root_btn_layout.addWidget(select_root_btn)

        # Reset button
        reset_root_btn = QPushButton('Reset to Default')
        reset_root_btn.setEnabled(bool(self.config.custom_output_root and self.config.custom_output_root.strip()))

        def reset_custom_root():
            self.config.custom_output_root = ''
            self.config.save()
            root_info.setText('Using default output folder')
            root_info.setStyleSheet('color: #666; padding: 5px;')
            reset_root_btn.setEnabled(False)

        reset_root_btn.clicked.connect(reset_custom_root)
        root_btn_layout.addWidget(reset_root_btn)

        root_btn_layout.addStretch()
        root_layout.addLayout(root_btn_layout)

        layout.addWidget(root_group)

        # Output folder structure group
        output_group = QGroupBox('Output Folder Structure')
        output_layout = QVBoxLayout(output_group)

        # Include parent folder checkbox
        parent_folder_check = QCheckBox('Include Parent Folder')
        parent_folder_check.setChecked(self.config.include_parent_folder)
        parent_folder_check.setToolTip(
            'When enabled: {root}/{lang_code}/{parent_folder}/file.html\n'
            'When disabled: {root}/{lang_code}/file.html'
        )
        output_layout.addWidget(parent_folder_check)

        # Include language code folder checkbox
        lang_folder_check = QCheckBox('Include Language Code Folder')
        lang_folder_check.setChecked(self.config.include_lang_code_folder)
        lang_folder_check.setToolTip(
            'When enabled: {root}/{lang_code}/{parent_folder}/file.html\n'
            'When disabled: {root}/{parent_folder}/file.html'
        )
        output_layout.addWidget(lang_folder_check)

        layout.addWidget(output_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Show dialog
        if dialog.exec() == QDialog.Accepted:
            # Save settings
            self.config.include_parent_folder = parent_folder_check.isChecked()
            self.config.include_lang_code_folder = lang_folder_check.isChecked()
            self.config.save()

            self.status_label.setText('Output settings saved')

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, 'About HTML Translator',
            'HTML Translation App\n\n'
            'Translate HTML files using local Ollama AI.\n\n'
            'Features:\n'
            '- Project-based glossary and cache\n'
            '- Side-by-side preview\n'
            '- Batch translation'
        )

    def closeEvent(self, event):
        """Handle window close"""
        # Auto-save modified translation
        if self.translated_modified and self.current_translated_path:
            self.save_translated_file()

        # Save window geometry
        self.config.window_width = self.width()
        self.config.window_height = self.height()

        # Save splitter sizes (find the main splitter)
        if hasattr(self, 'main_splitter'):
            self.config.splitter_sizes = self.main_splitter.sizes()

        # Save configuration
        self.config.save()

        # Stop translation worker if running
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        event.accept()
