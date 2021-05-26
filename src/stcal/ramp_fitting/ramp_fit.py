#! /usr/bin/env python
#
#  ramp_fit.py - calculate weighted mean of slope, based on Massimo
#                Robberto's "On the Optimal Strategy to fit MULTIACCUM
#                ramps in the presence of cosmic rays."
#                (JWST-STScI-0001490,SM-12; 07/25/08).   The derivation
#                is a generalization for >1 cosmic rays, calculating
#                the slope and variance of the slope for each section
#                of the ramp (in between cosmic rays). The intervals are
#                determined from the input data quality arrays.
#
# Note:
# In this module, comments on the 'first group','second group', etc are
#    1-based, unless noted otherwise.

import numpy as np
import logging

from . import constants
# from . import gls_fit           # used only if algorithm is "GLS"
from . import ols_fit           # used only if algorithm is "OLS"
from . import ramp_fit_class

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

BUFSIZE = 1024 * 300000  # 300Mb cache size for data section


def create_ramp_fit_class(model, dqflags=None):
    """
    Create an internal ramp fit class from a data model.

    Parameters
    ----------
    model : data model
        input data model, assumed to be of type RampModel

    Return
    ------
    ramp_class : RampFitInternal
        The internal ramp class.
    """
    ramp_class = ramp_fit_class.RampFitInternal()

    ramp_class.set_arrays(
        model.data, model.err, model.groupdq, model.pixeldq, model.int_times)

    ramp_class.set_meta(
        name=model.meta.instrument.name,
        frame_time=model.meta.exposure.frame_time,
        exp_ngroups=model.meta.exposure.ngroups,
        group_time=model.meta.exposure.group_time,
        groupgap=model.meta.exposure.groupgap,
        nframes=model.meta.exposure.nframes,
        drop_frames1=model.meta.exposure.drop_frames1)

    ramp_class.set_dqflags(dqflags)

    return ramp_class


def ramp_fit(model, buffsize, save_opt, readnoise_2d, gain_2d,
             algorithm, weighting, max_cores, dqflags):
    """
    Calculate the count rate for each pixel in all data cube sections and all
    integrations, equal to the slope for all sections (intervals between
    cosmic rays) of the pixel's ramp divided by the effective integration time.
    The weighting parameter must currently be set to 'optim', to use the optimal
    weighting (paper by Fixsen, ref. TBA) will be used in the fitting; this is
    currently the only supported weighting scheme.

    Parameters
    ----------
    model : data model
        input data model, assumed to be of type RampModel

    buffsize : int
        size of data section (buffer) in bytes

    save_opt : bool
       calculate optional fitting results

    readnoise_2d: ndarray
        2-D array readnoise for all pixels

    gain_2d: ndarray
        2-D array gain for all pixels

    algorithm : str
        'OLS' specifies that ordinary least squares should be used;
        'GLS' specifies that generalized least squares should be used.

    weighting : str
        'optimal' specifies that optimal weighting should be used;
         currently the only weighting supported.

    max_cores : str
        Number of cores to use for multiprocessing. If set to 'none' (the
        default), then no multiprocessing will be done. The other allowable
        values are 'quarter', 'half', and 'all'. This is the fraction of cores
        to use for multi-proc. The total number of cores includes the SMT cores
        (Hyper Threading for Intel).

    dqflags: dict
        A dictionary with at least the following keywords:
        DO_NOT_USE, SATURATED, JUMP_DET, NO_GAIN_VALUE, UNRELIABLE_SLOPE

    Returns
    -------
    image_info: tuple
        The tuple of computed ramp fitting arrays.

    integ_info: tuple
        The tuple of computed integration fitting arrays.

    opt_info: tuple
        The tuple of computed optional results arrays for fitting.

    gls_opt_model : GLS_RampFitModel object or None (Unused for now)
        Object containing optional GLS-specific ramp fitting data for the
        exposure
    """
    ramp_class = create_ramp_fit_class(model, dqflags)

    constants.update_dqflags(dqflags)
    if None in constants.dqflags.values():
        raise ValueError("Some of the DQ flags required for ramp_fitting are None.")

    if algorithm.upper() == "GLS":
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # !!!!! Reference to ReadModel and GainModel changed to simple ndarrays !!!!!
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # new_model, int_model, gls_opt_model = gls_fit.gls_ramp_fit(
        #     model, buffsize, save_opt, readnoise_model, gain_model, max_cores)
        image_info, integ_info, gls_opt_model = None, None, None
        opt_info = None
    else:
        # Get readnoise array for calculation of variance of noiseless ramps, and
        #   gain array in case optimal weighting is to be done
        nframes = model.meta.exposure.nframes
        readnoise_2d *= gain_2d / np.sqrt(2. * nframes)

        # Compute ramp fitting using ordinary least squares.
        image_info, integ_info, opt_info = ols_fit.ols_ramp_fit_multi(
            ramp_class, buffsize, save_opt, readnoise_2d, gain_2d, weighting, max_cores)
        gls_opt_model = None

    return image_info, integ_info, opt_info, gls_opt_model
