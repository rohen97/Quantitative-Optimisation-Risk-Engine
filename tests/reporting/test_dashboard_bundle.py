from dashboards.ic_dashboard import STREAMLIT_AVAILABLE


def test_dashboard_imports_without_streamlit_hard_requirement():
    assert isinstance(STREAMLIT_AVAILABLE, bool)
