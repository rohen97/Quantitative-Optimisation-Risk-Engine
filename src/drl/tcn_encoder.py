from __future__ import annotations

from dataclasses import dataclass

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional local install
    torch = None
    nn = None
    TORCH_AVAILABLE = False


@dataclass(frozen=True)
class TCNEncoderSpec:
    """Architecture placeholder for future causal/dilated TCN policy encoders."""

    causal_convolution: bool = True
    dilated_convolution: bool = True
    residual_blocks: int = 3
    dilation_rates: tuple[int, int, int] = (1, 2, 4)
    kernel_size: int = 3
    global_average_pooling: bool = True
    cross_asset_feature_integration: bool = True
    cash_logit: bool = True
    output_activation: str = "softmax_allocation"
    torch_available: bool = TORCH_AVAILABLE


def describe_tcn_encoder() -> dict[str, object]:
    """Return serialisable TCN encoder design metadata."""
    return TCNEncoderSpec().__dict__.copy()


if TORCH_AVAILABLE:

    class CausalConv1d(nn.Conv1d):
        """One-dimensional causal convolution that trims right-side padding."""

        def __init__(self, *args, dilation=1, kernel_size=3, **kwargs):
            padding = (kernel_size - 1) * dilation
            super().__init__(*args, dilation=dilation, kernel_size=kernel_size, padding=padding, **kwargs)
            self.trim = padding

        def forward(self, x):
            out = super().forward(x)
            if self.trim > 0:
                out = out[..., :-self.trim]
            return out


    class TCNResidualBlock(nn.Module):
        """Causal dilated TCN residual block."""

        def __init__(self, channels: int, dilation: int, dropout: float):
            super().__init__()
            self.net = nn.Sequential(
                CausalConv1d(channels, channels, dilation=dilation, kernel_size=3),
                nn.ReLU(),
                nn.Dropout(dropout),
                CausalConv1d(channels, channels, dilation=dilation, kernel_size=3),
                nn.ReLU(),
                nn.Dropout(dropout),
            )

        def forward(self, x):
            return x + self.net(x)


    class TCNGapPolicyEncoder(nn.Module):
        """Shared-parameter TCN + GAP policy encoder for portfolio weights.

        Input shape:
            ``(batch, assets, timesteps, features)``

        Output shape:
            ``(batch, assets + 1)`` where the final column is the cash weight.
        """

        def __init__(
            self,
            num_features: int,
            channels: int = 32,
            dilation_rates: tuple[int, int, int] = (1, 2, 4),
            dropout: float = 0.10,
        ):
            super().__init__()
            self.num_features = int(num_features)
            self.channels = int(channels)
            self.input_projection = nn.Conv1d(self.num_features, self.channels, kernel_size=1)
            self.tcn = nn.Sequential(*(TCNResidualBlock(self.channels, dilation, dropout) for dilation in dilation_rates))
            self.cross_asset_fc = nn.Linear(self.channels, self.channels)
            self.asset_logit = nn.Linear(self.channels, 1)
            self.cash_logit = nn.Linear(self.channels, 1)
            self.softmax = nn.Softmax(dim=-1)

        def encode_assets(self, x):
            if x.ndim != 4:
                raise ValueError("TCNGapPolicyEncoder expects input shape (batch, assets, timesteps, features).")
            batch, assets, timesteps, features = x.shape
            if features != self.num_features:
                raise ValueError(f"Expected {self.num_features} features, received {features}.")
            streams = x.reshape(batch * assets, timesteps, features).transpose(1, 2)
            encoded = self.input_projection(streams)
            encoded = self.tcn(encoded)
            pooled = encoded.mean(dim=-1)
            return pooled.reshape(batch, assets, self.channels)

        def forward(self, x):
            asset_features = self.encode_assets(x)
            cross_asset_context = torch.tanh(self.cross_asset_fc(asset_features.mean(dim=1)))
            enriched = asset_features + cross_asset_context.unsqueeze(1)
            asset_logits = self.asset_logit(enriched).squeeze(-1)
            cash_logit = self.cash_logit(cross_asset_context)
            logits = torch.cat([asset_logits, cash_logit], dim=-1)
            return self.softmax(logits)
