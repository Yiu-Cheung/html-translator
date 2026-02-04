"""
Automated tests for per-project settings functionality

Tests cover:
- 10.1: Fresh installation - create new project and verify settings.json
- 10.2: Migration - load project without settings.json and verify migration
- 10.3: Project switching - switch between projects with different settings
- 10.4: Settings modification - change settings and verify isolation
- 10.5: Project creation from template - verify settings are copied
- 10.6: Malformed settings.json - verify fallback to defaults
- 10.7: Global config persistence - verify UI settings persist
"""

import json
import pytest
import shutil
from pathlib import Path
from tempfile import mkdtemp

from app.core.config import AppConfig
from app.core.project_manager import ProjectManager, ProjectSettings, OllamaConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp = Path(mkdtemp())
    yield temp
    # Cleanup
    if temp.exists():
        shutil.rmtree(temp)


@pytest.fixture
def app_config(temp_dir):
    """Create a test AppConfig"""
    config = AppConfig(
        window_width=1400,
        window_height=900,
        splitter_sizes=[300, 1100],
        app_dir=str(temp_dir),
        projects_dir=str(temp_dir / 'projects'),
        last_project='default',
        recent_projects=[]
    )
    return config


@pytest.fixture
def project_manager(temp_dir, app_config):
    """Create a test ProjectManager"""
    projects_dir = temp_dir / 'projects'
    projects_dir.mkdir(parents=True, exist_ok=True)
    return ProjectManager(str(projects_dir), app_config=app_config)


class TestFreshInstallation:
    """Test 10.1: Fresh installation - create new project and verify settings.json"""

    def test_create_new_project_creates_settings_json(self, project_manager, temp_dir):
        """Test that creating a new project creates settings.json"""
        # Create a new project
        project = project_manager.create_project(
            name='test-project',
            description='Test project for settings'
        )

        # Verify settings.json exists
        settings_path = temp_dir / 'projects' / 'test-project' / 'settings.json'
        assert settings_path.exists(), "settings.json should be created"

        # Verify settings.json has valid structure
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings_data = json.load(f)

        # Check required fields
        assert 'source_lang' in settings_data
        assert 'target_lang' in settings_data
        assert 'ollama' in settings_data
        assert 'case_sensitive_glossary' in settings_data
        assert 'translation_mode' in settings_data
        assert 'worker_count' in settings_data
        assert 'last_input_dir' in settings_data
        assert 'last_output_dir' in settings_data

        # Check Ollama config structure
        assert 'host' in settings_data['ollama']
        assert 'port' in settings_data['ollama']
        assert 'model' in settings_data['ollama']
        assert 'timeout' in settings_data['ollama']

    def test_new_project_settings_have_defaults(self, project_manager, temp_dir):
        """Test that new project settings have correct default values"""
        project = project_manager.create_project(name='defaults-test')

        settings_path = temp_dir / 'projects' / 'defaults-test' / 'settings.json'
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings_data = json.load(f)

        # Verify defaults
        assert settings_data['source_lang'] == 'en'
        assert settings_data['target_lang'] == 'zh-TW'
        assert settings_data['ollama']['host'] == 'localhost'
        assert settings_data['ollama']['port'] == 11434
        assert settings_data['ollama']['model'] == 'gemma3:4b'
        assert settings_data['case_sensitive_glossary'] is True
        assert settings_data['translation_mode'] == 'glossary_reference'
        assert settings_data['worker_count'] == 3


class TestMigration:
    """Test 10.2: Migration - load project without settings.json and verify migration"""

    def test_load_project_without_settings_migrates(self, project_manager, temp_dir):
        """Test that loading a project without settings.json triggers migration"""
        # Create a project directory manually without settings.json
        project_dir = temp_dir / 'projects' / 'legacy-project'
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create only project.json (legacy format)
        project_data = {
            'name': 'legacy-project',
            'description': 'Legacy project without settings.json',
            'created': '2024-01-01T00:00:00',
            'modified': '2024-01-01T00:00:00',
            'settings': {
                'source_lang': 'en',
                'target_lang': 'ja',
            },
            'paths': {
                'glossary': 'glossary.json',
                'patterns': 'patterns.json',
                'cache': 'translations'
            },
            'statistics': {
                'files_translated': 0,
                'total_chunks': 0,
                'cache_entries': 0,
                'glossary_terms': 0
            }
        }

        with open(project_dir / 'project.json', 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2)

        # Create required directories
        (project_dir / 'glossary').mkdir(exist_ok=True)
        (project_dir / 'translations').mkdir(exist_ok=True)

        # Load the project (should trigger migration)
        project = project_manager.load_project('legacy-project')

        # Verify settings.json was created
        settings_path = project_dir / 'settings.json'
        assert settings_path.exists(), "Migration should create settings.json"

        # Verify migrated settings
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings_data = json.load(f)

        assert 'ollama' in settings_data
        assert settings_data['source_lang'] == 'en'

    def test_migration_preserves_global_config_values(self, project_manager, temp_dir):
        """Test that migration copies values from global AppConfig"""
        # Set custom values in app_config
        project_manager._app_config.ollama = OllamaConfig(
            host='custom-host',
            port=12345,
            model='custom-model',
            timeout=120
        )

        # Create legacy project without settings.json
        project_dir = temp_dir / 'projects' / 'migrate-test'
        project_dir.mkdir(parents=True, exist_ok=True)

        project_data = {
            'name': 'migrate-test',
            'description': 'Test migration',
            'settings': {},
            'paths': {},
            'statistics': {}
        }

        with open(project_dir / 'project.json', 'w', encoding='utf-8') as f:
            json.dump(project_data, f)

        (project_dir / 'glossary').mkdir(exist_ok=True)
        (project_dir / 'translations').mkdir(exist_ok=True)

        # Load project (triggers migration)
        project = project_manager.load_project('migrate-test')

        # Verify migrated settings contain global config values
        settings = project_manager.current_settings
        assert settings.ollama.host == 'custom-host'
        assert settings.ollama.port == 12345
        assert settings.ollama.model == 'custom-model'


class TestProjectSwitching:
    """Test 10.3: Project switching - switch between projects with different settings"""

    def test_switch_between_projects_preserves_settings(self, project_manager):
        """Test that switching projects loads correct settings for each"""
        # Create Project A with specific settings
        project_a = project_manager.create_project('project-a')
        project_manager.load_project('project-a')
        settings_a = project_manager.current_settings
        settings_a.ollama.model = 'gemma3:4b'
        settings_a.source_lang = 'en'
        settings_a.worker_count = 3
        project_manager.save_project_settings()

        # Create Project B with different settings
        project_b = project_manager.create_project('project-b')
        project_manager.load_project('project-b')
        settings_b = project_manager.current_settings
        settings_b.ollama.model = 'qwen3-vl:4b-instruct'
        settings_b.source_lang = 'ja'
        settings_b.worker_count = 5
        project_manager.save_project_settings()

        # Switch back to Project A
        project_manager.load_project('project-a')
        loaded_settings_a = project_manager.current_settings

        assert loaded_settings_a.ollama.model == 'gemma3:4b'
        assert loaded_settings_a.source_lang == 'en'
        assert loaded_settings_a.worker_count == 3

        # Switch to Project B
        project_manager.load_project('project-b')
        loaded_settings_b = project_manager.current_settings

        assert loaded_settings_b.ollama.model == 'qwen3-vl:4b-instruct'
        assert loaded_settings_b.source_lang == 'ja'
        assert loaded_settings_b.worker_count == 5

    def test_project_settings_are_isolated(self, project_manager):
        """Test that modifying one project's settings doesn't affect another"""
        # Create two projects
        project_manager.create_project('isolated-a')
        project_manager.create_project('isolated-b')

        # Modify Project A settings
        project_manager.load_project('isolated-a')
        settings_a = project_manager.current_settings
        settings_a.ollama.host = 'host-a'
        settings_a.target_lang = 'zh-CN'
        project_manager.save_project_settings()

        # Load Project B and verify it has default settings
        project_manager.load_project('isolated-b')
        settings_b = project_manager.current_settings

        assert settings_b.ollama.host == 'localhost'  # Default, not 'host-a'
        assert settings_b.target_lang == 'zh-TW'  # Default, not 'zh-CN'

    def test_switching_projects_with_different_models(self, project_manager):
        """Test that switching between projects with different models works correctly"""
        # Create Project A with model 1
        project_manager.create_project('model-test-a')
        project_manager.load_project('model-test-a')
        settings_a = project_manager.current_settings
        settings_a.ollama.host = 'localhost'
        settings_a.ollama.port = 11434
        settings_a.ollama.model = 'gemma3:4b'
        project_manager.save_project_settings()

        # Create Project B with different model but same host/port
        project_manager.create_project('model-test-b')
        project_manager.load_project('model-test-b')
        settings_b = project_manager.current_settings
        settings_b.ollama.host = 'localhost'
        settings_b.ollama.port = 11434
        settings_b.ollama.model = 'qwen3-vl:4b-instruct'
        project_manager.save_project_settings()

        # Switch back to Project A - should switch model without reconnecting
        project_manager.load_project('model-test-a')
        assert project_manager.current_settings.ollama.model == 'gemma3:4b'

        # Switch to Project B - should switch model without reconnecting
        project_manager.load_project('model-test-b')
        assert project_manager.current_settings.ollama.model == 'qwen3-vl:4b-instruct'


class TestSettingsModification:
    """Test 10.4: Settings modification - change settings and verify only current project affected"""

    def test_modify_settings_only_affects_current_project(self, project_manager, temp_dir):
        """Test that modifying settings only affects the current project's file"""
        # Create two projects
        project_manager.create_project('modify-a')
        project_manager.create_project('modify-b')

        # Get initial settings files
        settings_a_path = temp_dir / 'projects' / 'modify-a' / 'settings.json'
        settings_b_path = temp_dir / 'projects' / 'modify-b' / 'settings.json'

        # Read Project B's initial settings
        with open(settings_b_path, 'r') as f:
            initial_b_settings = json.load(f)

        # Modify Project A settings
        project_manager.load_project('modify-a')
        settings_a = project_manager.current_settings
        settings_a.ollama.model = 'modified-model'
        settings_a.worker_count = 99
        project_manager.save_project_settings()

        # Read Project B's settings again
        with open(settings_b_path, 'r') as f:
            current_b_settings = json.load(f)

        # Verify Project B's settings are unchanged
        assert current_b_settings == initial_b_settings
        assert current_b_settings['ollama']['model'] != 'modified-model'
        assert current_b_settings['worker_count'] != 99

        # Verify Project A's settings were changed
        with open(settings_a_path, 'r') as f:
            current_a_settings = json.load(f)

        assert current_a_settings['ollama']['model'] == 'modified-model'
        assert current_a_settings['worker_count'] == 99


class TestProjectCreationFromTemplate:
    """Test 10.5: Project creation from template - verify settings are copied"""

    def test_create_project_from_template_copies_settings(self, project_manager, temp_dir):
        """Test that creating project from template copies settings.json"""
        # Create source project with custom settings
        project_manager.create_project('template-source')
        project_manager.load_project('template-source')
        source_settings = project_manager.current_settings
        source_settings.ollama.model = 'template-model'
        source_settings.source_lang = 'fr'
        source_settings.worker_count = 7
        source_settings.custom_output_root = '/custom/path'
        project_manager.save_project_settings()

        # Create new project from template
        project_manager.create_project('template-copy', copy_from='template-source')

        # Verify copied project has same settings
        project_manager.load_project('template-copy')
        copied_settings = project_manager.current_settings

        assert copied_settings.ollama.model == 'template-model'
        assert copied_settings.source_lang == 'fr'
        assert copied_settings.worker_count == 7
        assert copied_settings.custom_output_root == '/custom/path'

    def test_template_and_copy_settings_are_independent(self, project_manager):
        """Test that template and copy have independent settings after creation"""
        # Create template with settings
        project_manager.create_project('template-orig')
        project_manager.load_project('template-orig')
        project_manager.current_settings.ollama.port = 9999
        project_manager.save_project_settings()

        # Create copy from template
        project_manager.create_project('template-dup', copy_from='template-orig')

        # Modify copy's settings
        project_manager.load_project('template-dup')
        project_manager.current_settings.ollama.port = 8888
        project_manager.save_project_settings()

        # Verify original template is unchanged
        project_manager.load_project('template-orig')
        assert project_manager.current_settings.ollama.port == 9999


class TestMalformedSettings:
    """Test 10.6: Malformed settings.json - verify fallback to defaults"""

    def test_malformed_json_falls_back_to_defaults(self, project_manager, temp_dir):
        """Test that malformed settings.json triggers fallback to defaults"""
        # Create project normally
        project_manager.create_project('malformed-test')

        # Corrupt the settings.json
        settings_path = temp_dir / 'projects' / 'malformed-test' / 'settings.json'
        with open(settings_path, 'w') as f:
            f.write('{invalid json syntax')

        # Load project (should handle error gracefully)
        project = project_manager.load_project('malformed-test')

        # Should have default settings
        settings = project_manager.current_settings
        assert settings is not None
        assert settings.ollama.host == 'localhost'
        assert settings.source_lang == 'en'

        # Settings file should be recreated with defaults
        assert settings_path.exists()
        with open(settings_path, 'r') as f:
            repaired_data = json.load(f)
            assert 'ollama' in repaired_data

    def test_missing_fields_filled_with_defaults(self, project_manager, temp_dir):
        """Test that settings with missing fields get filled with defaults"""
        # Create project
        project_manager.create_project('incomplete-test')
        settings_path = temp_dir / 'projects' / 'incomplete-test' / 'settings.json'

        # Write incomplete settings (missing some fields)
        incomplete_settings = {
            'source_lang': 'de',
            'ollama': {
                'host': 'localhost',
                'port': 11434
                # Missing 'model' and 'timeout'
            }
            # Missing many other fields
        }

        with open(settings_path, 'w') as f:
            json.dump(incomplete_settings, f)

        # Load project
        project = project_manager.load_project('incomplete-test')
        settings = project_manager.current_settings

        # Should have defaults for missing fields
        assert settings.source_lang == 'de'  # Preserved
        assert settings.target_lang == 'zh-TW'  # Default
        assert settings.ollama.model == 'gemma3:4b'  # Default
        assert settings.worker_count == 3  # Default


class TestGlobalConfigPersistence:
    """Test 10.7: Global config persistence - verify UI settings persist"""

    def test_global_config_persists_across_project_switches(self, project_manager, app_config, temp_dir):
        """Test that global AppConfig settings persist when switching projects"""
        # Set custom global config values
        app_config.window_width = 1600
        app_config.window_height = 1000
        app_config.splitter_sizes = [400, 1200]

        # Save global config
        config_path = temp_dir / 'config.json'
        app_config.save(str(config_path))

        # Create and switch between projects
        project_manager.create_project('ui-test-1')
        project_manager.create_project('ui-test-2')

        project_manager.load_project('ui-test-1')
        project_manager.load_project('ui-test-2')
        project_manager.load_project('ui-test-1')

        # Reload global config
        loaded_config = AppConfig.load(str(config_path))

        # Verify global settings are preserved
        assert loaded_config.window_width == 1600
        assert loaded_config.window_height == 1000
        assert loaded_config.splitter_sizes == [400, 1200]

    def test_global_config_separate_from_project_settings(self, project_manager, app_config, temp_dir):
        """Test that global config file doesn't contain project-specific settings"""
        # Create project with specific settings
        project_manager.create_project('separation-test')
        project_manager.load_project('separation-test')
        project_manager.current_settings.ollama.model = 'project-specific-model'
        project_manager.current_settings.source_lang = 'es'
        project_manager.save_project_settings()

        # Save global config
        config_path = temp_dir / 'config.json'
        app_config.save(str(config_path))

        # Read global config file
        with open(config_path, 'r') as f:
            global_config_data = json.load(f)

        # Verify project-specific settings are NOT in global config
        assert 'ollama' not in global_config_data
        assert 'source_lang' not in global_config_data
        assert 'target_lang' not in global_config_data
        assert 'worker_count' not in global_config_data

        # Verify UI settings ARE in global config
        assert 'window_width' in global_config_data
        assert 'window_height' in global_config_data
        assert 'splitter_sizes' in global_config_data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
