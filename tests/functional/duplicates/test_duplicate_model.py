import pytest

from dbt.exceptions import CompilationException, DuplicateResourceName
from dbt.tests.fixtures.project import write_project_files
from dbt.tests.util import run_dbt, get_manifest


disabled_model_sql = """
{{
    config(
        enabled=False,
        materialized="table",
    )
}}

select 1

"""

enabled_model_sql = """
{{
    config(
        enabled=True,
        materialized="table",
    )
}}

select 1 as value

"""

dbt_project_yml = """
name: 'local_dep'
version: '1.0'
config-version: 2

profile: 'default'

model-paths: ["models"]

seeds:
  quote_columns: False

"""


class TestDuplicateModelEnabled:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "model-enabled-1": {"model.sql": enabled_model_sql},
            "model-enabled-2": {"model.sql": enabled_model_sql},
        }

    def test_duplicate_model_enabled(self, project):
        message = "dbt found two models with the name"
        with pytest.raises(CompilationException) as exc:
            run_dbt(["compile"])
        exc_str = " ".join(str(exc.value).split())  # flatten all whitespace
        assert message in exc_str


class TestDuplicateModelDisabled:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "model-disabled": {"model.sql": disabled_model_sql},
            "model-enabled": {"model.sql": enabled_model_sql},
        }

    def test_duplicate_model_disabled(self, project):
        results = run_dbt(["compile"])
        assert len(results) == 1

        manifest = get_manifest(project.project_root)

        model_id = "model.test.model"
        assert model_id in manifest.nodes
        assert model_id in manifest.disabled

    def test_duplicate_model_disabled_partial_parsing(self, project):
        run_dbt(["clean"])
        results = run_dbt(["--partial-parse", "compile"])
        assert len(results) == 1
        results = run_dbt(["--partial-parse", "compile"])
        assert len(results) == 1
        results = run_dbt(["--partial-parse", "compile"])
        assert len(results) == 1


class TestDuplicateModelEnabledAcrossPackages:
    @pytest.fixture(scope="class")
    def models(self):
        return {"table_model.sql": enabled_model_sql}

    @pytest.fixture(scope="class", autouse=True)
    def setUp(self, project_root):
        local_dependency_files = {
            "dbt_project.yml": dbt_project_yml,
            "models": {"table_model.sql": enabled_model_sql},
        }
        write_project_files(project_root, "local_dependency", local_dependency_files)

    @pytest.fixture(scope="class")
    def packages(self):
        return {"packages": [{"local": "local_dependency"}]}

    def test_duplicate_model_enabled_across_packages(self, project):
        run_dbt(["deps"])
        message = "dbt found two models with the name"
        with pytest.raises(DuplicateResourceName) as exc:
            run_dbt(["run"])
        assert message in str(exc.value)


class TestDuplicateModelDisabledAcrossPackages:
    @pytest.fixture(scope="class", autouse=True)
    def setUp(self, project_root):
        local_dependency_files = {
            "dbt_project.yml": dbt_project_yml,
            "models": {"table_model.sql": enabled_model_sql},
        }
        write_project_files(project_root, "local_dependency", local_dependency_files)

    @pytest.fixture(scope="class")
    def models(self):
        return {"table_model.sql": disabled_model_sql}

    @pytest.fixture(scope="class")
    def packages(self):
        return {"packages": [{"local": "local_dependency"}]}

    def test_duplicate_model_disabled_across_packages(self, project):
        run_dbt(["deps"])
        results = run_dbt(["compile"])
        assert len(results) == 1

        manifest = get_manifest(project.project_root)
        local_dep_model_id = "model.local_dep.table_model"
        model_id = "model.test.table_model"
        assert local_dep_model_id in manifest.nodes
        assert model_id in manifest.disabled


class TestModelTestOverlap:
    @pytest.fixture(scope="class")
    def models(self):
        return {"table_model.sql": enabled_model_sql}

    @property
    def project_config(self):
        return {
            "config-version": 2,
            "test-paths": ["models"],
        }

    def test_duplicate_test_model_paths(self, project):
        # this should be ok: test/model overlap is fine
        run_dbt(["compile"])
        run_dbt(["--partial-parse", "compile"])
        run_dbt(["--partial-parse", "compile"])


class TestMultipleDisabledModels:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "subdir3": {"model_alt.sql": disabled_model_sql},
            "subdir2": {"model_alt.sql": disabled_model_sql},
            "subdir1": {"model_alt.sql": enabled_model_sql},
        }

    def test_multiple_disabled_models(self, project):
        run_dbt(["compile"])
        manifest = get_manifest(project.project_root)
        model_id = "model.test.model_alt"
        assert model_id in manifest.nodes
