"""10x Atera (WTA Preview) reader for OmicVerse spatial I/O.

Atera ships a Xenium-compatible ``outs/`` bundle with three additions worth
calling out:

1. ``nucleus_boundaries.parquet`` — per-cell nucleus polygon vertices, in the
   same long-table format as ``cell_boundaries.parquet``.
2. ``morphology_focus/`` — multi-channel stain images named by content
   (``ch0000_dapi.ome.tif``, ``ch0001_atp1a1_cd45_e-cadherin.ome.tif``,
   ``ch0002_18s.ome.tif``, ``ch0003_alphasma_vimentin.ome.tif``) rather than
   the Xenium V2 ``morphology_focus_NNNN.ome.tif`` pattern.
3. Optional companion files shipped alongside ``outs/`` (not inside it):

   - ``*_cell_groups.csv``: cell_id → cell-type label + display colour for the
     vendor's pre-computed segmentation classifier.
   - ``*_he_image.ome.tif`` + ``*_he_alignment.csv``: a registered H&E whole-slide
     image and the 3×3 affine that maps H&E pixel coords → Atera spatial
     (micron) coords.

The pipeline metadata (``experiment.xenium``) and ``cell_feature_matrix.h5``
schema are identical to Xenium, so the matrix / centroid / cell-boundary path
reuses helpers from :mod:`._xenium`.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import pandas as pd
from anndata import AnnData

from ..._registry import register_function
from ..single import read_10x_h5
from ._xenium import (
    Colors,
    _boundaries_to_wkt,
    _load_experiment_metadata,
    _read_cells_table,
    _resolve,
)


def _progress(message: str, level: str = "info") -> None:
    color = Colors.CYAN
    if level == "success":
        color = Colors.GREEN
    elif level == "warn":
        color = Colors.WARNING
    print(f"{color}[Atera] {message}{Colors.ENDC}")


# Atera ships morphology stains with descriptive filenames. Lower-cased substrings
# (without the ``ch####_`` index prefix) used for ``image_key`` matching.
_ATERA_MORPHOLOGY_TAGS = {
    "dapi":     ["dapi"],
    "boundary": ["atp1a1", "cd45", "e-cadherin", "ecadherin", "boundary"],
    "rna":      ["18s", "rna"],
    "stroma":   ["alphasma", "vimentin", "stroma"],
}


def _nucleus_boundaries_to_wkt(
    root: Path,
    cell_index: pd.Index,
) -> Optional[pd.Series]:
    """Atera-specific nucleus polygons. Same schema as ``cell_boundaries.parquet``;
    we just point ``_boundaries_to_wkt`` at a different filename via a temporary
    rename-style resolver. Re-implemented inline (rather than parameterising
    :func:`._xenium._boundaries_to_wkt`) to keep that function's contract narrow.
    """
    path = _resolve(root, "nucleus_boundaries.parquet",
                    "nucleus_boundaries.csv.gz", "nucleus_boundaries.csv")
    if path is None:
        return None
    try:
        bnd = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    except Exception as exc:  # pragma: no cover
        warnings.warn(f"Failed to read nucleus boundaries ({path.name}): {exc}")
        return None

    id_col = next((c for c in ("cell_id", "cellID", "CellID", "cell_ID") if c in bnd.columns), None)
    if id_col is None or "vertex_x" not in bnd.columns or "vertex_y" not in bnd.columns:
        warnings.warn(
            f"Unexpected columns in {path.name}: {list(bnd.columns)}; expected "
            "`cell_id`, `vertex_x`, `vertex_y`."
        )
        return None
    bnd[id_col] = bnd[id_col].astype(str)
    grouped = bnd.groupby(id_col, sort=False)[["vertex_x", "vertex_y"]]

    def _to_wkt(block: pd.DataFrame) -> str:
        xs = block["vertex_x"].to_numpy()
        ys = block["vertex_y"].to_numpy()
        if len(xs) < 3:
            return ""
        if xs[0] != xs[-1] or ys[0] != ys[-1]:
            xs = np.append(xs, xs[0])
            ys = np.append(ys, ys[0])
        parts = ", ".join(f"{x:.4f} {y:.4f}" for x, y in zip(xs, ys))
        return f"POLYGON (({parts}))"

    wkts = grouped.apply(_to_wkt)
    wkts.index = wkts.index.astype(str)
    return wkts.reindex(cell_index.astype(str)).fillna("")


def _list_atera_morphology_channels(root: Path) -> list[Path]:
    """Atera channel files are ``morphology_focus/chNNNN_<tag>.ome.tif``."""
    focus_dir = root / "morphology_focus"
    if not focus_dir.is_dir():
        return []
    return sorted(focus_dir.glob("ch*.ome.tif"))


def _select_morphology_channel(channels: list[Path], image_key: str) -> Optional[Path]:
    """Resolve ``image_key`` against Atera's descriptive filenames.

    ``image_key`` may be:

    - A semantic tag (``'dapi'``, ``'boundary'``, ``'rna'``, ``'stroma'``).
    - A substring of the filename (case-insensitive), e.g. ``'18s'``,
      ``'alphasma'``, ``'cd45'``.
    - An integer index as a string (``'0'`` … ``'3'``).
    - ``'morphology_focus'`` / ``'morphology'`` — falls back to channel 0 (DAPI).

    Returns the first matching channel path, or ``None`` if nothing matches.
    """
    if not channels:
        return None

    key = image_key.strip().lower()

    # Index-based selection ("0" → channels[0]).
    if key.isdigit():
        idx = int(key)
        if 0 <= idx < len(channels):
            return channels[idx]
        return None

    if key in {"morphology_focus", "morphology", "morphology_mip"}:
        return channels[0]

    # Semantic tag (dapi / boundary / rna / stroma).
    tag_substrings = _ATERA_MORPHOLOGY_TAGS.get(key, [key])
    for cand in channels:
        name = cand.name.lower()
        if any(sub in name for sub in tag_substrings):
            return cand
    return None


def _load_pyramid_tiff(
    path: Path,
    max_dim: int = 4096,
) -> Optional[tuple[np.ndarray, float]]:
    """Load the highest-resolution OME-TIFF pyramid level fitting under ``max_dim``.

    Returns ``(image_array, downsample)`` where ``downsample = chosen_h / full_h``
    so micron coordinates can still be mapped into image-pixel space after
    downsampling. Returns ``None`` when the file is missing or ``tifffile`` is
    unavailable.

    Atera ``morphology_focus/`` channel files cross-reference each other through
    OME XML. tifffile then opens the series in *multi-file* mode and refuses to
    walk the pyramid (``"OME series cannot read multi-file pyramids"``), so we
    pass ``is_ome=False`` to read each file as a standalone TIFF — the per-file
    pyramid IFDs are still exposed via ``series.levels``.
    """
    try:
        import tifffile
    except ImportError:
        warnings.warn(
            "tifffile not installed — skipping image load. "
            "`pip install tifffile` to enable morphology / H&E overlay."
        )
        return None
    try:
        with tifffile.TiffFile(path, is_ome=False) as tif:
            series = tif.series[0]
            levels = getattr(series, "levels", None) or [series]
            full_h, full_w = levels[0].shape[-2:]
            target_idx = 0
            for i, lvl in enumerate(levels):
                h, w = lvl.shape[-2:]
                if max(h, w) <= max_dim:
                    target_idx = i
                    break
            else:
                target_idx = len(levels) - 1
            arr = levels[target_idx].asarray()
        # Strip leading singleton axes (e.g. (1, H, W) or (1, 1, H, W)) without
        # collapsing real RGB channels; H&E is (H, W, 3).
        while arr.ndim > 3:
            arr = arr[0]
        if arr.ndim == 3 and arr.shape[0] in (1, 2, 3, 4) and arr.shape[-1] not in (3, 4):
            # (C, H, W) → (H, W, C) for RGB; otherwise pick channel 0 for stains.
            if arr.shape[0] in (3, 4):
                arr = np.moveaxis(arr, 0, -1)
            else:
                arr = arr[0]
        downsample = arr.shape[0] / full_h if full_h else 1.0
        return arr, float(downsample)
    except Exception as exc:
        warnings.warn(f"Failed to read {path.name}: {exc}")
        return None


def _load_he_alignment(path: Path) -> Optional[np.ndarray]:
    """Read the 3×3 affine matrix from ``*_he_alignment.csv`` (no header).

    The matrix maps **H&E pixel coords (x, y, 1) → Atera spatial (micron) coords**.
    Returned in row-major form; callers invert it when overlaying H&E behind a
    micron-coord scatter.
    """
    try:
        # Atera's alignment CSV has no header — three lines of three floats.
        mat = pd.read_csv(path, header=None).to_numpy(dtype=np.float64)
    except Exception as exc:  # pragma: no cover
        warnings.warn(f"Failed to read H&E alignment {path.name}: {exc}")
        return None
    if mat.shape != (3, 3):
        warnings.warn(
            f"Expected 3×3 affine in {path.name}, got shape {mat.shape}; ignoring."
        )
        return None
    return mat


def _merge_cell_groups(
    adata: AnnData,
    csv_path: Path,
) -> int:
    """Merge an Atera ``*_cell_groups.csv`` (cell_id, group, color) into ``obs``.

    Adds ``obs['cell_group']`` (categorical) and ``obs['cell_group_color']``.
    Returns the number of cells matched (cells absent from the CSV get NaN).
    """
    df = pd.read_csv(csv_path)
    expected = {"cell_id", "group", "color"}
    if not expected.issubset(df.columns):
        warnings.warn(
            f"{csv_path.name} columns {list(df.columns)} do not match expected "
            f"{sorted(expected)}; skipping cell-group merge."
        )
        return 0
    df["cell_id"] = df["cell_id"].astype(str)
    df = df.drop_duplicates("cell_id").set_index("cell_id")
    cells = adata.obs_names.astype(str)
    matched = cells.isin(df.index)
    adata.obs["cell_group"] = pd.Categorical(df["group"].reindex(cells).to_numpy())
    adata.obs["cell_group_color"] = df["color"].reindex(cells).to_numpy()
    return int(matched.sum())


@register_function(
    aliases=["read_atera", "atera", "10x atera", "wta", "wta preview", "读取atera"],
    category="io",
    description=(
        "Read a 10x Genomics Atera (Whole-Transcriptome Atlas Preview) outs bundle. "
        "Mirrors read_xenium plus nucleus polygons, multi-channel morphology "
        "selection, optional H&E image + affine, and optional cell-groups CSV merge."
    ),
    prerequisites={},
    requires={},
    produces={},
    auto_fix="none",
    examples=[
        "adata = ov.io.spatial.read_atera('/path/to/outs/')",
        "adata = ov.io.spatial.read_atera(",
        "    '/path/to/outs/',",
        "    image_key='boundary',  # ATP1A1+CD45+E-Cadherin stain",
        "    cell_groups_csv='/path/to/cell_groups.csv',",
        "    he_image='/path/to/he_image.ome.tif',",
        "    he_alignment_csv='/path/to/he_alignment.csv',",
        ")",
    ],
    related=["io.spatial.read_xenium", "io.spatial.read_visium_hd"],
)
def read_atera(
    path: Union[str, Path],
    *,
    library_id: Optional[str] = None,
    load_image: bool = True,
    image_key: str = "dapi",
    image_max_dim: int = 4096,
    load_boundaries: bool = True,
    load_nucleus_boundaries: bool = True,
    cell_groups_csv: Optional[Union[str, Path]] = None,
    he_image: Optional[Union[str, Path]] = None,
    he_alignment_csv: Optional[Union[str, Path]] = None,
    he_max_dim: int = 4096,
    cache_file: Optional[Union[str, Path]] = None,
) -> AnnData:
    """Read a 10x Atera ``outs`` directory into an AnnData object.

    Atera (WTA Preview) ships an Xenium-compatible bundle plus a nucleus
    polygon file and per-content-named morphology channels:

    .. code-block:: text

        outs/
          cell_feature_matrix.h5
          cells.parquet                          # per-cell metadata + centroids
          cell_boundaries.parquet                # cell polygon vertices
          nucleus_boundaries.parquet             # nucleus polygon vertices (Atera-only)
          experiment.xenium                      # pipeline metadata (JSON)
          morphology.ome.tif                     # full multi-z stack (large)
          morphology_focus/
            ch0000_dapi.ome.tif
            ch0001_atp1a1_cd45_e-cadherin.ome.tif
            ch0002_18s.ome.tif
            ch0003_alphasma_vimentin.ome.tif
          transcripts.parquet                    # not loaded (10 GB+)

    Parameters
    ----------
    path
        The Atera ``outs`` directory.
    library_id
        Key under ``adata.uns['spatial']``. Defaults to ``experiment.xenium``'s
        ``region_name``/``run_name``, else the directory name.
    load_image
        Load a morphology stain (``image_key`` selects which channel).
    image_key
        Channel selector for ``morphology_focus/``: a semantic tag
        (``'dapi'``, ``'boundary'``, ``'rna'``, ``'stroma'``), a filename
        substring (``'cd45'``, ``'18s'``, ``'alphasma'``), or an integer index
        as a string (``'0'`` … ``'3'``). Default ``'dapi'``.
    image_max_dim
        Maximum extent (along either axis) of the loaded morphology pyramid
        level. Default 4096.
    load_boundaries
        When ``True``, ``cell_boundaries.parquet`` → ``obs['geometry']`` (WKT).
    load_nucleus_boundaries
        When ``True``, ``nucleus_boundaries.parquet`` → ``obs['nucleus_geometry']``
        (WKT). Atera-specific; toggle off to save memory.
    cell_groups_csv
        Optional path to Atera's vendor-shipped cell-groups CSV (``cell_id``,
        ``group``, ``color``). When set, merged into ``obs['cell_group']`` and
        ``obs['cell_group_color']``.
    he_image
        Optional H&E OME-TIFF (companion to ``outs/``). When set, loaded into
        ``uns['spatial'][library_id]['images']['he']``.
    he_alignment_csv
        Optional 3×3 affine CSV mapping H&E pixel coords → Atera microns.
        Stored at ``uns['spatial'][library_id]['scalefactors']['he_affine']``.
    he_max_dim
        Maximum extent of the loaded H&E pyramid level. Default 4096.
    cache_file
        Optional ``.h5ad`` cache (read on hit, written on miss).

    Returns
    -------
    AnnData
        - ``X``: CSR sparse, ``int32`` counts (cells × genes)
        - ``obs``: cell metadata (centroids dropped into ``obsm['spatial']``);
          optionally ``geometry``, ``nucleus_geometry``, ``cell_group``,
          ``cell_group_color``
        - ``obsm['spatial']``: ``(n_obs, 2)`` cell centroids in **microns**
        - ``var``: gene panel metadata
        - ``uns['spatial'][library_id]``:
            - ``images['hires']``: morphology channel array (if loaded)
            - ``images['he']``: H&E array (if loaded)
            - ``scalefactors['tissue_hires_scalef']``: ``downsample / pixel_size``
              — micron coords × scalef → image-pixel coords
            - ``scalefactors['spot_diameter_fullres']``: mean cell diameter in
              the loaded image's pixels
            - ``scalefactors['he_affine']``: 3×3 ``np.ndarray`` mapping H&E
              pixel coords → Atera microns (if H&E loaded)
            - ``scalefactors['he_downsample']``: downsample factor of the
              loaded H&E pyramid level (if H&E loaded)
            - ``metadata``: ``experiment.xenium`` contents
            - ``metadata['morphology_channels']``: channel filename list
    """
    root = Path(path).resolve()
    if cache_file is not None:
        cache_path = Path(cache_file).expanduser().resolve()
        if cache_path.exists():
            import anndata as _ad
            _progress(f"Reading cached AnnData from: {cache_path}")
            return _ad.read_h5ad(cache_path)
    else:
        cache_path = None

    _progress(f"Reading Atera data from: {root}")

    mat_path = _resolve(root, "cell_feature_matrix.h5")
    if mat_path is None:
        raise FileNotFoundError(
            f"`cell_feature_matrix.h5` not found in {root}. Pass the directory holding the "
            "Atera outs bundle as `path`."
        )
    cells_path = _resolve(root, "cells.parquet", "cells.csv.gz", "cells.csv")
    if cells_path is None:
        raise FileNotFoundError(f"`cells.parquet` / `cells.csv.gz` not found in {root}.")

    adata = read_10x_h5(str(mat_path))
    if hasattr(adata.var, "columns") and "feature_types" in adata.var.columns:
        gene_mask = adata.var["feature_types"] == "Gene Expression"
        dropped = int((~gene_mask).sum())
        if dropped:
            _progress(
                f"Dropping {dropped} non-Gene-Expression features "
                f"(control probes / codewords) out of {adata.n_vars}"
            )
            adata = adata[:, gene_mask].copy()

    cells = _read_cells_table(cells_path)
    id_col = next(
        (c for c in ("cell_id", "cellID", "CellID", "cell_ID") if c in cells.columns),
        cells.columns[0],
    )
    cells[id_col] = cells[id_col].astype(str)
    cells = cells.set_index(id_col)

    matrix_ids = pd.Index(adata.obs_names.astype(str))
    common = matrix_ids.intersection(cells.index)
    if len(common) != len(matrix_ids):
        warnings.warn(
            f"{len(matrix_ids) - len(common)} cells in cell_feature_matrix.h5 are absent "
            f"from cells metadata and will be dropped."
        )
        adata = adata[adata.obs_names.astype(str).isin(common)].copy()
        matrix_ids = pd.Index(adata.obs_names.astype(str))
    cells = cells.reindex(matrix_ids)

    xy_pairs = [("x_centroid", "y_centroid"), ("CenterX_local_px", "CenterY_local_px")]
    xy = next((pair for pair in xy_pairs if all(c in cells.columns for c in pair)), None)
    if xy is None:
        raise ValueError(
            "Could not find centroid columns in cells metadata. "
            f"Expected one of {xy_pairs}, found {list(cells.columns)}."
        )
    adata.obsm["spatial"] = cells[list(xy)].to_numpy(dtype=np.float32)
    adata.obs = cells.drop(columns=list(xy))

    exp_meta = _load_experiment_metadata(root)
    if library_id is None:
        library_id = (
            exp_meta.get("region_name")
            or exp_meta.get("run_name")
            or root.name
            or "atera"
        )
    library_id = str(library_id).strip() or "atera"

    pixel_size_um = float(exp_meta.get("pixel_size", 0.2125))
    mean_diam_um = 15.0
    if "cell_area" in adata.obs.columns:
        mean_area = float(np.nanmean(adata.obs["cell_area"].to_numpy()))
        if np.isfinite(mean_area) and mean_area > 0:
            mean_diam_um = 2.0 * np.sqrt(mean_area / np.pi)
    spot_diameter_fullres = float(mean_diam_um / pixel_size_um)
    hires_scalef = 1.0 / pixel_size_um

    channels = _list_atera_morphology_channels(root)

    uns_spatial: dict[str, Any] = {
        "images": {},
        "scalefactors": {
            "tissue_hires_scalef": hires_scalef,
            "spot_diameter_fullres": spot_diameter_fullres,
        },
        "metadata": dict(exp_meta),
    }
    uns_spatial["metadata"]["morphology_channels"] = [c.name for c in channels]

    if load_image:
        chosen = _select_morphology_channel(channels, image_key)
        if chosen is None:
            _progress(
                f"No morphology channel matched image_key={image_key!r}; "
                f"available: {[c.name for c in channels]}",
                level="warn",
            )
        else:
            loaded = _load_pyramid_tiff(chosen, max_dim=image_max_dim)
            if loaded is not None:
                img, downsample = loaded
                _progress(
                    f"Loaded morphology channel {chosen.name} {img.shape} "
                    f"(downsample {downsample:.4f})"
                )
                uns_spatial["images"]["hires"] = img
                uns_spatial["scalefactors"]["tissue_hires_scalef"] = hires_scalef * downsample
                uns_spatial["scalefactors"]["spot_diameter_fullres"] = (
                    spot_diameter_fullres * downsample
                )
                uns_spatial["scalefactors"]["morphology_channel"] = chosen.name

    has_geometry = False
    if load_boundaries:
        wkts = _boundaries_to_wkt(root, cell_index=pd.Index(adata.obs_names.astype(str)))
        if wkts is not None:
            adata.obs["geometry"] = wkts.values
            has_geometry = bool((wkts != "").any())
            if has_geometry:
                _progress(
                    f"Loaded cell polygons for {int((wkts != '').sum())}/{len(wkts)} cells"
                )

    if load_nucleus_boundaries:
        nwkts = _nucleus_boundaries_to_wkt(
            root, cell_index=pd.Index(adata.obs_names.astype(str))
        )
        if nwkts is not None:
            adata.obs["nucleus_geometry"] = nwkts.values
            n_nuc = int((nwkts != "").sum())
            if n_nuc:
                _progress(f"Loaded nucleus polygons for {n_nuc}/{len(nwkts)} cells")

    if cell_groups_csv is not None:
        cg_path = Path(cell_groups_csv).expanduser().resolve()
        if cg_path.exists():
            n_matched = _merge_cell_groups(adata, cg_path)
            _progress(
                f"Merged cell_groups: {n_matched}/{adata.n_obs} cells from {cg_path.name}"
            )
        else:
            warnings.warn(f"cell_groups_csv not found: {cg_path}")

    if he_image is not None:
        he_path = Path(he_image).expanduser().resolve()
        if not he_path.exists():
            warnings.warn(f"he_image not found: {he_path}")
        else:
            loaded = _load_pyramid_tiff(he_path, max_dim=he_max_dim)
            if loaded is not None:
                he_arr, he_downsample = loaded
                _progress(
                    f"Loaded H&E image {he_arr.shape} (downsample {he_downsample:.4f}) "
                    f"from {he_path.name}"
                )
                uns_spatial["images"]["he"] = he_arr
                uns_spatial["scalefactors"]["he_downsample"] = he_downsample
                if he_alignment_csv is not None:
                    align_path = Path(he_alignment_csv).expanduser().resolve()
                    if align_path.exists():
                        affine = _load_he_alignment(align_path)
                        if affine is not None:
                            uns_spatial["scalefactors"]["he_affine"] = affine
                            _progress(f"Loaded H&E affine from {align_path.name}")
                    else:
                        warnings.warn(f"he_alignment_csv not found: {align_path}")

    adata.uns["spatial"] = {library_id: uns_spatial}
    adata.uns["omicverse_io"] = {
        "type": "atera_seg" if has_geometry else "atera",
        "library_id": library_id,
    }

    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            adata.write(cache_path)
            _progress(f"Wrote cache AnnData to: {cache_path}", level="success")
        except Exception as exc:
            warnings.warn(f"Failed to write cache {cache_path}: {exc}")

    _progress(
        f"Done (n_obs={adata.n_obs}, n_vars={adata.n_vars}, library_id={library_id})",
        level="success",
    )
    return adata


__all__ = ["read_atera"]
