"""Execute committed notebooks with this interpreter, without a global kernelspec install."""
import json
import sys
import tempfile

from .config import ROOT

NOTEBOOK_NAMES = (
    "00_source_and_relational_schema.ipynb",
    "01_data_quality_and_sql.ipynb",
    "02_delivery_and_satisfaction.ipynb",
    "03_reviews_and_sensitivity.ipynb",
    "04_findings_and_recommendations.ipynb",
)


def execute_notebooks() -> list[str]:
    import nbformat
    from jupyter_client import KernelManager
    from jupyter_client.kernelspec import KernelSpecManager
    from nbclient import NotebookClient

    runtime = ROOT / "data/interim"
    runtime.mkdir(parents=True, exist_ok=True)
    paths = sorted((ROOT / "notebooks").glob("*.ipynb"))
    if tuple(path.name for path in paths) != NOTEBOOK_NAMES:
        raise ValueError("Notebook files do not match the documented sequence")
    completed = []
    with tempfile.TemporaryDirectory(dir=runtime) as kernel_dir:
        from pathlib import Path
        spec = Path(kernel_dir) / "olist-env"
        spec.mkdir()
        (spec / "kernel.json").write_text(json.dumps({
            "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Olist project environment", "language": "python",
            "env": {"IPYTHONDIR": str(runtime / "ipython"), "MPLCONFIGDIR": str(runtime / "matplotlib")},
        }))
        for path in paths:
            notebook = nbformat.read(path, as_version=4)
            nbformat.validate(notebook)
            manager = KernelSpecManager(kernel_dirs=[kernel_dir], ensure_native_kernel=False)
            km = KernelManager(kernel_name="olist-env", kernel_spec_manager=manager)
            client = NotebookClient(notebook, km=km, kernel_name="olist-env", timeout=300,
                                    resources={"metadata": {"path": str(ROOT)}})
            # Supplying a kernel manager transfers lifecycle responsibility to us.
            try:
                client.execute()
            finally:
                if km.has_kernel:
                    km.shutdown_kernel(now=True)
            nbformat.write(notebook, path)
            completed.append(path.name)
    return completed
