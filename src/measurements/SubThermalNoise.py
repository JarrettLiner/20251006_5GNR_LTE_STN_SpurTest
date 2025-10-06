# File: src/measurements/SubThermalNoise.py
# Author: [Your Name or Company]
# Date: October 06, 2025
# Description: This module handles Sub-Thermal Noise (STN) measurements. It configures instruments,
#              performs noise marker measurements, and calculates statistics.

import logging
import numpy as np
from src.utils.utils import method_timer
from src.instruments.bench import bench

logger = logging.getLogger(__name__)

class option_functions:
    """Class for Sub-Thermal Noise (STN) measurements."""

    def __init__(self, freq=6e9):
        """Initialize STN driver and connections.

        Args:
            freq (float): Center frequency in Hz, default 6e9.
        """
        logger.info(f"Initializing STN driver with freq={freq / 1e9:.3f}GHz")
        self.VSA = bench().VSA_start()  # Start VSA connection
        self.VSA.sock.settimeout(30)  # Set timeout
        self.VSG = bench().VSG_start()  # Start VSG connection
        self.VSG.write("OUTP:STAT OFF")  # Turn off VSG output
        self.frequency = freq
        self.swp_time = 1.0

    @method_timer
    def VSA_Config(self):
        """Configure VSA for STN measurement."""
        logger.info("Configuring VSA for STN")
        self.VSA.query('*RST;*OPC?')  # Reset VSA
        self.VSA.query(':INST:SEL "Spectrum";*OPC?')  # Select spectrum mode
        self.VSA.write(f':SENS:FREQ:CENT {self.frequency}')  # Set center frequency
        self.VSA.write(':SENS:FREQ:SPAN 1e9')  # Set span to 1 GHz
        self.VSA.write(':INP:GAIN:STAT ON')  # Enable input gain
        self.VSA.write(':INP:GAIN:VAL 30')  # Set gain to 30 dB
        self.VSA.write(':INP:ATT:AUTO OFF')  # Disable auto attenuation
        self.VSA.write(':INP:ATT 0')  # Set attenuation to 0 dB
        self.VSA.write(f':SENS:SWE:WIND:POIN {2001}')  # Set sweep points to 2001
        self.VSA.write('DISP:WIND1:SUBW:TRAC1:MODE WRIT')  # Set trace mode to clear write
        self.VSA.write(':SENS:WIND1:DET:FUNC RMS')  # Set RMS detector
        self.VSA.write(f'SENS:BAND:RES {10e3}')  # Set resolution bandwidth to 10 kHz
        self.VSA.write(f'SENS:BAND:VID {10e3}')  # Set video bandwidth to 10 kHz
        self.VSA.write('SENS:SWE:TIME:AUTO OFF')  # Enable auto sweep time
        self.VSA.write(f'SENS:SWE:TIME {0.005}')
        self.VSA.write('SENS:SWE:TYPE AUTO')  # Enable auto sweep type
        self.VSA.write(':SENS:SWE:OPT AUTO')  # Enable auto sweep optimization
        self.VSA.query('DISP:WIND1:SUBW:TRAC1:Y:SCAL:AUTO ONCE;*OPC?')  # Auto-scale display
        self.VSA.write('SENS:POW:NCOR ON')  # Enable noise correction
        self.VSA.query('INIT:IMM;*OPC?')  # Initiate sweep
        self.VSA.query('DISP:WIND1:SUBW:TRAC1:Y:SCAL:AUTO ONCE;*OPC?')  # Auto-scale again
        self.STN_Noise_Marker()  # Configure noise marker
        self.VSA.clear_error()  # Clear error queue

    def STN_Noise_Marker(self):
        """Configure noise marker for STN measurement."""
        logger.info("Configuring noise marker for STN")
        self.VSA.write(':CALC1:DELT1:FUNC:PNO:STAT OFF')  # Disable power noise function
        self.VSA.write(':CALC1:MARK1:FUNC:NOIS:STAT ON')  # Enable noise marker
        self.VSA.write(f':CALC1:MARK1:X {self.frequency}')  # Set marker frequency

    @method_timer
    def get_VSA_sweep_noise_mkr(self):
        """Perform VSA sweep and measure noise marker.

        Returns:
            float: Noise marker value in dBm.
        """
        logger.info("Performing VSA sweep for STN noise marker")
        self.VSA.write('INIT:CONT OFF')  # Disable continuous sweep
        self.VSA.query('INIT:IMM;*OPC?')  # Initiate sweep and wait
        marker = self.VSA.queryFloat(':CALC:MARK:FUNC:NOIS:RES?')  # Fetch noise marker
        logger.info(f"Noise marker measured: {marker:.2f} dBm")
        return marker  # Decorator returns (marker, delta_time)

    def STN_set_frequency(self, freq):
        """Set frequency for STN measurement.

        Args:
            freq (float): Frequency in Hz.
        """
        logger.info(f"Setting STN frequency to {freq / 1e9:.3f}GHz")
        self.frequency = freq
        self.VSA.write(f':SENS:FREQ:CENT {self.frequency}')  # Set center frequency
        self.VSA.write(f':CALC1:MARK1:X {self.frequency}')  # Set marker frequency
        self.VSA.query('*OPC?')  # Wait for operation complete

    @staticmethod
    def get_Array_stats(in_arry):
        """Calculate statistics for an array of measurements.

        Args:
            in_arry (np.ndarray): Array of measurement values.

        Returns:
            str: Formatted string of statistics.
        """
        logger.info("Calculating STN array stats")
        avg = np.mean(in_arry)
        min_val = np.min(in_arry)
        max_val = np.max(in_arry)
        std_dev = np.std(in_arry)
        out_str = (f'Min:{min_val:.3f} Max:{max_val:.3f} Avg:{avg:.3f} '
                   f'StdDev:{std_dev:.3f} Delta:{max_val - min_val:.3f}')
        logger.info(f"STN stats: {out_str}")
        return out_str

    @method_timer
    def close_connections(self):
        """Close VSA and VSG connections."""
        logger.info("Closing VSA and VSG connections")
        self.VSA.close()
        self.VSG.close()
        logger.info("Connections closed successfully")