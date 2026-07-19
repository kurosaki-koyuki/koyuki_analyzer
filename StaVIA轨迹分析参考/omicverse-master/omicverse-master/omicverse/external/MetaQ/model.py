import torch
import numpy as np
import torch.nn as nn
import torch.nn.functional as F


class Quantizer(nn.Module):
    def __init__(self, entry_num, entry_dim):
        super().__init__()

        self.entry_num = entry_num
        self.entry_dim = entry_dim
        self.decay = 0.9
        self.entry = nn.Embedding(self.entry_num, self.entry_dim)
        self.register_buffer("entry_prob", torch.zeros(self.entry_num))

    def init_codebook(self, z, method):
        if method == "Random":
            self.entry.weight.data.uniform_(-1.0 / self.entry_num, 1.0 / self.entry_num)
        elif method == "Kmeans":
            import faiss

            d = z.shape[1]
            kmeans = faiss.Kmeans(d, self.entry_num, spherical=True, gpu=True)
            kmeans.train(z)
            D, I = kmeans.index.search(z, 1)
            assignments = I.reshape(-1)
            centers = np.zeros((self.entry_num, d))
            for i in range(self.entry_num):
                centers[i] = z[assignments == i].mean(axis=0)
            self.entry.weight.data.copy_(torch.from_numpy(centers))
        elif method == "Geometric":
            from geosketch import gs

            sketch_index = gs(z, self.entry_num, replace=False)
            self.entry.weight.data.copy_(torch.from_numpy(z[sketch_index]))

    def forward(self, e, return_assignment):
        # cosine similarity
        normed_e = F.normalize(e, dim=1).detach()
        normed_c = F.normalize(self.entry.weight, dim=1)
        sim = torch.einsum("bd,dn->bn", normed_e, normed_c.t())

        # entry assignment
        assignment_indices = torch.argmax(sim, dim=1)
        assignments = torch.zeros(
            assignment_indices.unsqueeze(1).shape[0], self.entry_num, device=e.device
        )
        assignments.scatter_(1, assignment_indices.unsqueeze(1), 1)
        avg_probs = torch.mean(assignments, dim=0)

        # quantize
        e_q = torch.matmul(assignments, self.entry.weight)
        # L_C
        loss = torch.mean((e_q - e.detach()) ** 2)

        if self.training:
            # update the entry usage
            self.entry_prob.mul_(self.decay).add_(avg_probs, alpha=1 - self.decay)

            # deal with small entries
            norm_distance = F.softmax(1 - sim, dim=1)
            norm_distance = torch.max(norm_distance, dim=1).values
            dis_indices = torch.multinomial(
                norm_distance, num_samples=self.entry_num, replacement=True
            ).view(-1)
            random_feat = e.detach()[dis_indices]
            beta_s = (
                torch.exp(-self.entry_prob * self.entry_num * 100 - 1e-3)
                .unsqueeze(1)
                .repeat(1, self.entry_dim)
            )
            self.entry.weight.data = (
                self.entry.weight.data * (1 - beta_s) + random_feat * beta_s
            )

            # deal with large entries
            if self.entry_prob.sum() + 1e-4 >= 1:
                sim_t = sim.t()
                median_distance = torch.median(sim_t, dim=1).values
                median_distance = torch.abs(sim_t - median_distance[:, None])
                dis_indices = torch.multinomial(
                    F.softmax(-median_distance, dim=1), num_samples=1
                ).view(-1)
                random_feat = e.detach()[dis_indices]
                beta_l = (
                    torch.exp(-self.entry_prob.mean() / self.entry_prob * 10 - 1e-3)
                    .unsqueeze(1)
                    .repeat(1, self.entry_dim)
                )
                self.entry.weight.data = (
                    self.entry.weight.data * (1 - beta_l) + random_feat * beta_l
                )

        if return_assignment:
            top2_sim = torch.topk(sim, 2, dim=1).values
            delta_conf = top2_sim[:, 0] - top2_sim[:, 1]
            loss_c_sum = torch.sum((e_q - e.detach()) ** 2)

            return assignment_indices, delta_conf, loss_c_sum
        else:
            return e_q, loss


class Encoder(nn.Module):
    def __init__(self, input_dim, entry_dim):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Linear(512, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Linear(128, entry_dim),
        )

    def forward(self, input):
        return self.encoder(input)


class Decoder(nn.Module):
    def __init__(self, entry_dim, output_dim):
        super().__init__()
        self.docoder = nn.Sequential(
            nn.Linear(entry_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Linear(128, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
        )
        self.decoder_mean = nn.Linear(512, output_dim)
        self.decoder_disp = nn.Sequential(
            nn.Linear(512, output_dim),
            nn.Softplus(),
        )

    def forward(self, input):
        decode = self.docoder(input)
        mean = torch.clamp(torch.exp(self.decoder_mean(decode)), 1e-5, 1e6)
        disp = torch.clamp(self.decoder_disp(decode), 1e-4, 1e4)
        return mean, disp


class Decoder_ATAC(nn.Module):
    def __init__(self, entry_dim, output_dim):
        super().__init__()
        self.docoder = nn.Sequential(
            nn.BatchNorm1d(entry_dim),
            nn.Linear(entry_dim, output_dim),
        )

    def forward(self, input):
        mean = torch.clamp(torch.exp(self.docoder(input)), 1e-5, 1e6)
        return mean, None


def get_decoder(data_type, entry_dim, output_dim):
    if data_type == "RNA" or data_type == "ADT":
        return Decoder(entry_dim, output_dim)
    elif data_type == "ATAC":
        return Decoder_ATAC(entry_dim, output_dim)


class MetaQ(nn.Module):
    def __init__(self, input_dims, data_types, entry_num, entry_dim=32):
        super(MetaQ, self).__init__()
        self.omics_num = len(input_dims)
        self.encoders = nn.ModuleList(
            [Encoder(input_dim, entry_dim) for input_dim in input_dims]
        )
        self.quantizer = Quantizer(entry_num, entry_dim * self.omics_num)
        self.decoders = nn.ModuleList(
            [
                get_decoder(data_type, entry_dim, input_dim)
                for input_dim, data_type in zip(input_dims, data_types)
            ]
        )
        self.decoders_q = nn.ModuleList(
            [
                get_decoder(data_type, entry_dim * self.omics_num, input_dim)
                for input_dim, data_type in zip(input_dims, data_types)
            ]
        )

    def copy_decoder_q(self):
        if self.omics_num == 1:
            self.decoders_q[0].load_state_dict(self.decoders[0].state_dict())

    def quantize(self, hiddens, return_assignment=False):
        if self.omics_num > 1:
            hidden = torch.cat(hiddens, dim=1)
        else:
            hidden = hiddens[0]
        return self.quantizer(hidden, return_assignment)

    def forward(self, inputs):
        hiddens = []
        for i in range(self.omics_num):
            hiddens.append(self.encoders[i](inputs[i]))
        return hiddens

    def decode(self, hiddens):
        means, disps = [], []
        for i in range(self.omics_num):
            mean, disp = self.decoders[i](hiddens[i])
            means.append(mean)
            disps.append(disp)
        return means, disps

    def decode_q(self, hidden):
        means, disps = [], []
        for i in range(self.omics_num):
            mean, disp = self.decoders_q[i](hidden)
            means.append(mean)
            disps.append(disp)
        return means, disps


def negative_binomial_loss(mean, disp, scale_factor, x):
    eps = 1e-12
    mean = mean * scale_factor

    t1 = torch.lgamma(disp + eps) + torch.lgamma(x + 1.0) - torch.lgamma(x + disp + eps)
    t2 = (disp + x) * torch.log(1.0 + (mean / (disp + eps))) + (
        x * (torch.log(disp + eps) - torch.log(mean + eps))
    )
    nb_final = t1 + t2
    result = nb_final

    return result


def poisson_loss(mean, scale_factor, x):
    eps = 1e-12
    mean = mean * scale_factor

    poisson = mean - x * torch.log(mean + eps) + torch.lgamma(x + 1)

    return poisson


def reconstruction_loss(mean, disp, scale_factor, x, data_type, reduction="mean"):
    if data_type == "RNA" or data_type == "ADT":
        loss = negative_binomial_loss(mean, disp, scale_factor, x)
    elif data_type == "ATAC":
        loss = poisson_loss(mean, scale_factor, x)
    if reduction == "mean":
        loss = torch.mean(loss)
    elif reduction == "sum":
        loss = torch.sum(loss)
    else:
        raise NotImplementedError
    return loss
