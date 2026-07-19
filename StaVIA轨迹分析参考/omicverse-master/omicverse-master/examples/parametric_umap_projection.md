# Parametric UMAP — project new data onto a reference embedding

`ov.pp.umap(adata, method='pumap')` fits a **parametric UMAP**: besides the 2-D
embedding, it learns the *mapping rule* (a small neural-network encoder) from
the high-dimensional representation to the embedding. That rule can then be
**reused to place new cells onto the same UMAP** — the atlas / reference-mapping
use case.

> When do you want this? Atlas building, or any workflow where new samples must
> land in the **same** embedding as a reference. For a one-off pipeline (no new
> data to add), the default non-parametric UMAP is simpler and faster — just use
> `ov.pp.umap(adata)`.

The key idea: the model maps a fixed input representation → 2-D. So new data
must arrive in **exactly the representation the model was trained on** (same
genes, same scaling, same PCA). The cleanest way to guarantee that is to keep a
single PCA object fitted on the reference and reuse it for the query.

## 1. Fit on the reference and keep the model

```python
import numpy as np
import scanpy as sc
from sklearn.decomposition import PCA
import omicverse as ov

# --- reference preprocessing ---
ref = sc.datasets.pbmc3k()
sc.pp.normalize_total(ref, target_sum=1e4); sc.pp.log1p(ref)
sc.pp.highly_variable_genes(ref, n_top_genes=2000)
ref = ref[:, ref.var.highly_variable].copy()
sc.pp.scale(ref, max_value=10)

# one PCA object fitted on the reference (its .transform reuses the
# reference mean + components — that is what makes query projection correct)
ref_pca = PCA(n_components=50, random_state=0).fit(np.asarray(ref.X))
ref.obsm['X_pca'] = ref_pca.transform(np.asarray(ref.X)).astype('float32')

ov.pp.neighbors(ref, n_neighbors=15, use_rep='X_pca')

# fit parametric UMAP — RETURNS the model; ref.obsm['X_umap'] is also written
model = ov.pp.umap(ref, method='pumap')
```

## 2. Bring new data into the **same feature space**

Process the query identically, align it to the **reference genes**, scale it,
then project with the **reference PCA** (do not refit PCA on the query):

```python
qry = sc.datasets.pbmc3k()                 # your new sample(s)
sc.pp.normalize_total(qry, target_sum=1e4); sc.pp.log1p(qry)
qry = qry[:, ref.var_names].copy()         # same genes, same order
sc.pp.scale(qry, max_value=10)

qry_pca = ref_pca.transform(np.asarray(qry.X)).astype('float32')  # reference PCA
```

## 3. Generate the new embedding through the model

```python
new_embedding = model.transform(qry_pca)   # (n_query, 2)
qry.obsm['X_umap'] = new_embedding

# the query now lies in the SAME embedding as the reference
ov.pl.embedding(qry, basis='X_umap', color='your_label')
```

`model.transform` is deterministic — the same model + input always gives the
same coordinates.

## 4. Save / reuse the model

```python
model.save('pbmc_reference_pumap.pkl')
model = ov.pp.load_pumap('pbmc_reference_pumap.pkl')
emb = model.transform(another_query_pca.astype('float32'))
```

## Choosing the UMAP backend

| call | backend | use it for |
|---|---|---|
| `ov.pp.umap(adata)` (mode `cpu`) | scanpy / umap-learn (CPU) | default, exact scanpy result |
| `ov.pp.umap(adata)` (mode `cpu-gpu-mixed`) | non-parametric GPU UMAP | same result as scanpy, GPU-accelerated |
| `ov.pp.umap(adata, method='pumap')` | **parametric UMAP** | atlas / projecting new data (this tutorial) |

`method='pumap'` requires a GPU and `torch`.
