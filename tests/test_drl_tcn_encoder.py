import pytest

from src.drl.tcn_encoder import TORCH_AVAILABLE, describe_tcn_encoder


def test_tcn_encoder_description_is_available_without_hard_dependency():
    description = describe_tcn_encoder()
    assert description["causal_convolution"]
    assert description["dilated_convolution"]
    assert description["dilation_rates"] == (1, 2, 4)
    assert description["cash_logit"]
    assert "torch_available" in description


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch is optional for the TCN encoder.")
def test_causal_conv_preserves_sequence_length_after_trim():
    import torch

    from src.drl.tcn_encoder import CausalConv1d

    layer = CausalConv1d(4, 4, dilation=2, kernel_size=3)
    x = torch.randn(2, 4, 11)
    out = layer(x)
    assert out.shape[-1] == x.shape[-1]


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch is optional for the TCN encoder.")
def test_tcn_gap_policy_encoder_outputs_softmax_weights_with_cash():
    import torch

    from src.drl.tcn_encoder import TCNGapPolicyEncoder

    model = TCNGapPolicyEncoder(num_features=5, channels=8, dropout=0.0)
    x = torch.randn(3, 4, 20, 5)
    weights = model(x)
    assert weights.shape == (3, 5)
    assert torch.all(weights >= 0)
    assert torch.allclose(weights.sum(dim=1), torch.ones(3), atol=1e-6)


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch is optional for the TCN encoder.")
def test_tcn_gap_policy_encoder_validates_feature_count():
    import torch

    from src.drl.tcn_encoder import TCNGapPolicyEncoder

    model = TCNGapPolicyEncoder(num_features=5, channels=8, dropout=0.0)
    with pytest.raises(ValueError):
        model(torch.randn(2, 3, 10, 4))
