"""Tests for feature flag system."""
import pytest
from factory.features import is_feature_allowed, get_all_features, get_paid_features, FEATURES


class TestFeatureFlags:
    def test_all_features_have_key_and_description(self):
        for f in FEATURES:
            assert f.key
            assert f.description

    def test_free_features_allowed_for_non_vip(self):
        free_features = [f for f in FEATURES if f.free]
        assert len(free_features) > 0
        for f in free_features:
            assert is_feature_allowed(f.key, is_vip=False) is True
            assert is_feature_allowed(f.key, is_vip=True) is True

    def test_paid_features_blocked_for_non_vip(self):
        paid_features = [f for f in FEATURES if not f.free]
        assert len(paid_features) > 0
        for f in paid_features:
            assert is_feature_allowed(f.key, is_vip=False) is False

    def test_paid_features_allowed_for_vip(self):
        paid_features = [f for f in FEATURES if not f.free]
        for f in paid_features:
            assert is_feature_allowed(f.key, is_vip=True) is True

    def test_unknown_feature_denied(self):
        assert is_feature_allowed("unknown.feature", is_vip=True) is False

    def test_get_all_features(self):
        all_f = get_all_features()
        assert len(all_f) == len(FEATURES)

    def test_get_paid_features(self):
        paid = get_paid_features()
        for f in paid:
            assert not f.free

    def test_feature_flag_immutable(self):
        f = FEATURES[0]
        with pytest.raises(Exception):
            f.key = "changed"  # type: ignore[misc]

    def test_free_and_paid_disjoint(self):
        free_keys = {f.key for f in FEATURES if f.free}
        paid_keys = {f.key for f in FEATURES if not f.free}
        assert free_keys & paid_keys == set()

    def test_all_features_have_unique_keys(self):
        keys = [f.key for f in FEATURES]
        assert len(keys) == len(set(keys))
