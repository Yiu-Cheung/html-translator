"""
Application Configuration
Manages app settings and persistence
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class OllamaConfig:
    """Ollama connection settings"""
    host: str = 'localhost'
    port: int = 11434
    model: str = 'gemma3:4b'
    timeout: int = 60

    @property
    def base_url(self) -> str:
        return f'http://{self.host}:{self.port}'


@dataclass
class AppConfig:
    """Main application configuration - UI and global settings only"""
    # UI settings
    window_width: int = 1400
    window_height: int = 900
    splitter_sizes: list = field(default_factory=lambda: [300, 1100])

    # Paths
    app_dir: str = ''
    projects_dir: str = ''
    last_project: str = 'default'

    # Recent projects
    recent_projects: list = field(default_factory=list)

    def __post_init__(self):
        # Always compute app_dir relative to this file (cross-platform)
        computed_app_dir = str(Path(__file__).parent.parent)

        # Validate app_dir - use computed if empty or invalid
        if not self.app_dir or not Path(self.app_dir).exists():
            self.app_dir = computed_app_dir

        # Validate projects_dir - use computed if empty or invalid
        computed_projects_dir = str(Path(self.app_dir) / 'projects')
        if not self.projects_dir or not Path(self.projects_dir).exists():
            self.projects_dir = computed_projects_dir

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'AppConfig':
        """Load configuration from JSON file"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config.json'
        else:
            config_path = Path(config_path)

        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Remove project-specific fields that have been moved to ProjectSettings
                # These are now handled per-project
                removed_fields = [
                    'ollama', 'source_lang', 'target_lang',
                    'case_sensitive_glossary', 'translation_mode', 'direct_translate_mode',
                    'auto_refresh_preview', 'worker_count',
                    'include_parent_folder', 'include_lang_code_folder', 'custom_output_root',
                    'last_input_dir', 'last_output_dir'
                ]
                for field in removed_fields:
                    data.pop(field, None)

                # Remove platform-specific paths - will be recomputed in __post_init__
                data.pop('app_dir', None)
                data.pop('projects_dir', None)

                config = cls(**data)
                print(f'[Config] Loaded from {config_path}')
                return config
            except Exception as e:
                print(f'[Config] Failed to load config: {e}')

        print(f'[Config] No config file found, using defaults')
        return cls()

    def save(self, config_path: Optional[str] = None):
        """Save configuration to JSON file"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config.json'
        else:
            config_path = Path(config_path)

        try:
            data = asdict(self)
            # Don't save platform-specific paths - they're computed on load
            data.pop('app_dir', None)
            data.pop('projects_dir', None)

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f'[Config] Saved to {config_path}')
        except Exception as e:
            print(f'[Config] Failed to save config: {e}')

    def add_recent_project(self, project_name: str):
        """Add project to recent list"""
        if project_name in self.recent_projects:
            self.recent_projects.remove(project_name)
        self.recent_projects.insert(0, project_name)
        # Keep only last 10
        self.recent_projects = self.recent_projects[:10]


# Supported languages for translation
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'zh-TW': 'Chinese (Traditional)',
    'zh-CN': 'Chinese (Simplified)',
    'ja': 'Japanese',
    'ko': 'Korean',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
}
