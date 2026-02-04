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
class ProjectSettings:
    """Project-specific settings"""
    source_lang: str = 'en'
    target_lang: str = 'zh'
    ollama_model: str = 'gemma3:4b'
    preserve_formatting: bool = True
    use_glossary: bool = True
    use_patterns: bool = True
    selected_glossary: str = ''  # Filename of selected glossary (e.g., "glossary.json")


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
        return {
            'name': self.name,
            'description': self.description,
            'created': self.created,
            'modified': self.modified,
            'settings': asdict(self.settings),
            'paths': asdict(self.paths),
            'statistics': asdict(self.statistics),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create Project from dictionary"""
        settings = ProjectSettings(**data.get('settings', {}))
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

    def __init__(self, projects_dir: str):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._current_project: Optional[Project] = None
        self._current_project_path: Optional[Path] = None

    @property
    def current_project(self) -> Optional[Project]:
        return self._current_project

    @property
    def current_project_path(self) -> Optional[Path]:
        return self._current_project_path

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

        # If copying from another project, copy its data
        if copy_from and self.project_exists(copy_from):
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
        else:
            # Create default empty glossary in glossary folder
            self._create_empty_glossary(glossary_dir / 'glossary.json')
            # Create empty patterns
            self._create_empty_patterns(project_dir / 'patterns.json')

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

        return project

    def save_current_project(self):
        """Save the current project"""
        if self._current_project and self._current_project_path:
            self._current_project.modified = datetime.now().isoformat()
            self._save_project(self._current_project, self._current_project_path)

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
