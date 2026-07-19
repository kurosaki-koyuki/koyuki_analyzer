from __future__ import annotations

import logging
from pathlib import Path

from ._config import GenerateLdscoreConfig
from ._style import Colors, EMOJI

logger = logging.getLogger(__name__)


def _ensure_symlink(link_path: Path, target_path: Path) -> None:
    """Create a symlink when missing and validate existing links."""

    if link_path.exists():
        if link_path.is_symlink() and link_path.resolve() == target_path.resolve():
            return
        if link_path.resolve() == target_path.resolve():
            return
        raise FileExistsError(f"{link_path} already exists and does not point to {target_path}.")

    link_path.symlink_to(target_path, target_is_directory=True)


def run_generate_ldscore(config: GenerateLdscoreConfig) -> Path:
    """Run the supported gsMap ldscore workflow and return the output directory."""

    ldscore_save_dir = config.ldscore_save_dir
    ldscore_save_dir.mkdir(parents=True, exist_ok=True)

    if config.ldscore_save_format == "quick_mode":
        print(
            f"{EMOJI['start']} {Colors.CYAN}Running gsMap generate_ldscore in quick_mode "
            f"with precomputed resources.{Colors.ENDC}"
        )
        baseline_dir = ldscore_save_dir / "baseline"
        snp_gene_pair_dir = ldscore_save_dir / "SNP_gene_pair"

        _ensure_symlink(baseline_dir, Path(config.baseline_annotation_dir))
        _ensure_symlink(snp_gene_pair_dir, Path(config.snp_gene_pair_dir))

        done_path = ldscore_save_dir / f"{config.sample_name}_generate_ldscore.done"
        done_path.touch(exist_ok=True)
        return ldscore_save_dir

    raise ImportError(
        "Full generate_ldscore mode requires pyranges and the upstream gsMap "
        "LD-score calculation stack, which are not available in this OmicVerse integration yet."
    )
