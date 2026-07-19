# iStar — vendored copy

Source: https://github.com/daviddaiweizhang/istar (commit master)
Paper:  Zhang et al., Inferring super-resolution tissue architecture by
        integrating spatial transcriptomics with histology, Nature
        Biotechnology, 2024. https://doi.org/10.1038/s41587-023-02019-9
License: GPL-3.0 (see ``LICENSE`` in this directory).

This source tree is vendored verbatim and wrapped by
``omicverse.space.histo._istar`` to provide a pythonic API for
super-resolving paired Visium + H&E samples. The original ``run.sh`` and
all python entry points are preserved unchanged.

**Commercial use:** the upstream README states that commercial use requires
contacting the iStar authors (daiwei.zhang@pennmedicine.upenn.edu). The
vendored copy is provided for research and educational purposes; consult
the upstream maintainers before any commercial deployment.

**HIPT checkpoints** are not vendored; ``omicverse.space.histo`` downloads
them on first use via ``download_checkpoints.sh`` into the user-level
cache directory.
