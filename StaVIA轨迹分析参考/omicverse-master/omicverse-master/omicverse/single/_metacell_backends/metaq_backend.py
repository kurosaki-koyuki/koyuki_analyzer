"""MetaQ backend (Li et al., Nat Commun 2025)."""

from __future__ import annotations

import time
from typing import List, Optional

import numpy as np
from scipy import sparse


from .base import FitResult, MetaCellBackend


class MetaQBackend(MetaCellBackend):
    name = "metaq"
    capabilities = {"soft", "latent", "codebook", "out_of_sample", "multimodal", "streaming"}

    def __init__(
        self,
        adata,
        n_metacells: Optional[int] = None,
        layer: Optional[str] = None,
        device: str = "cpu",
        random_state: int = 0,
        entry_dim: int = 32,
        codebook_init: str = "random",
        train_epoch: int = 300,
        batch_size: int = 512,
        converge_threshold: int = 10,
        data_types: Optional[List[str]] = None,    # e.g. ['RNA']; 'ADT'/'ATAC' allowed
        warm_epochs: int = 30,
        verbose: bool = False,
        **kwargs,
    ):
        self.adata = adata
        self.n_metacells = n_metacells or (adata.n_obs // 75)
        self.layer = layer
        self.device = device
        self.random_state = random_state
        self.entry_dim = entry_dim
        self.codebook_init = {"random": "Random", "kmeans": "Kmeans", "geometric": "Geometric"}.get(
            str(codebook_init).lower(), codebook_init
        )
        self.train_epoch = int(train_epoch)
        self.batch_size = int(batch_size)
        self.converge_threshold = int(converge_threshold)
        self.warm_epochs = int(warm_epochs)
        self.verbose = verbose
        self.data_types = list(data_types) if data_types else ["RNA"]
        self._extra = kwargs

        self.model = None
        self._preprocess_stats: dict = {}
        self._embeds: Optional[np.ndarray] = None
        self._delta_confs: Optional[np.ndarray] = None
        self._assignments: Optional[np.ndarray] = None

    # ----- internals --------------------------------------------------------

    def _prep_one_omic(self, ad, data_type):
        from ...external.MetaQ import preprocess
        x, sf, raw, ad_post = preprocess(ad.copy(), data_type)
        return x.astype(np.float32), sf.astype(np.float32), raw.astype(np.float32), ad_post

    def _to_dense(self, X):
        if sparse.issparse(X):
            return np.asarray(X.todense())
        return np.asarray(X)

    def _build_dataloaders(self):
        import torch
        from torch.utils.data import DataLoader
        from ...external.MetaQ import MetaQDataset

        n_obs = self.adata.n_obs
        # MetaQ requires raw counts in adata.X. Use specified layer or .X.
        if self.layer is not None and self.layer in self.adata.layers:
            X = self._to_dense(self.adata.layers[self.layer])
        else:
            X = self._to_dense(self.adata.X)
        ad = self.adata.copy()
        ad.X = X
        x, sf, raw, ad_post = self._prep_one_omic(ad, self.data_types[0])

        self._preprocess_stats = {
            "input_dim": int(x.shape[1]),
            "var_index": ad_post.var_names.to_list(),
            "data_type": self.data_types[0],
        }

        bs = self.batch_size
        if self.n_metacells > 1000 and bs <= 512:
            bs = 4096
        # Tiny-dataset safety: don't drop_last when batch >= n_obs.
        n_obs = x.shape[0]
        if bs >= n_obs:
            bs = max(2, n_obs // 4)
        ds = MetaQDataset([x], [sf], [raw])
        drop_last = n_obs > bs * 2
        dl_train = DataLoader(ds, batch_size=bs, shuffle=True,
                              drop_last=drop_last, num_workers=0)
        dl_eval = DataLoader(ds, batch_size=bs * 4, shuffle=False,
                             drop_last=False, num_workers=0)
        return dl_train, dl_eval, [int(x.shape[1])]

    # ----- fit --------------------------------------------------------------

    def fit(self, n_metacells: Optional[int] = None, **kwargs) -> FitResult:
        import torch
        from ...external.MetaQ import MetaQ, train_one_epoch, warm_one_epoch, inference

        if n_metacells is not None:
            self.n_metacells = n_metacells

        torch.manual_seed(self.random_state)
        np.random.seed(self.random_state)

        device = torch.device(self.device if torch.cuda.is_available() or self.device == "cpu" else "cpu")

        dl_train, dl_eval, input_dims = self._build_dataloaders()

        net = MetaQ(
            input_dims=input_dims,
            data_types=self.data_types,
            entry_num=self.n_metacells,
            entry_dim=self.entry_dim,
        ).to(device)

        # Warmup
        opt = torch.optim.Adam(net.parameters(), lr=1e-3)
        t0 = time.time()
        for ep in range(self.warm_epochs):
            warm_one_epoch(net, self.data_types, dl_train, opt, ep, device)

        # Codebook init from current encoder embeddings.
        with torch.no_grad():
            net.eval()
            z_init = []
            for data in dl_eval:
                x_list = [data["x"][0].to(device)]
                z_init.append(net(x_list)[0].cpu().numpy())
            z_init = np.concatenate(z_init, axis=0)
        net.quantizer.init_codebook(z_init, self.codebook_init)
        net.copy_decoder_q()

        # Main training with VQ.
        opt = torch.optim.Adam(net.parameters(), lr=1e-3)
        loss_hist: list[tuple[float, float]] = []
        converged_at = None
        for ep in range(self.train_epoch):
            loss_rec_q, loss_c = train_one_epoch(net, self.data_types, dl_train, opt, ep, device)
            loss_hist.append((float(loss_rec_q), float(loss_c)))
            if len(loss_hist) > self.converge_threshold:
                recent = np.array(loss_hist[-self.converge_threshold:])
                deltas = np.abs(np.diff(recent, axis=0)).max(axis=0)
                if deltas.max() < 1e-5:
                    converged_at = ep + 1
                    break
        runtime = time.time() - t0
        self.model = net

        embeds, ids, delta_confs, rec_q_percent, loss_c_all = inference(
            net, self.data_types, dl_eval, device
        )
        self._embeds = embeds
        self._delta_confs = delta_confs
        self._assignments = ids.astype(np.int64)

        return FitResult(
            assignments=self._assignments,
            soft=self.soft_membership(),
            latent=embeds,
            codebook=net.quantizer.entry.weight.detach().cpu().numpy(),
            n_iter=converged_at or self.train_epoch,
            converged=converged_at is not None,
            runtime_s=float(runtime),
            backend_meta={"loss_hist": loss_hist, "rec_q_percent": float(rec_q_percent)},
        )

    # ----- capability methods ----------------------------------------------

    def soft_membership(self, top_k: int = 5) -> sparse.csr_matrix:
        """Top-k softmax(cosine) similarity between cell latent and codebook."""
        if self.model is None or self._embeds is None:
            raise RuntimeError("Call .fit() first.")
        import torch
        z = torch.from_numpy(self._embeds).float()
        cb = self.model.quantizer.entry.weight.detach().cpu().float()
        z = z / z.norm(dim=1, keepdim=True).clamp(min=1e-12)
        cb = cb / cb.norm(dim=1, keepdim=True).clamp(min=1e-12)
        sim = z @ cb.t()                            # (n_cells, n_mc)
        vals, idx = sim.topk(min(top_k, sim.shape[1]), dim=1)
        soft = torch.softmax(vals, dim=1)
        n, m = sim.shape
        rows = np.repeat(np.arange(n), soft.shape[1])
        cols = idx.numpy().ravel()
        data = soft.numpy().ravel()
        return sparse.csr_matrix((data, (rows, cols)), shape=(n, m))

    def latent(self) -> np.ndarray:
        if self._embeds is None:
            raise RuntimeError("Call .fit() first.")
        return self._embeds

    def codebook(self) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Call .fit() first.")
        return self.model.quantizer.entry.weight.detach().cpu().numpy()

    def assign_new_cells(self, adata_query) -> dict:
        if self.model is None:
            raise RuntimeError("Call .fit() first.")
        import torch
        # Re-use the *exact* gene set the encoder was trained on (re-doing
        # HVG selection on the query would produce a different feature axis).
        var_index = self._preprocess_stats.get("var_index")
        ad = adata_query.copy()
        if var_index is not None:
            common = [g for g in var_index if g in ad.var_names]
            if not common:
                raise ValueError(
                    "adata_query shares no gene names with the trained encoder; "
                    "check var_names match the original training adata."
                )
            ad = ad[:, common].copy()
            # Pad missing genes with zeros so the feature axis matches exactly.
            if len(common) < len(var_index):
                import scipy.sparse as sp
                missing = [g for g in var_index if g not in set(common)]
                pad = sp.csr_matrix((ad.n_obs, len(missing)))
                import anndata as _ad
                ad = _ad.concat(
                    [ad, _ad.AnnData(X=pad, var=pd.DataFrame(index=missing),
                                     obs=ad.obs.copy())],
                    axis=1, merge="first",
                )[:, var_index]
            else:
                ad = ad[:, var_index]
        # Light normalisation matching upstream preprocess (normalize_total +
        # log1p + scale) but with the FIXED gene set rather than HVG re-pick.
        if sparse.issparse(ad.X):
            X = np.asarray(ad.X.todense())
        else:
            X = np.asarray(ad.X)
        sf = X.sum(axis=1).reshape(-1, 1) / 1e4
        sf[sf == 0] = 1.0
        X_norm = X / sf * 1e4
        X_log = np.log1p(X_norm).astype(np.float32)
        mean = X_log.mean(axis=0)
        std = X_log.std(axis=0) + 1e-8
        x = np.clip((X_log - mean) / std, -10, 10).astype(np.float32)

        device = next(self.model.parameters()).device
        with torch.no_grad():
            self.model.eval()
            x_t = torch.from_numpy(x).float().to(device)
            z = self.model.encoders[0](x_t)
            id_, delta_conf, _ = self.model.quantizer(z, return_assignment=True)
        return {
            "metacell_id": id_.cpu().numpy().astype(np.int64),
            "confidence": delta_conf.cpu().numpy(),
            "embedding": z.cpu().numpy(),
        }

    # ----- persistence -------------------------------------------------------

    def save(self, path: str) -> None:
        if self.model is None:
            raise RuntimeError("Call .fit() first.")
        import torch
        torch.save(
            {
                "encoder_state": [enc.state_dict() for enc in self.model.encoders],
                "quantizer_state": self.model.quantizer.state_dict(),
                "decoder_state": [dec.state_dict() for dec in self.model.decoders],
                "decoder_q_state": [dec.state_dict() for dec in self.model.decoders_q],
                "config": {
                    "n_metacells": self.n_metacells,
                    "entry_dim": self.entry_dim,
                    "data_types": self.data_types,
                    "input_dims": [self._preprocess_stats.get("input_dim")],
                },
                "preprocess_stats": self._preprocess_stats,
                "embeds": self._embeds,
                "assignments": self._assignments,
                "delta_confs": self._delta_confs,
            },
            path,
        )

    def load(self, path: str) -> None:
        from ...external.MetaQ import MetaQ
        import torch
        state = torch.load(path, map_location="cpu", weights_only=False)
        cfg = state["config"]
        self.n_metacells = cfg["n_metacells"]
        self.entry_dim = cfg["entry_dim"]
        self.data_types = cfg["data_types"]
        self.model = MetaQ(
            input_dims=cfg["input_dims"],
            data_types=cfg["data_types"],
            entry_num=cfg["n_metacells"],
            entry_dim=cfg["entry_dim"],
        )
        for enc, sd in zip(self.model.encoders, state["encoder_state"]):
            enc.load_state_dict(sd)
        self.model.quantizer.load_state_dict(state["quantizer_state"])
        for dec, sd in zip(self.model.decoders, state["decoder_state"]):
            dec.load_state_dict(sd)
        for dec, sd in zip(self.model.decoders_q, state["decoder_q_state"]):
            dec.load_state_dict(sd)
        self._preprocess_stats = state["preprocess_stats"]
        self._embeds = state["embeds"]
        self._assignments = state["assignments"]
        self._delta_confs = state["delta_confs"]
