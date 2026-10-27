import typing as ty
from pathlib import Path

from fileformats.core import converter
from fileformats.vendor.xnat.medimage import Snapshots
from pydra.compose import python

from fileformats.vendor.canfield.medimage import DexiDataDir


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def SnapshotDexiDataDir(
    in_file: DexiDataDir,
    out_file: ty.Optional[Path] = None,
) -> Snapshots:
    """Generate XNAT snapshots from a DexiDataDir directory"""

    orig_gif = None
    thumbnail_gif = None

    return Snapshots([orig_gif, thumbnail_gif])
