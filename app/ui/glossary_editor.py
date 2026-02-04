"""
Glossary Editor Dialog
Allows viewing, searching, adding, editing, and deleting glossary terms
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QLabel, QHeaderView, QMessageBox,
    QWidget, QAbstractItemView, QGroupBox, QFormLayout, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from pathlib import Path
import json


class GlossaryEditor(QDialog):
    """Dialog for editing glossary terms"""

    glossary_changed = Signal()  # Emitted when glossary is modified

    def __init__(self, glossary_path: str, parent=None, case_sensitive: bool = True):
        super().__init__(parent)
        self.glossary_path = Path(glossary_path)
        self.terms = {}  # {term: translation}
        self.filtered_terms = []  # List of (term, translation) for display
        self.case_sensitive = case_sensitive

        self.setWindowTitle("Glossary Editor")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        self.load_glossary()

    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)

        # Stats label
        self.stats_label = QLabel("Loading...")
        self.stats_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(self.stats_label)

        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter terms (English or Chinese)...")
        self.search_input.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_input)

        self.clear_search_btn = QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self.clear_search)
        search_layout.addWidget(self.clear_search_btn)
        layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["English Term", "Chinese Translation"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Add new term section
        add_group = QGroupBox("Add New Term")
        add_layout = QHBoxLayout(add_group)

        self.new_term_input = QLineEdit()
        self.new_term_input.setPlaceholderText("English term")
        add_layout.addWidget(self.new_term_input)

        self.new_translation_input = QLineEdit()
        self.new_translation_input.setPlaceholderText("Chinese translation")
        add_layout.addWidget(self.new_translation_input)

        self.add_btn = QPushButton("Add Term")
        self.add_btn.clicked.connect(self.add_term)
        add_layout.addWidget(self.add_btn)

        layout.addWidget(add_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        button_layout.addWidget(self.delete_btn)

        self.import_btn = QPushButton("Import...")
        self.import_btn.clicked.connect(self.import_glossary)
        button_layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export...")
        self.export_btn.clicked.connect(self.export_glossary)
        button_layout.addWidget(self.export_btn)

        self.remove_duplicates_btn = QPushButton("Remove Duplicates")
        self.remove_duplicates_btn.clicked.connect(self.remove_duplicates)
        button_layout.addWidget(self.remove_duplicates_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        # Debounce timer for search
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.apply_filter)

    def load_glossary(self):
        """Load glossary from JSON file"""
        if self.glossary_path.exists():
            try:
                with open(self.glossary_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Support both old format (with "terms" wrapper) and new format
                    if isinstance(data, dict):
                        if 'terms' in data:
                            old_terms = data['terms']
                            self.terms = {}
                            for term, translations in old_terms.items():
                                if isinstance(translations, dict):
                                    translation = translations.get('zh') or translations.get('zh-TW') or list(translations.values())[0]
                                    self.terms[term] = translation
                                else:
                                    self.terms[term] = translations
                        else:
                            self.terms = data

                self.update_stats()
                self.apply_filter()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load glossary: {e}")
                self.terms = {}
        else:
            QMessageBox.warning(self, "Warning", f"Glossary file not found: {self.glossary_path}")
            self.terms = {}

    def update_stats(self):
        """Update the stats label"""
        total = len(self.terms)
        showing = len(self.filtered_terms)
        if self.search_input.text():
            self.stats_label.setText(f"Showing {showing:,} of {total:,} terms")
        else:
            self.stats_label.setText(f"Total: {total:,} terms")

    def on_search_changed(self, text):
        """Handle search input change with debouncing"""
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms debounce

    def clear_search(self):
        """Clear search and show all terms"""
        self.search_input.clear()
        self.apply_filter()

    def apply_filter(self):
        """Apply search filter to terms"""
        search_text = self.search_input.text().lower().strip()

        # Block signals while updating table
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        if search_text:
            # Filter terms
            self.filtered_terms = [
                (term, trans) for term, trans in self.terms.items()
                if search_text in term.lower() or search_text in trans.lower()
            ]
        else:
            # Show first 1000 terms when no search (for performance)
            items = list(self.terms.items())[:1000]
            self.filtered_terms = items

        # Populate table
        self.table.setRowCount(len(self.filtered_terms))
        for row, (term, translation) in enumerate(self.filtered_terms):
            term_item = QTableWidgetItem(term)
            trans_item = QTableWidgetItem(translation)

            # Store original term for tracking edits
            term_item.setData(Qt.UserRole, term)

            self.table.setItem(row, 0, term_item)
            self.table.setItem(row, 1, trans_item)

        self.table.blockSignals(False)
        self.update_stats()

    def on_item_changed(self, item):
        """Handle item edit in table"""
        row = item.row()
        col = item.column()

        if row >= len(self.filtered_terms):
            return

        original_term = self.table.item(row, 0).data(Qt.UserRole)

        if col == 0:
            # Term changed
            new_term = item.text().strip()
            if new_term and new_term != original_term:
                # Rename term
                if new_term in self.terms and new_term != original_term:
                    QMessageBox.warning(self, "Warning", f"Term '{new_term}' already exists!")
                    item.setText(original_term)
                    return

                translation = self.terms.pop(original_term)
                self.terms[new_term] = translation
                item.setData(Qt.UserRole, new_term)
                self.auto_save()

        else:
            # Translation changed
            new_translation = item.text().strip()
            if original_term in self.terms:
                self.terms[original_term] = new_translation
                self.auto_save()

        self.update_stats()

    def add_term(self):
        """Add a new term"""
        term = self.new_term_input.text().strip()
        translation = self.new_translation_input.text().strip()

        if not term:
            QMessageBox.warning(self, "Warning", "Please enter an English term")
            self.new_term_input.setFocus()
            return

        if not translation:
            QMessageBox.warning(self, "Warning", "Please enter a Chinese translation")
            self.new_translation_input.setFocus()
            return

        if term in self.terms:
            result = QMessageBox.question(
                self, "Confirm",
                f"Term '{term}' already exists with translation '{self.terms[term]}'.\n"
                f"Do you want to update it to '{translation}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if result != QMessageBox.Yes:
                return

        self.terms[term] = translation

        # Clear inputs
        self.new_term_input.clear()
        self.new_translation_input.clear()
        self.new_term_input.setFocus()

        # Refresh display
        self.search_input.setText(term)
        self.apply_filter()

        # Auto-save
        self.auto_save()

    def delete_selected(self):
        """Delete the selected term"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a term to delete")
            return

        term_item = self.table.item(current_row, 0)
        if not term_item:
            return

        term = term_item.data(Qt.UserRole) or term_item.text()

        result = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the term '{term}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if result == QMessageBox.Yes:
            if term in self.terms:
                del self.terms[term]
                self.apply_filter()
                self.auto_save()

    def save_glossary(self):
        """Save glossary to file"""
        try:
            with open(self.glossary_path, 'w', encoding='utf-8') as f:
                json.dump(self.terms, f, ensure_ascii=False, indent=2)

            self.update_stats()
            self.glossary_changed.emit()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save glossary: {e}")

    def auto_save(self):
        """Auto-save glossary after any change"""
        self.save_glossary()

    def import_glossary(self):
        """Import glossary from another JSON file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Glossary",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Parse imported data - support multiple formats
            imported_terms = {}

            if isinstance(data, dict):
                if 'terms' in data:
                    # Old format with "terms" wrapper
                    old_terms = data['terms']
                    for term, translations in old_terms.items():
                        if isinstance(translations, dict):
                            # Format: {term: {zh: translation}}
                            translation = translations.get('zh') or translations.get('zh-TW') or list(translations.values())[0]
                            imported_terms[term] = translation
                        else:
                            imported_terms[term] = translations
                else:
                    # New format: {term: translation} directly
                    for term, translation in data.items():
                        if isinstance(translation, dict):
                            # Nested translation format
                            trans = translation.get('zh') or translation.get('zh-TW') or list(translation.values())[0]
                            imported_terms[term] = trans
                        else:
                            imported_terms[term] = translation

            if not imported_terms:
                QMessageBox.warning(self, "Warning", "No terms found in the imported file")
                return

            # Check for duplicates
            duplicates = set(imported_terms.keys()) & set(self.terms.keys())
            new_terms = set(imported_terms.keys()) - set(self.terms.keys())

            # Ask user how to handle import
            if duplicates:
                result = QMessageBox.question(
                    self, "Import Options",
                    f"Found {len(imported_terms):,} terms to import:\n"
                    f"- {len(new_terms):,} new terms\n"
                    f"- {len(duplicates):,} duplicates\n\n"
                    f"Do you want to overwrite existing terms with duplicates?\n"
                    f"(Click 'No' to only import new terms)",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )

                if result == QMessageBox.Cancel:
                    return
                elif result == QMessageBox.Yes:
                    # Import all terms (overwrite duplicates)
                    self.terms.update(imported_terms)
                    imported_count = len(imported_terms)
                else:
                    # Import only new terms
                    for term, translation in imported_terms.items():
                        if term not in self.terms:
                            self.terms[term] = translation
                    imported_count = len(new_terms)
            else:
                # No duplicates, import all
                self.terms.update(imported_terms)
                imported_count = len(imported_terms)

            self.apply_filter()
            self.auto_save()

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Error", f"Invalid JSON file: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import glossary: {e}")

    def export_glossary(self):
        """Export glossary to a JSON file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Glossary",
            str(Path.home() / "glossary_export.json"),
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.terms, f, ensure_ascii=False, indent=2)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export glossary: {e}")

    def _term_priority(self, term: str) -> int:
        """
        Calculate priority for a term when removing duplicates.
        Higher priority = preferred to keep.
        Priority: ALL UPPERCASE (2) > First char uppercase (1) > lowercase (0)
        """
        if term.isupper():
            return 2
        elif term and term[0].isupper():
            return 1
        return 0

    def remove_duplicates(self):
        """Remove duplicate glossary entries (case-insensitive, keeps uppercase/capitalized)"""
        if not self.terms:
            QMessageBox.warning(self, "Warning", "No glossary terms loaded.")
            return

        original_count = len(self.terms)

        # Remove duplicates using case-insensitive comparison
        # Prefer keeping: ALL UPPERCASE > First char uppercase > lowercase
        unique_terms = {}

        for english_term, translation in self.terms.items():
            # Always use lowercase key for case-insensitive comparison
            key = english_term.lower()

            if key not in unique_terms:
                # First occurrence
                unique_terms[key] = (english_term, translation)
            else:
                # Compare priority: keep the one with higher priority (uppercase preferred)
                existing_term, existing_translation = unique_terms[key]
                if self._term_priority(english_term) > self._term_priority(existing_term):
                    unique_terms[key] = (english_term, translation)

        # Rebuild glossary with unique terms (preserve preferred casing)
        new_glossary = {original_term: translation for original_term, translation in unique_terms.values()}

        duplicates_removed = original_count - len(new_glossary)

        if duplicates_removed == 0:
            QMessageBox.information(self, "No Duplicates", "No duplicate entries found.")
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Confirm Remove Duplicates",
            f"Found {duplicates_removed} duplicate(s).\n"
            f"Original: {original_count:,} terms\n"
            f"After cleanup: {len(new_glossary):,} terms\n\n"
            f"(Case-insensitive, keeps uppercase/capitalized terms)\n\n"
            f"Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.terms = new_glossary
            self.apply_filter()
            self.auto_save()
