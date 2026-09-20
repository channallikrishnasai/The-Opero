from core.live_reconnect import is_clean_live_close


def test_clean_live_close_detects_direct_normal_close():
    assert is_clean_live_close(RuntimeError("1000 None."))
    assert is_clean_live_close(RuntimeError("sent 1000 (OK); then received 1000 (OK)"))


def test_clean_live_close_detects_task_group_leaf():
    group = ExceptionGroup("task failures", [RuntimeError("1000 None."), RuntimeError("other")])
    assert is_clean_live_close(group)


def test_clean_live_close_does_not_mask_real_errors():
    assert not is_clean_live_close(RuntimeError("401 API key not valid"))

