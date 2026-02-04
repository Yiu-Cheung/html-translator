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
    """Main application configuration"""
    # Ollama settings
    ollama: OllamaConfig = field(default_factory=OllamaConfig)

    # Default languages
    source_lang: str = 'en'
    target_lang: str = 'zh-TW'

    # UI settings
    window_width: int = 1400
    window_height: int = 900
    splitter_sizes: list = field(default_factory=lambda: [300, 1100])

    # Paths
    app_dir: str = ''
    projects_dir: str = ''
    last_project: str = 'default'
    last_input_dir: str = ''
    last_output_dir: str = ''

    # Recent projects
    recent_projects: list = field(default_factory=list)

    # Translation options
    case_sensitive_glossary: bool = True  # Match glossary terms with exact case
    translation_mode: str = 'glossary_reference'  # Translation mode: 'glossary_reference', 'glossary_placeholder', or 'full_context'
    direct_translate_mode: bool = False  # Deprecated: kept for backward compatibility
    auto_refresh_preview: bool = True  # Auto-refresh preview during translation
    worker_count: int = 3  # Number of parallel translation workers (1-10)

    # Output folder settings
    include_parent_folder: bool = True  # Include source parent folder name in output path
    include_lang_code_folder: bool = True  # Include language code folder in output path
    custom_output_root: str = ''  # Custom output root folder (empty = use default 'output' folder)

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

        # Validate custom_output_root - clear if invalid path
        if self.custom_output_root and not Path(self.custom_output_root).exists():
            print(f'[Config] Custom output root not found, resetting: {self.custom_output_root}')
            self.custom_output_root = ''

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

                # Handle nested OllamaConfig
                ollama_data = data.pop('ollama', {})
                ollama_config = OllamaConfig(**ollama_data)

                # Remove platform-specific paths - will be recomputed in __post_init__
                data.pop('app_dir', None)
                data.pop('projects_dir', None)

                config = cls(ollama=ollama_config, **data)
                print(f'[Config] Loaded from {config_path}')
                print(f'[Config] Target language: {config.target_lang}')
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
