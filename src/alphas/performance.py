import numpy as np
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning)

def estimate_annualization_factor_unix(timestamps):
    """
    Estimate annualization factor from a list of datetime objects.
    """
    if len(timestamps) < 2:
        raise ValueError("Need at least 2 timestamps to estimate frequency.")

    total_periods = len(timestamps) - 1
    duration_sec = (timestamps[-1] - timestamps[0]).total_seconds()

    if duration_sec <= 0:
        raise ValueError("Timestamps must be increasing and span > 0 time.")

    seconds_per_year = 365.25 * 24 * 60 * 60
    return total_periods / duration_sec * seconds_per_year

def compute_effective_period_count(timestamps, target_period_length='1s'):
    """
    Estimate the number of periods as if the data were sampled at `target_period_length`.

    Parameters
    ----------
    timestamps : list[datetime] or pd.DatetimeIndex
    target_period_length : str
        Frequency string like '1s', '1min', '100ms'

    Returns
    -------
    float
        Estimated number of effective periods (for use in annualization denominator).
    """
    import pandas as pd

    if len(timestamps) < 2:
        raise ValueError("Need at least 2 timestamps.")

    ts = pd.Series(pd.to_datetime(timestamps))
    total_duration = (ts.iloc[-1] - ts.iloc[0]).total_seconds()

    period_sec = pd.to_timedelta(target_period_length).total_seconds()
    return total_duration / period_sec



def resolve_annualization(freq=None, annualization_factor=None):
    if annualization_factor is not None:
        return annualization_factor
    if freq is not None:
        return get_annualization_factor(freq)
    raise ValueError("Either `freq` or `annualization_factor` must be provided.")


# Annualization frequency map
ANNUALIZATION_MAP = {
    'year': 1.0,
    'month': 12.0,
    'day': 365.25,
    'hour': 365.25 * 24,
    'minute': 365.25 * 24 * 60,
    'second': 365.25 * 24 * 60 * 60,
    'microsecond': 365.25 * 24 * 60 * 60 * 1e6,
    'nanosecond': 365.25 * 24 * 60 * 60 * 1e9
}

def normalize_weights_sumabs(array, axis):
    abs_array = np.abs(array)
    sum_abs = np.nansum(abs_array, axis=axis, keepdims=True)
    return array / sum_abs

def normalize_meanstd(array, axis, with_std=True):
    mean_val = np.nanmean(array, axis=axis, keepdims=True)
    normalized_array = array - mean_val
    if with_std:
        std_val = np.nanstd(array, axis=axis, keepdims=True)
        normalized_array /= std_val
    return normalized_array

def normalize_medianiqr(array, axis, ql=25, qh=75):
    median_val = np.nanmedian(array, axis=axis, keepdims=True)
    q_low = np.nanpercentile(array, ql, axis=axis, keepdims=True)
    q_high = np.nanpercentile(array, qh, axis=axis, keepdims=True)
    iqr = q_high - q_low
    return (array - median_val) / iqr

def normalize_minmax(array, axis):
    min_val = np.nanmin(array, axis=axis, keepdims=True)
    max_val = np.nanmax(array, axis=axis, keepdims=True)
    midpoint = (min_val + max_val) / 2
    half_range = (max_val - min_val) / 2
    return (array - midpoint) / half_range

def normalize_equal_weights(array, axis):
    count = np.sum(~np.isnan(array), axis=axis, keepdims=True)
    count = np.where(count == 0, 1, count)
    equal_weights = 1.0 / count
    return array * equal_weights

def fill_nans(arr, axis=0, method='ffill'):
    arr = np.moveaxis(arr, axis, 0)
    if method in ('ffill', 'both'):
        for i in range(1, arr.shape[0]):
            mask = np.isnan(arr[i])
            arr[i, mask] = arr[i - 1, mask]
    if method in ('bfill', 'both'):
        for i in range(arr.shape[0] - 2, -1, -1):
            mask = np.isnan(arr[i])
            arr[i, mask] = arr[i + 1, mask]
    return np.moveaxis(arr, 0, axis)

def get_annualization_factor(freq):
    return ANNUALIZATION_MAP[freq]

def annualized_returns(period_returns, total_periods, freq=None, compound=True, annualization_factor=None):
    scale = resolve_annualization(freq, annualization_factor) / total_periods
    print(f"Annualization scale: {scale}, Period returns: {period_returns}")
    if compound:
        return np.power(1.0 + period_returns, scale) - 1.0
    else:
        return period_returns * scale

def annualized_returns_linear(sum_return, total_periods, annualization_factor):
    """
    Non-compounded (linear) annualized return.

    Parameters
    ----------
    sum_return : float
        Total cumulative return across the observed periods (i.e., sum of r_t).
    total_periods : float
        Effective number of periods over which return was measured.
    annualization_factor : float
        Estimated number of periods per year.

    Returns
    -------
    float
        Annualized return (linear, not compounded).
    """
    scale = annualization_factor / total_periods
    return sum_return * scale


def annualized_turnover(period_turnover, total_periods, freq=None, annualization_factor=None):
    scale = resolve_annualization(freq, annualization_factor) / total_periods
    return period_turnover * scale

def annualized_sharpe(returns, risk_free_rate=0.0, freq=None, axis=0, annualization_factor=None):
    annual_factor = resolve_annualization(freq, annualization_factor)
    rf_per_period = risk_free_rate / annual_factor
    excess = returns - rf_per_period
    return np.nanmean(excess, axis=axis) / np.nanstd(excess, axis=axis) * np.sqrt(annual_factor)

def max_drawdown(returns, axis=0):
    cumulative = np.cumprod(1.0 + returns, axis=axis)
    peak = np.maximum.accumulate(cumulative, axis=axis)
    drawdown = (cumulative - peak) / peak
    return -np.nanmin(drawdown, axis=axis)

def sortino_ratio(returns, risk_free_rate=0.0, freq=None, axis=0, annualization_factor=None):
    annual_factor = resolve_annualization(freq, annualization_factor)
    rf_per_period = risk_free_rate / annual_factor
    excess = returns - rf_per_period
    downside = np.where(excess < 0, excess, 0)
    return np.nanmean(excess, axis=axis) / np.nanstd(downside, axis=axis) * np.sqrt(annual_factor)

def calmar_ratio(returns, freq=None, axis=0, compound=False, annualization_factor=None, timestamps=None, period_length='1s'):
    if timestamps is not None:
        total_periods = compute_effective_period_count(timestamps, target_period_length=period_length)
    else:
        total_periods = returns.shape[axis]

    avg_return = np.nanmean(returns, axis=axis)
    ann_return = annualized_returns_linear(
        avg_return,
        total_periods=total_periods,
        annualization_factor=resolve_annualization(freq, annualization_factor),
    )
    max_dd = max_drawdown(returns, axis=axis)
    return ann_return / np.abs(max_dd)

def hit_rate(returns, axis=0):
    return np.mean(returns > 0, axis=axis)

def position_changes_with_drift(weights_array, position_returns, time_axis=0, instrument_axis=1):
    next_weights = np.roll(weights_array, -1, axis=time_axis)
    index = [slice(None)] * weights_array.ndim
    index[time_axis] = -1
    next_weights[tuple(index)] = np.nan

    sum_returns = np.sum(position_returns, axis=instrument_axis, keepdims=True)
    drift = weights_array * (position_returns - sum_returns) / (1.0 + sum_returns)
    changes = np.abs(next_weights - (weights_array + drift))
    return changes

def period_turnover(position_changes, axis=(0, 1)):
    return np.nansum(position_changes, axis=axis)

def turnover(weights, returns, time_axis=0, turnover_sum_axis=None, instrument_axis=1):
    changes = position_changes_with_drift(weights, returns, time_axis, instrument_axis)
    changes = np.nan_to_num(changes, nan=0.0)
    if turnover_sum_axis is None:
        turnover_sum_axis = (time_axis, instrument_axis)
    return np.nansum(changes, axis=turnover_sum_axis)

def portfolio_efficiency_np(weights, returns, time_axis=0, instrument_axis=1,
                            freq=None, compound=True, turnover_sum_axis=None, returns_sum_axis=None,
                            annualization_factor=None):
    changes = position_changes_with_drift(weights, returns, time_axis, instrument_axis)
    if turnover_sum_axis is None:
        turnover_sum_axis = (time_axis, instrument_axis)
    period_turnover_val = np.nansum(changes, axis=turnover_sum_axis)

    total_periods = weights.shape[time_axis]
    ann_turnover = annualized_turnover(period_turnover_val, total_periods, freq=freq, annualization_factor=annualization_factor)

    if returns_sum_axis is None:
        returns_sum_axis = (instrument_axis,)
    period_returns = returns.sum(axis=returns_sum_axis)

    ann_returns = annualized_returns(period_returns, total_periods, freq=freq, compound=compound, annualization_factor=annualization_factor)

    return ann_returns / ann_turnover

def naive_portfolio_efficiency(returns, weights, timestamps=None, freq='second', compound=True):
    """
    Compute naive efficiency: annualized return / sum(abs(returns)).

    Parameters:
    - returns: 1D np.ndarray
    - timestamps: list of datetime (optional)
    - freq: str (only used if timestamps is None)

    Returns:
    - scalar efficiency
    """
    returns = np.nan_to_num(returns)

    if timestamps is not None:
        total_periods = compute_effective_period_count(timestamps, target_period_length='1s')
        annualization = estimate_annualization_factor_unix(timestamps)
    else:
        total_periods = len(returns)
        annualization = get_annualization_factor(freq)

    sum_return = np.nansum(returns)

    ann_return = annualized_returns_linear(
        sum_return,
        total_periods=total_periods,
        annualization_factor=annualization,
    )

    total_turnover = np.nansum(np.abs(weights))
    eff = ann_return / total_turnover if total_turnover > 0 else 0.0
    return eff


