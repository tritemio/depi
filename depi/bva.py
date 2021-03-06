"""
Compute BVA from burst photon data.

The input photon data must be a DataFrame with one row per photon and
mandatory columns 'timestamp' and 'stream' (additional columns are ignored).
The input photons must be only the photons remaining after burst search.

The DataFrame index must contains two levels ('burst', 'ph'). 'burst' is
an integer indicating the burst number. 'ph' is an integer indicating the
photon-number in each burst ('ph' is 0 for the first photon of each burst).
This format is exported by FRETBursts when saving the burst photon data.
"""

from collections import defaultdict
import numpy as np
import pandas as pd


def bva(burstsph_Dex, n):
    """Compute BVA quantity for each burst.

    Arguments:
        burstsph_Dex (pandas.DataFrame): dataframe with one row per photon
            and a column `stream` indicating the stream of each photon.
            The index need to have two levels (burst, ph) indicating the
            burst and photon ID respectively.
        n (int): the number of photon used to compute E in sub-bursts
    """
    E_sub_std = []
    DexAem = burstsph_Dex.stream == 'DexAem'
    for i in np.unique(burstsph_Dex.index.get_level_values('burst')):
        DexAem_burst = DexAem.loc[i].values
        E_sub_bursts = []
        for istart in range(0, DexAem_burst.shape[0], n):
            A_D = DexAem_burst[istart:istart + n].sum()
            E = A_D / n
            E_sub_bursts.append(E)
        E_sub_std.append(np.std(E_sub_bursts))
    E_sub_std = np.array(E_sub_std)
    return E_sub_std


def bva_bin(burstsph_Dex, n, num_sub_bursts_th=60,
            E_bins=np.arange(0, 1.01, 0.05)):
    """Compute the mean BVA on E bins.

    Arguments:
        burstsph_Dex (pandas.DataFrame): dataframe with one row per photon
            and a column `stream` indicating the stream of each photon.
            The index need to have two levels (burst, ph) indicating the
            burst and photon ID respectively.
        n (int): the number of photon used to compute E in sub-bursts
        num_sub_bursts_th (int): minimum number of sub-bursts in a bin
            for BVA to be reported.
        E_bins (array): array of E bin edges, size in number of bins + 1.

    Returns:
        2-tuple of two arrays:
        - `E_sub_std_mean_bin`: the mean BVA in each E bins
        - `E_centers`: bin centers for each value in `E_sub_std_mean_bin`.
    """
    E_centers = E_bins[:-1] + 0.5 * (E_bins[1] - E_bins[0])
    burstsph_Dex_grp = burstsph_Dex.groupby('burst')
    # compute raw E values from photon data
    Nd_plus_Na = burstsph_Dex_grp['stream'].count()
    Na = burstsph_Dex_grp['stream'].agg(lambda x: (x == 'DexAem').sum())
    E_raw = Na / Nd_plus_Na
    # index of the bin for each burst in E_raw
    burst_indices = np.unique(burstsph_Dex.index.get_level_values('burst'))
    E_raw_bins = pd.Series(np.digitize(E_raw, E_bins) - 1,
                           index=burst_indices)
    E_sub_bursts_bin = defaultdict(list)
    DexAem = burstsph_Dex.stream == 'DexAem'
    for i in np.unique(burstsph_Dex.index.get_level_values('burst')):
        DexAem_burst = DexAem.loc[i].values
        E_raw_bin = E_raw_bins.loc[i]
        for istart in range(0, DexAem_burst.shape[0], n):
            A_D = DexAem_burst[istart:istart + n].sum()
            E = A_D / n
            E_sub_bursts_bin[E_raw_bin].append(E)
    E_sub_std_mean_bin = \
        [np.std(E_sub_bursts_bin[i])
         if len(E_sub_bursts_bin[i]) > num_sub_bursts_th else -1
         for i in range(len(E_centers))]
    assert len(E_sub_std_mean_bin) == len(E_bins) - 1
    return np.array(E_sub_std_mean_bin), E_centers


def bva_bin_combo(burstsph_Dex, n, num_sub_bursts_th=60,
                  E_bins=np.arange(0, 1.01, 0.05)):
    """Compute the BVA per each burst and mean BVA on E bins.

    This function combines :func:`bva` and :func:`bva_bin` and is much
    faster than calling these two functions separately.

    Arguments:
        burstsph_Dex (pandas.DataFrame): dataframe with one row per photon
            and a column `stream` indicating the stream of each photon.
            The index need to have two levels (burst, ph) indicating the
            burst and photon ID respectively.
        n (int): the number of photon used to compute E in sub-bursts
        num_sub_bursts_th (int): minimum number of sub-bursts in a bin
            for BVA to be reported.
        E_bins (array): array of E bin edges, size in number of bins + 1.

    Returns:
        Tuple of 3 arrays:
        - `E_sub_std`: the BVA computed on each burst
        - `E_sub_std_mean_bin`: the mean BVA in each E bins
        - `E_centers`: bin centers for each value in `E_sub_std_mean_bin`.
    """
    E_centers = E_bins[:-1] + 0.5 * (E_bins[1] - E_bins[0])
    burstsph_Dex_grp = burstsph_Dex.groupby('burst')
    # compute raw E values from photon data
    E_raw = (burstsph_Dex_grp['stream']
             .agg(lambda x: (x == 'DexAem').sum() / x.size))
    # index of the left bin edges in E_bins for each burst in E_raw
    burst_indices = np.unique(burstsph_Dex.index.get_level_values('burst'))
    E_raw_bins = pd.Series(np.digitize(E_raw, E_bins) - 1,
                           index=burst_indices)
    # standard deviation of sub-bursts in each burst
    E_sub_std = []
    # dict with bin index as key and values that are a list of lists.
    # The innermost list contains the E values of sub-bursts in a burst.
    E_sub_bursts_bin = defaultdict(list)
    DexAem = burstsph_Dex.stream == 'DexAem'
    # Loop over each burst
    for i in np.unique(burstsph_Dex.index.get_level_values('burst')):
        DexAem_burst = DexAem.loc[i].values
        E_raw_bin = E_raw_bins.loc[i]
        # We initialize a list of sub-bursts for each burst
        E_sub_bursts = []
        # Loop over each n-tuple of photons (i.e. sub-bursts)
        for istart in range(0, DexAem_burst.shape[0], n):
            A_D = DexAem_burst[istart:istart + n].sum()
            E = A_D / n
            E_sub_bursts.append(E)
        # Append list of current burst as an element in the list of current bin
        E_sub_bursts_bin[E_raw_bin].append(E_sub_bursts)
        E_sub_std.append(np.std(E_sub_bursts))
    E_bin_len = {k: sum([len(x) for x in v])
                 for k, v in E_sub_bursts_bin.items()}
    E_sub_std_mean_bin = [np.std(np.hstack(E_sub_bursts_bin[i]))
                          if E_bin_len.get(i, 0) > num_sub_bursts_th else -1
                          for i in range(len(E_centers))]
    E_sub_std = np.array(E_sub_std)
    assert len(E_sub_std_mean_bin) == len(E_centers)
    return E_sub_std, np.array(E_sub_std_mean_bin), E_centers
