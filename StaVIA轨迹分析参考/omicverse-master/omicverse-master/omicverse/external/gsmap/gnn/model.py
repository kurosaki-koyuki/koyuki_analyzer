from __future__ import annotations

"""GAT model used by the vendored gsMap latent-representation workflow."""

try:
    import torch
    from torch import nn
    import torch.nn.functional as F
    from torch_geometric.nn import GATConv
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

    class _DummyModule:
        """Placeholder so class definitions stay syntactically valid when torch is absent."""
        pass

    nn = type("DummyNN", (), {
        "Module": _DummyModule,
        "Sequential": _DummyModule,
        "Linear": _DummyModule,
        "BatchNorm1d": _DummyModule,
        "ELU": _DummyModule,
        "Dropout": _DummyModule,
    })()
    F = None
    GATConv = _DummyModule


def full_block(in_features: int, out_features: int, p_drop: float) -> nn.Sequential:
    """Build one dense block used by the encoder, decoder, and classifier."""

    return nn.Sequential(
        nn.Linear(in_features, out_features),
        nn.BatchNorm1d(out_features),
        nn.ELU(),
        nn.Dropout(p=p_drop),
    )


class gat_model(nn.Module):
    """Graph attention autoencoder used by gsMap latent learning."""

    def __init__(self, input_dim: int, params, num_classes: int = 1) -> None:
        if not _TORCH_AVAILABLE:
            raise ImportError(
                "torch and torch-geometric are required for gsMap. "
                "Install with: pip install omicverse[gsmap]"
            )
        super().__init__()
        self.var = params.var
        self.num_classes = num_classes
        self.params = params

        self.encoder = nn.Sequential(
            full_block(input_dim, params.feat_hidden1, params.p_drop),
            full_block(params.feat_hidden1, params.feat_hidden2, params.p_drop),
        )

        self.gat1 = GATConv(
            in_channels=params.feat_hidden2,
            out_channels=params.gat_hidden1,
            heads=params.nheads,
            dropout=params.p_drop,
        )
        self.gat2 = GATConv(
            in_channels=params.gat_hidden1 * params.nheads,
            out_channels=params.gat_hidden2,
            heads=1,
            concat=False,
            dropout=params.p_drop,
        )
        if self.var:
            self.gat3 = GATConv(
                in_channels=params.gat_hidden1 * params.nheads,
                out_channels=params.gat_hidden2,
                heads=1,
                concat=False,
                dropout=params.p_drop,
            )

        self.decoder = nn.Sequential(
            full_block(params.gat_hidden2, params.feat_hidden2, params.p_drop),
            full_block(params.feat_hidden2, params.feat_hidden1, params.p_drop),
            nn.Linear(params.feat_hidden1, input_dim),
        )

        self.cluster = nn.Sequential(
            full_block(params.gat_hidden2, params.feat_hidden2, params.p_drop),
            nn.Linear(params.feat_hidden2, self.num_classes),
        )

    def encode(self, x: torch.Tensor, edge_index: torch.Tensor):
        """Encode node features into the latent graph-attention space."""

        x = self.encoder(x)
        x = self.gat1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=self.params.p_drop, training=self.training)

        mu = self.gat2(x, edge_index)
        if self.var:
            logvar = self.gat3(x, edge_index)
            return mu, logvar
        return mu, None

    def reparameterize(self, mu: torch.Tensor, logvar: torch.Tensor | None) -> torch.Tensor:
        """Sample the latent variable when a variance head is enabled."""

        if self.training and logvar is not None:
            std = torch.exp(0.5 * logvar)
            eps = torch.randn_like(std)
            return eps * std + mu
        return mu

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor):
        """Run the encoder, latent sampler, decoder, and classifier heads."""

        mu, logvar = self.encode(x, edge_index)
        z = self.reparameterize(mu, logvar)
        x_reconstructed = self.decoder(z)
        pred_label = self.cluster(z)
        return pred_label, x_reconstructed, z, mu, logvar
