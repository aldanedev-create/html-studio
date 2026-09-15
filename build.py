"""Build the .vel frontend with the editable local Teloce-Py checkout."""

from pathlib import Path
import shutil

from teloce.build import build_project


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"


def build() -> dict:
    result = build_project(
        ROOT,
        out_dir=DIST,
        options={
            "dev": True,
            "source_maps": True,
            "shared_runtime": True,
            "static_dir": "static/js",
            "clean": True,
        },
    )

    # Keep browser adapters in the same public tree as generated .vel modules.
    # AssetManager also copies source assets for web projects, but this explicit
    # path is the stable path used by the Flaxon shell and Tauri frontendDist.
    adapter_source = ROOT / "static" / "js" / "adapters"
    adapter_output = DIST / "static" / "js" / "adapters"
    if adapter_source.is_dir():
        shutil.copytree(adapter_source, adapter_output, dirs_exist_ok=True)
    asset_source = ROOT / "static" / "assets"
    asset_output = DIST / "static" / "assets"
    if asset_source.is_dir():
        shutil.copytree(asset_source, asset_output, dirs_exist_ok=True)
    return result


if __name__ == "__main__":
    outcome = build()
    print(
        f"Scanned {outcome['total']} .vel files; compiled {outcome['compiled']} "
        f"({outcome.get('cache_hits', 0)} cache hits); "
        f"{outcome.get('assets_copied', 0)} assets copied into {DIST}"
    )
