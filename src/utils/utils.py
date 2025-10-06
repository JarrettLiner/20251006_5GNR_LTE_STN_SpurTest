"""Utilities for EVM Sweep Measurements.

Provides timing decorators and standard configuration/measurement functions.
"""

# File: src/utils/utils.py
import timeit
from functools import wraps
import logging


def method_timer(method):
    """Decorator to measure and print execution time of a method.

    Args:
        method (callable): Method to time.

    Returns:
        callable: Wrapped method that returns result and execution time.
    """
    def wrapper(*args, **kwargs):
        start_time = timeit.default_timer()
        result = method(*args, **kwargs)
        stop_time = timeit.default_timer()
        delta_time = stop_time - start_time
        print(f"{method.__name__:15s}: {delta_time:.3f} secs")
        return result, delta_time
    return wrapper


def std_config(instr):
    """Perform standard configuration for VSA and VSG.

    Args:
        instr: Instrument driver instance with VSA/VSG methods.
    """
    instr.VSG_Config()  # Configure VSG
    instr.VSA_Config()  # Configure VSA
    instr.VSx_freq(instr.freq)  # Set frequency
    instr.VSA_sweep()  # Perform initial sweep
    instr.VSG.clear_error()  # Clear VSG errors
    instr.VSA.clear_error()  # Clear VSA errors


def std_meas(instr, measure_aclr=True, measure_ch_pwr=True):
    """Perform standard measurements (EVM, ACLR, Channel Power)."""
    instr.VSA_get_info()  # Print configuration info
    instr.VSA_sweep()  # Perform sweep
    instr.VSA_level()  # Adjust level
    evm = instr.VSA_get_EVM()[0]  # Measure EVM
    ch_pwr = None
    aclr = ''
    if measure_aclr:
        aclr = instr.VSA_get_ACLR()[0]  # Measure ACLR
        ch_pwr = float(aclr.split(',')[0]) if aclr else None
    elif measure_ch_pwr:
        ch_pwr = instr.VSA_get_chPwr()  # Measure channel power
    print(f'EVM:{evm:.2f} CH_Pwr:{ch_pwr:.2f} ACLR:{aclr}')

@method_timer
def test(in_string):
    """Test function for timing decorator.

    Args:
        in_string (str): String to print.
    """
    sum(range(1000000))  # Simulate work
    print(f'{in_string}')