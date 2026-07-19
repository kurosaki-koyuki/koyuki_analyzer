import numpy as np
import torch
from torch.utils.data import Dataset, IterableDataset


def _prep_graph(graph_, graph_n_epochs):
    """Filter weak edges and return (head, tail, weight, graph_n_epochs).

    graph_n_epochs controls the cutoff (matches umap-learn / Sainburg pumap):
    edges with weight < max_weight / graph_n_epochs are dropped.
    """
    graph = graph_.tocoo()
    graph.sum_duplicates()
    if graph_n_epochs is None:
        graph_n_epochs = 500 if graph.shape[0] <= 10000 else 200
    cutoff = graph.data.max() / float(graph_n_epochs)
    keep = graph.data >= cutoff
    head = graph.row[keep].astype(np.int64, copy=False)
    tail = graph.col[keep].astype(np.int64, copy=False)
    weight = graph.data[keep].astype(np.float32, copy=False)
    return head, tail, weight, graph_n_epochs


class StreamingUMAPDataset(IterableDataset):
    """On-the-fly weighted edge sampler for parametric UMAP.

    Replaces the previous map-style UMAPDataset that expanded the edge list
    via np.repeat(head, epochs_per_sample) — at 1M cells x k=15 x n_epochs=200
    that allocation alone is ~14 GB of int64 in CPU RAM. This class samples
    edges per batch using a cached cumulative-weight table (O(num_edges)
    memory) and yields already-batched feature tensors.

    Pair with DataLoader(batch_size=None, shuffle=False).
    """

    def __init__(
        self,
        data,
        graph_=None,
        batch_size=512,
        graph_n_epochs=None,
        seed=None,
        pin_memory=False,
        device=None,
        negative_sample_rate=5,
        gpu_coo=None,
    ):
        # Two ways to specify the fuzzy graph:
        #   1) graph_ : scipy.sparse matrix (legacy CPU-built path)
        #   2) gpu_coo: (rows, cols, vals, n_vertices) torch tensors on GPU
        #               -- skips the scipy round-trip, set by get_umap_graph_gpu
        if gpu_coo is not None:
            head_t, tail_t, weight_t, n_vertices = gpu_coo
            if graph_n_epochs is None:
                graph_n_epochs = 500 if n_vertices <= 10000 else 200
            cutoff = weight_t.max() / float(graph_n_epochs)
            keep = weight_t >= cutoff
            head_t = head_t[keep].to(torch.long)
            tail_t = tail_t[keep].to(torch.long)
            weight_t = weight_t[keep].to(torch.float32)
            head_np = None  # signal that head/tail/weight already on target device
            self._gpu_coo_n_vertices = n_vertices
            self._gpu_coo_tensors = (head_t, tail_t, weight_t)
        else:
            head, tail, weight, graph_n_epochs = _prep_graph(graph_, graph_n_epochs)
            head_np = (head, tail, weight)
            self._gpu_coo_n_vertices = None
            self._gpu_coo_tensors = None

        self.batch_size = int(batch_size)
        self.graph_n_epochs = int(graph_n_epochs)
        self.negative_sample_rate = int(negative_sample_rate)

        # Resolve target device. Putting data + sampling tables on GPU removes
        # the per-batch CPU->GPU copy and host-side gather, which dominate
        # training wall time at 1M+ cells.
        if device is None:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        elif isinstance(device, str):
            device = torch.device(device)
        self.device = device

        if isinstance(data, torch.Tensor):
            data_t = data.detach().contiguous()
        else:
            data_t = torch.as_tensor(np.ascontiguousarray(data), dtype=torch.float32)
        if data_t.dtype != torch.float32:
            data_t = data_t.float()
        if device.type == "cpu" and pin_memory and torch.cuda.is_available():
            data_t = data_t.pin_memory()
        self.data = data_t.to(device, non_blocking=True)

        if self._gpu_coo_tensors is not None:
            head_t, tail_t, weight_t = self._gpu_coo_tensors
            self.head = head_t.to(device, non_blocking=True)
            self.tail = tail_t.to(device, non_blocking=True)
            self._cum = torch.cumsum(weight_t.to(torch.float64), dim=0).to(device, non_blocking=True)
        else:
            head, tail, weight = head_np
            self.head = torch.from_numpy(head).to(device, non_blocking=True)
            self.tail = torch.from_numpy(tail).to(device, non_blocking=True)
            # Keep cum as fp64 on the sampling device for numerical stability of
            # searchsorted across millions of edges.
            self._cum = torch.cumsum(torch.from_numpy(weight).double(), dim=0).to(device, non_blocking=True)
        self._total_weight = float(self._cum[-1].item())

        # One epoch covers every fuzzy edge (in expectation) graph_n_epochs
        # times, matching umap-learn's edge-SGD semantics. Total samples per
        # epoch = graph_n_epochs * sum(weight); n_batches = total / batch_size.
        total_per_epoch = int(np.ceil(self.graph_n_epochs * self._total_weight))
        self.num_batches = max(1, total_per_epoch // self.batch_size)
        self._base_seed = seed

    def __len__(self):
        return self.num_batches

    def __iter__(self):
        worker = torch.utils.data.get_worker_info()
        if self._base_seed is None:
            base = int(torch.empty((), dtype=torch.int64).random_().item())
        else:
            base = int(self._base_seed)
        worker_id = 0 if worker is None else worker.id
        num_workers = 1 if worker is None else worker.num_workers
        # Generator must live on the same device as the tensors it draws into,
        # otherwise torch.rand(generator=...) raises.
        rng = torch.Generator(device=self.device)
        rng.manual_seed(base + worker_id)

        n_batches = self.num_batches // num_workers
        if worker_id < (self.num_batches % num_workers):
            n_batches += 1

        cum = self._cum
        total = self._total_weight
        head = self.head
        tail = self.tail
        data = self.data
        bs = self.batch_size
        device = self.device
        neg_rate = self.negative_sample_rate
        n_vertices = data.shape[0]
        n_edges_minus_one = head.numel() - 1
        neg_total = bs * neg_rate

        for _ in range(n_batches):
            u = torch.rand(bs, generator=rng, dtype=torch.float64, device=device) * total
            idx = torch.searchsorted(cum, u).clamp_(max=n_edges_minus_one)
            if neg_rate <= 0:
                # Legacy 2-tuple path; loss does in-batch shuffle for negatives.
                yield data[head[idx]], data[tail[idx]]
            else:
                # Negatives: uniform random vertex indices across the full
                # dataset (matches umap-learn's nonparametric SGD semantics).
                neg = torch.randint(0, n_vertices, (neg_total,), generator=rng, device=device)
                yield data[head[idx]], data[tail[idx]], data[neg]


class MatchDataset(Dataset):
    """Map-style dataset for the match_nonparametric_umap pathway (unchanged)."""

    def __init__(self, data, embeddings):
        self.embeddings = torch.as_tensor(embeddings, dtype=torch.float32)
        if isinstance(data, torch.Tensor):
            self.data = data.detach().cpu()
        else:
            self.data = torch.as_tensor(np.ascontiguousarray(data), dtype=torch.float32)

    def __len__(self):
        return int(self.data.shape[0])

    def __getitem__(self, index):
        return self.data[index], self.embeddings[index]


def get_graph_elements(graph_, n_epochs):
    """Back-compat shim. Returns the same tuple shape as the old version but
    no longer materializes np.repeat(head, epochs_per_sample) — callers should
    prefer StreamingUMAPDataset, which never expands the edge list."""
    head, tail, weight, n_epochs = _prep_graph(graph_, n_epochs)
    epochs_per_sample = (n_epochs * weight).astype(np.float64)
    return graph_.tocoo(), epochs_per_sample, head, tail, weight, graph_.shape[0]


# Back-compat alias.
UMAPDataset = StreamingUMAPDataset
