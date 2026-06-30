"""Tests for vue-vitest-jest-setup challenge.

Illustrates Vue/Vitest/Jest setup issues: naming, globals, watch mode, dependencies.
"""
import textwrap

import pytest

class TestVueVitestJestSetup:
    """Test scenarios illustrating Vue/Vitest/Jest setup challenges."""

    def test_missing_vitest_configuration(self, tmp_path):
        """Vue project with missing Vitest configuration."""
        (tmp_path / 'package.json').write_text(textwrap.dedent("""\
            {
              "name": "my-vue-app",
              "version": "1.0.0",
              "dependencies": {
                "vue": "^3.0.0"
              }
              // Missing vitest configuration
            }
        """))
        
        (tmp_path / 'vite.config.js').write_text(textwrap.dedent("""\
            import { defineConfig } from 'vite'
            import vue from '@vitejs/plugin-vue'
            
            export default defineConfig({
              plugins: [vue()]
              // Missing test configuration for Vitest
            })
        """))
        
        package_content = (tmp_path / 'package.json').read_text()
        vite_content = (tmp_path / 'vite.config.js').read_text()
        # Check that vitest is not in dependencies or devDependencies
        assert '"vitest"' not in package_content
        assert 'test:' not in vite_content
        # Missing Vitest setup for Vue project

    def test_missing_jest_globals(self, tmp_path):
        """JavaScript project with missing Jest globals configuration."""
        (tmp_path / 'jest.config.js').write_text(textwrap.dedent("""\
            module.exports = {
              testEnvironment: 'node',
              // Missing globals configuration
              transform: {}
            }
        """))
        
        # Create test directory
        (tmp_path / 'test').mkdir()
        (tmp_path / 'test' / 'example.test.js').write_text(textwrap.dedent("""\
            // This test uses Jest globals but they might not be available
            test('example test', () => {
              expect(true).toBe(true)
            })
        """))
        
        jest_config = (tmp_path / 'jest.config.js').read_text()
        assert 'globals:' not in jest_config
        # Missing globals configuration for Jest

    def test_wrong_test_file_naming(self, tmp_path):
        """Project with wrong test file naming convention."""
        # Create src directory
        (tmp_path / 'src').mkdir()
        
        # Create test files with wrong names
        (tmp_path / 'src' / 'myTest.js').write_text('test("test", () => {})')
        (tmp_path / 'src' / 'component.spec.js').write_text('test("test", () => {})')
        (tmp_path / 'src' / 'utils_test.js').write_text('test("test", () => {})')
        
        # Create files with correct names
        (tmp_path / 'src' / 'correct.test.js').write_text('test("test", () => {})')
        
        # Jest by default looks for *.test.js and *.spec.js
        test_files = [f for f in (tmp_path / 'src').iterdir() if f.suffix.endswith('.js')]
        assert len(test_files) >= 3
        # Some test files might not be discovered due to naming

    def test_missing_watch_mode_configuration(self, tmp_path):
        """Vitest configuration missing watch mode setup."""
        (tmp_path / 'vite.config.js').write_text(textwrap.dedent("""\
            import { defineConfig } from 'vite'
            import vue from '@vitejs/plugin-vue'
            
            export default defineConfig({
              plugins: [vue()],
              test: {
                // Missing watch mode configuration
                environment: 'jsdom'
              }
            })
        """))
        
        content = (tmp_path / 'vite.config.js').read_text()
        assert 'test:' in content
        assert 'environment' in content
        # Watch mode not configured, might default to watch=false

    def test_dependency_conflicts(self, tmp_path):
        """Project with conflicting testing library dependencies."""
        (tmp_path / 'package.json').write_text(textwrap.dedent("""\
            {
              "name": "my-app",
              "dependencies": {
                "jest": "^29.0.0",
                "vitest": "^1.0.0",
                "@vue/test-utils": "^2.0.0",
                "jest-environment-jsdom": "^29.0.0"
              },
              "devDependencies": {
                "@vitest/ui": "^1.0.0"
              }
              // Having both jest and vitest can cause conflicts
            }
        """))
        
        package_content = (tmp_path / 'package.json').read_text()
        assert '"jest"' in package_content
        assert '"vitest"' in package_content
        # Multiple testing frameworks can cause conflicts