from __future__ import annotations

"""Training helpers for the vendored gsMap graph attention model."""

import logging
import time

try:
    import torch
    import torch.nn.functional as F
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
from tqdm.auto import tqdm

from .._style import Colors, EMOJI
from .model import gat_model

logger = logging.getLogger(__name__)


def reconstruction_loss(decoded: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
    """Compute the reconstruction loss for the autoencoder output."""

    return F.mse_loss(decoded, x)


def label_loss(pred_label: torch.Tensor, true_label: torch.Tensor) -> torch.Tensor:
    """Compute the supervised classification loss when annotations exist."""

    return F.cross_entropy(pred_label, true_label.long())


class model_trainer:
    """Train the vendored gsMap graph attention autoencoder."""

    def __init__(self, node_x, graph_dict, params, label=None) -> None:
        if not _TORCH_AVAILABLE:
            raise ImportError(
                "torch and torch-geometric are required for gsMap. "
                "Install with: pip install omicverse[gsmap]"
            )
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.params = params
        self.epochs = params.epochs
        self.node_x = torch.FloatTensor(node_x).to(self.device)
        self.adj_norm = graph_dict["adj_norm"].to(self.device).coalesce()
        self.label = label
        self.num_classes = 1

        if self.label is not None:
            self.label = torch.tensor(self.label).to(self.device)
            self.num_classes = len(torch.unique(self.label))

        self.model = gat_model(self.params.feat_cell, self.params, self.num_classes).to(
            self.device
        )
        self.optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.params.gat_lr,
            weight_decay=self.params.gcn_decay,
        )

    def run_train(self) -> None:
        """Train until convergence threshold or max epochs."""

        self.model.train()
        prev_loss = float("inf")
        print(f"{EMOJI['start']} {Colors.CYAN}Begin GAT-AE model training{Colors.ENDC}")
        progress = tqdm(range(self.epochs), desc="GAT-AE model train:", leave=True)
        for epoch in range(self.epochs):
            start_time = time.time()
            self.optimizer.zero_grad()
            pred_label, decoded, _, _, _ = self.model(self.node_x, self.adj_norm)
            loss_rec = reconstruction_loss(decoded, self.node_x)

            if self.label is not None:
                loss_pre = label_loss(pred_label, self.label)
                loss = self.params.rec_w * loss_rec + self.params.label_w * loss_pre
            else:
                loss = loss_rec

            loss.backward()
            self.optimizer.step()

            batch_time = time.time() - start_time
            left_time = batch_time * (self.epochs - epoch - 1) / 60
            progress.set_postfix(
                {"left_time": f"{left_time:.2f} mins", "loss": f"{loss.item():.4f}"}
            )
            progress.update(1)

            if abs(loss.item() - prev_loss) <= self.params.convergence_threshold and epoch >= 200:
                progress.close()
                tqdm.write(
                    f"{EMOJI['done']} {Colors.GREEN}Convergence reached at epoch "
                    f"{epoch + 1}/{self.epochs} (loss={loss.item():.4f}). Training stopped.{Colors.ENDC}"
                )
                logger.info("Convergence reached. Training stopped.")
                break

            prev_loss = loss.item()
        else:
            progress.close()
            tqdm.write(f"Max epochs reached ({self.epochs}). Training stopped.")
            logger.info("Max epochs reached. Training stopped.")

    def get_latent(self):
        """Return the learned latent embedding for all nodes."""

        self.model.eval()
        with torch.no_grad():
            _, _, latent_z, _, _ = self.model(self.node_x, self.adj_norm)
        return latent_z.cpu().numpy()
