"""
Project Manager
Handles creation, loading, and management of translation projects
Each project has its own glossary, patterns, and translation cache
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime


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
class ProjectSettings:
    """Project-specific settings"""
    # Language settings
    source_lang: str = 'en'
    target_lang: str = 'zh-TW'

    # Ollama configuration
    ollama: 'OllamaConfig' = field(default_factory=OllamaConfig)

    # Translation options
    case_sensitive_glossary: bool = True
    translation_mode: str = 'glossary_reference'
    auto_refresh_preview: bool = True
    worker_count: int = 3

    # Output folder settings
    include_parent_folder: bool = True
    include_lang_code_folder: bool = True
    custom_output_root: str = ''

    # Directory history
    last_input_dir: str = ''
    last_output_dir: str = ''

    # Legacy fields (for backward compatibility)
    preserve_formatting: bool = True
    use_glossary: bool = True
    use_patterns: bool = True
    selected_glossary: str = ''  # Filename of selected glossary (e.g., "glossary.json")

    # Deprecated field
    ollama_model: str = ''  # Kept for backward compatibility, use ollama.model instead


@dataclass
class ProjectPaths:
    """Project file paths (relative to project directory)"""
    glossary: str = 'glossary.json'
    patterns: str = 'patterns.json'
    cache: str = 'translations'


@dataclass
class ProjectStatistics:
    """Project statistics"""
    files_translated: int = 0
    total_chunks: int = 0
    cache_entries: int = 0
    glossary_terms: int = 0


@dataclass
class Project:
    """Translation project configuration"""
    name: str
    description: str = ''
    created: str = ''
    modified: str = ''
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    paths: ProjectPaths = field(default_factory=ProjectPaths)
    statistics: ProjectStatistics = field(default_factory=ProjectStatistics)

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now().isoformat()
        if not self.modified:
            self.modified = self.created

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        # Convert settings to dict, handling nested OllamaConfig
        settings_dict = asdict(self.settings)

        return {
            'name': self.name,
            'description': self.description,
            'created': self.created,
            'modified': self.modified,
            'settings': settings_dict,
            'paths': asdict(self.paths),
            'statistics': asdict(self.statistics),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create Project from dictionary"""
        # Handle nested OllamaConfig in settings
        settings_data = data.get('settings', {})
        ollama_data = settings_data.pop('ollama', {}) if 'ollama' in settings_data else {}

        # Create OllamaConfig from dict
        if ollama_data:
            ollama_config = OllamaConfig(**ollama_data)
        else:
            # Backward compatibility: if ollama_model field exists, use it
            if 'ollama_model' in settings_data and settings_data['ollama_model']:
                ollama_config = OllamaConfig(model=settings_data['ollama_model'])
            else:
                ollama_config = OllamaConfig()

        settings = ProjectSettings(ollama=ollama_config, **settings_data)
        paths = ProjectPaths(**data.get('paths', {}))
        statistics = ProjectStatistics(**data.get('statistics', {}))

        return cls(
            name=data['name'],
            description=data.get('description', ''),
            created=data.get('created', ''),
            modified=data.get('modified', ''),
            settings=settings,
            paths=paths,
            statistics=statistics,
        )


class ProjectManager:
    """Manages translation projects"""

    def __init__(self, projects_dir: str, app_config: Optional[Any] = None):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._current_project: Optional[Project] = None
        self._current_project_path: Optional[Path] = None
        self._current_settings: Optional[ProjectSettings] = None
        self._app_config = app_config  # Reference to global AppConfig for migration

    @property
    def current_project(self) -> Optional[Project]:
        return self._current_project

    @property
    def current_project_path(self) -> Optional[Path]:
        return self._current_project_path

    @property
    def current_settings(self) -> Optional[ProjectSettings]:
        """Get the current project's settings"""
        return self._current_settings

    def list_projects(self) -> List[str]:
        """List all available projects"""
        projects = []
        for item in self.projects_dir.iterdir():
            if item.is_dir() and (item / 'project.json').exists():
                projects.append(item.name)
        return sorted(projects)

    def project_exists(self, name: str) -> bool:
        """Check if a project exists"""
        project_dir = self.projects_dir / name
        return project_dir.exists() and (project_dir / 'project.json').exists()

    def create_project(self, name: str, description: str = '',
                       copy_from: Optional[str] = None) -> Project:
        """Create a new project"""
        project_dir = self.projects_dir / name

        if project_dir.exists():
            raise ValueError(f'Project "{name}" already exists')

        # Create project directory
        project_dir.mkdir(parents=True)

        # Create project
        project = Project(name=name, description=description)

        # Create glossary directory
        glossary_dir = project_dir / 'glossary'
        glossary_dir.mkdir(exist_ok=True)

        # Create project settings
        if copy_from and self.project_exists(copy_from):
            # Copy from source project
            source_dir = self.projects_dir / copy_from

            # Copy glossary folder or file
            source_glossary_dir = source_dir / 'glossary'
            if source_glossary_dir.exists() and source_glossary_dir.is_dir():
                # Copy all glossary files from source
                for glossary_file in source_glossary_dir.glob('*.json'):
                    shutil.copy(glossary_file, glossary_dir / glossary_file.name)
            elif (source_dir / 'glossary.json').exists():
                # Old format: copy glossary.json to glossary folder
                shutil.copy(source_dir / 'glossary.json', glossary_dir / 'glossary.json')

            # Copy patterns
            if (source_dir / 'patterns.json').exists():
                shutil.copy(source_dir / 'patterns.json', project_dir / 'patterns.json')

            # Copy settings if available
            source_settings_file = source_dir / 'settings.json'
            if source_settings_file.exists():
                shutil.copy(source_settings_file, project_dir / 'settings.json')
                print(f'[ProjectManager] Copied settings from project "{copy_from}"')
            else:
                # Source project doesn't have settings.json, create from global config
                settings = self._migrate_settings_from_global(project_dir)
                self._save_project_settings(settings, project_dir)
        else:
            # Create new project with default data
            # Create default empty glossary in glossary folder
            self._create_empty_glossary(glossary_dir / 'glossary.json')
            # Create empty patterns
            self._create_empty_patterns(project_dir / 'patterns.json')

            # Create settings from global config
            try:
                settings = self._migrate_settings_from_global(project_dir)
                self._save_project_settings(settings, project_dir)
                print(f'[ProjectManager] Created settings.json for new project "{name}"')
            except Exception as e:
                print(f'[ProjectManager] Warning: Failed to create settings: {e}')
                # Create with defaults
                settings = ProjectSettings()
                self._save_project_settings(settings, project_dir)

        # Create translations cache directory
        (project_dir / 'translations').mkdir(exist_ok=True)

        # Save project config
        self._save_project(project, project_dir)

        return project

    def load_project(self, name: str) -> Project:
        """Load a project by name"""
        project_dir = self.projects_dir / name

        if not project_dir.exists():
            raise ValueError(f'Project "{name}" does not exist')

        project_file = project_dir / 'project.json'
        if not project_file.exists():
            raise ValueError(f'Project "{name}" is corrupted (missing project.json)')

        with open(project_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        project = Project.from_dict(data)

        # Update statistics
        project.statistics.glossary_terms = self._count_glossary_terms(project_dir)
        project.statistics.cache_entries = self._count_cache_entries(project_dir)

        self._current_project = project
        self._current_project_path = project_dir

        # Load project settings
        settings = self._load_project_settings(project_dir)

        # If settings.json doesn't exist, migrate from global config
        if settings is None:
            print(f'[ProjectManager] No settings.json found for project "{name}", migrating...')
            settings = self._migrate_settings_from_global(project_dir)
            # Save migrated settings immediately
            self._save_project_settings(settings, project_dir)
            print(f'[ProjectManager] Migration complete for project "{name}"')

        self._current_settings = settings

        return project

    def save_current_project(self):
        """Save the current project and its settings"""
        if self._current_project and self._current_project_path:
            self._current_project.modified = datetime.now().isoformat()
            self._save_project(self._current_project, self._current_project_path)
            # Also save project settings
            if self._current_settings:
                self._save_project_settings(self._current_settings, self._current_project_path)

    def delete_project(self, name: str):
        """Delete a project"""
        if name in ['default']:
            raise ValueError(f'Cannot delete system project "{name}"')

        project_dir = self.projects_dir / name

        if not project_dir.exists():
            raise ValueError(f'Project "{name}" does not exist')

        # Clear current project if it's the one being deleted
        if self._current_project and self._current_project.name == name:
            self._current_project = None
            self._current_project_path = None
            self._current_settings = None

        shutil.rmtree(project_dir)

    def get_glossary_path(self, project_name: Optional[str] = None) -> Path:
        """Get the glossary path for a project"""
        if project_name:
            return self.projects_dir / project_name / 'glossary.json'
        elif self._current_project_path:
            return self._current_project_path / 'glossary.json'
        else:
            raise ValueError('No project loaded')

    def get_patterns_path(self, project_name: Optional[str] = None) -> Path:
        """Get the patterns path for a project"""
        if project_name:
            return self.projects_dir / project_name / 'patterns.json'
        elif self._current_project_path:
            return self._current_project_path / 'patterns.json'
        else:
            raise ValueError('No project loaded')

    def get_cache_path(self, project_name: Optional[str] = None) -> Path:
        """Get the cache directory for a project"""
        if project_name:
            return self.projects_dir / project_name / 'translations'
        elif self._current_project_path:
            return self._current_project_path / 'translations'
        else:
            raise ValueError('No project loaded')

    def get_settings_path(self, project_name: Optional[str] = None) -> Path:
        """Get the settings file path for a project"""
        if project_name:
            project_dir = self.projects_dir / project_name
            if not project_dir.exists():
                raise ValueError(f'Project "{project_name}" does not exist')
            return project_dir / 'settings.json'
        elif self._current_project_path:
            return self._current_project_path / 'settings.json'
        else:
            raise ValueError('No project loaded')

    def _load_project_settings(self, project_dir: Path) -> ProjectSettings:
        """Load project settings from settings.json"""
        settings_file = project_dir / 'settings.json'

        if not settings_file.exists():
            # Settings file doesn't exist, will need migration
            return None

        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle nested OllamaConfig
            ollama_data = data.pop('ollama', {})
            if ollama_data:
                ollama_config = OllamaConfig(**ollama_data)
            else:
                # Fallback to default
                ollama_config = OllamaConfig()

            # Create ProjectSettings with all fields
            settings = ProjectSettings(ollama=ollama_config, **data)
            print(f'[ProjectManager] Loaded settings from {settings_file}')
            return settings

        except json.JSONDecodeError as e:
            print(f'[ProjectManager] Error: Malformed settings.json: {e}')
            print(f'[ProjectManager] Creating new settings with defaults')
            return None
        except Exception as e:
            print(f'[ProjectManager] Error loading settings: {e}')
            return None

    def _save_project_settings(self, settings: ProjectSettings, project_dir: Path):
        """Save project settings to settings.json"""
        settings_file = project_dir / 'settings.json'

        try:
            # Convert to dict
            settings_dict = asdict(settings)

            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=2, ensure_ascii=False)
            print(f'[ProjectManager] Saved settings to {settings_file}')
        except Exception as e:
            print(f'[ProjectManager] Failed to save settings: {e}')

    def save_project_settings(self):
        """Save the current project's settings"""
        if self._current_settings and self._current_project_path:
            self._save_project_settings(self._current_settings, self._current_project_path)
        else:
            print('[ProjectManager] Warning: No project loaded, cannot save settings')

    def _migrate_settings_from_global(self, project_dir: Path) -> ProjectSettings:
        """Migrate settings from global AppConfig to project-specific settings"""
        try:
            # Try to get settings from global config
            if self._app_config:
                print('[ProjectManager] Migrating settings from global config...')
                # Import OllamaConfig from config module
                from app.core.config import OllamaConfig as GlobalOllamaConfig

                # Copy Ollama settings if available
                if hasattr(self._app_config, 'ollama') and self._app_config.ollama:
                    ollama = OllamaConfig(
                        host=self._app_config.ollama.host,
                        port=self._app_config.ollama.port,
                        model=self._app_config.ollama.model,
                        timeout=self._app_config.ollama.timeout
                    )
                else:
                    ollama = OllamaConfig()

                # Create ProjectSettings with migrated values
                settings = ProjectSettings(
                    source_lang=getattr(self._app_config, 'source_lang', 'en'),
                    target_lang=getattr(self._app_config, 'target_lang', 'zh-TW'),
                    ollama=ollama,
                    case_sensitive_glossary=getattr(self._app_config, 'case_sensitive_glossary', True),
                    translation_mode=getattr(self._app_config, 'translation_mode', 'glossary_reference'),
                    auto_refresh_preview=getattr(self._app_config, 'auto_refresh_preview', True),
                    worker_count=getattr(self._app_config, 'worker_count', 3),
                    include_parent_folder=getattr(self._app_config, 'include_parent_folder', True),
                    include_lang_code_folder=getattr(self._app_config, 'include_lang_code_folder', True),
                    custom_output_root=getattr(self._app_config, 'custom_output_root', ''),
                    last_input_dir=getattr(self._app_config, 'last_input_dir', ''),
                    last_output_dir=getattr(self._app_config, 'last_output_dir', '')
                )

                print('[ProjectManager] Successfully migrated settings from global config')
                return settings
            else:
                print('[ProjectManager] No global config available, using defaults')
                return ProjectSettings()

        except Exception as e:
            print(f'[ProjectManager] Warning: Migration failed: {e}')
            print('[ProjectManager] Using default settings')
            return ProjectSettings()

    def _save_project(self, project: Project, project_dir: Path):
        """Save project to disk"""
        project_file = project_dir / 'project.json'
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project.to_dict(), f, indent=2, ensure_ascii=False)

    def _create_empty_glossary(self, path: Path):
        """Create an empty glossary file"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)

    def _create_empty_patterns(self, path: Path):
        """Create an empty patterns file"""
        default_patterns = {
            "exclusion_patterns": [],
            "description": "Custom patterns to exclude from translation"
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default_patterns, f, indent=2)

    def _count_glossary_terms(self, project_dir: Path) -> int:
        """Count terms in glossary"""
        glossary_file = project_dir / 'glossary.json'
        if glossary_file.exists():
            try:
                with open(glossary_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Handle both formats
                        if 'terms' in data:
                            return len(data['terms'])
                        else:
                            return len(data)
            except:
                pass
        return 0

    def _count_cache_entries(self, project_dir: Path) -> int:
        """Count entries in translation cache"""
        cache_dir = project_dir / 'translations'
        if cache_dir.exists():
            count = 0
            for jsonl_file in cache_dir.glob('*.jsonl'):
                try:
                    with open(jsonl_file, 'r', encoding='utf-8') as f:
                        count += sum(1 for _ in f)
                except:
                    pass
            return count
        return 0


def setup_default_projects(projects_dir: str):
    """Setup default and Lineage2 projects"""
    pm = ProjectManager(projects_dir)

    # Create Default project if not exists
    if not pm.project_exists('default'):
        pm.create_project(
            name='default',
            description='Default project with no game-specific glossary or patterns'
        )
        print('[ProjectManager] Created "default" project')

    # Create Lineage2 project if not exists
    if not pm.project_exists('lineage2'):
        project = pm.create_project(
            name='lineage2',
            description='Lineage 2 game HTML translation with full glossary and patterns'
        )
        # Update settings for Lineage2
        project.settings.use_glossary = True
        project.settings.use_patterns = True
        pm._save_project(project, pm.projects_dir / 'lineage2')
        print('[ProjectManager] Created "lineage2" project')

    return pm
