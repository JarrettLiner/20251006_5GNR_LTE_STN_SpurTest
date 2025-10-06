# File: src/measurements/nr5g_fr1.py
# Author: [Your Name or Company]
# Date: October 06, 2025
# Description: This module provides the driver for NR5G FR1 measurements using VSA and VSG instruments.
#              It handles configuration, EVM, and ACLR measurements for 5G NR signals.

import logging
import time
import os
import re
from src.utils.utils import method_timer
from src.instruments.bench import bench

logger = logging.getLogger(__name__)


class std_insr_driver:
    """Class for NR5G FR1 measurements with VSA and VSG.

    This class manages shared connections and methods for 5G NR measurements.
    """

    _vsa_instance = None  # Class variable for VSA connection
    _vsg_instance = None  # Class variable for VSG connection

    def __init__(self, freq=6e9, pwr=-10.0, waveform_file=None, setup_file=None):
        """Initialize instrument connections and parameters.

        Args:
            freq (float): Center frequency in Hz, default 6e9.
            pwr (float): Power in dBm, default -10.0.
            waveform_file (str, optional): Path to waveform file.
            setup_file (str, optional): Path to FSW setup file.
        """
        logger.info(f"Initializing NR5G driver with freq={freq / 1e9:.3f}GHz, pwr={pwr}dBm, "
                    f"waveform_file={waveform_file}, setup_file={setup_file}")
        self._validate_file_names(waveform_file, setup_file)
        self.waveform_params = self._extract_waveform_params(waveform_file) if waveform_file else {}
        self.rb = self.waveform_params.get("resource_blocks", 51)
        self.rbo = self.waveform_params.get("resource_block_offset", 0)
        self.bw = self.waveform_params.get("bandwidth_mhz", 20)
        self.mod = self.waveform_params.get("modulation", "QAM256")
        self.scs = self.waveform_params.get("subcarrier_spacing_khz", 30)
        self.dupl = self.waveform_params.get("duplexing", "FDD")
        self.ldir = self.waveform_params.get("link_direction", "UP")
        if std_insr_driver._vsa_instance is None:
            try:
                std_insr_driver._vsa_instance = bench().VSA_start()
                std_insr_driver._vsa_instance.sock.settimeout(30)
                response = std_insr_driver._vsa_instance.query('*IDN?')
                logger.info("Created new VSA connection")
                logger.info(f"VSA IDN: {response}")
            except Exception as e:
                logger.error(f"Failed to create VSA connection: {e}")
                raise
        if std_insr_driver._vsg_instance is None:
            try:
                std_insr_driver._vsg_instance = bench().VSG_start()
                response = std_insr_driver._vsg_instance.query('*IDN?')
                logger.info("Created new VSG connection")
                logger.info(f"VSG IDN: {response}")
            except Exception as e:
                logger.error(f"Failed to create VSG connection: {e}")
                raise
        self.VSA = std_insr_driver._vsa_instance
        self.VSG = std_insr_driver._vsg_instance
        self.freq = float(freq)
        self.pwr = float(pwr)
        self.waveform_file = waveform_file
        self.setup_file = setup_file
        self.swp_time = 0.015

    def _validate_file_names(self, waveform_file, setup_file):
        """Validate waveform and setup file names against required format."""
        waveform_pattern = r'^5GNR_(UL|DL)_(\d+MHz)_(QPSK|16QAM|64QAM|256QAM|1024QAM)_(\d+kHz)_(\d+RB)_(\d+RBO)\.wv$'
        setup_pattern = r'^5GNR_(UL|DL)_(\d+MHz)_(QPSK|16QAM|64QAM|256QAM|1024QAM)_(\d+kHz)_(\d+RB)_(\d+RBO)\.dfl$'
        for file_path, file_type, pattern in [(waveform_file, "waveform", waveform_pattern),
                                              (setup_file, "setup", setup_pattern)]:
            if file_path:
                file_name = os.path.basename(file_path).strip()
                logger.debug(f"Validating {file_type} file name: '{file_name}'")
                if not re.match(pattern, file_name):
                    logger.error(f"Invalid {file_type} file name: {file_name}")
                    raise ValueError(f"Invalid {file_type} file name: {file_name}")

    def _extract_waveform_params(self, waveform_file):
        """Extract parameters from waveform file name."""
        file_name = os.path.basename(waveform_file).strip()
        logger.debug(f"Extracting parameters from waveform file: '{file_name}'")
        pattern = r'^5GNR_(UL|DL)_(\d+MHz)_(QPSK|16QAM|64QAM|256QAM|1024QAM)_(\d+kHz)_(\d+RB)_(\d+RBO)\.wv$'
        match = re.match(pattern, file_name)
        if not match:
            logger.error(f"Cannot extract parameters from waveform file: {file_name}")
            return {}
        try:
            link_direction = match.group(1)
            return {
                "signal_type": "5GNR",
                "link_direction": link_direction,
                "bandwidth_mhz": int(match.group(2).replace("MHz", "")),
                "modulation": match.group(3),
                "subcarrier_spacing_khz": int(match.group(4).replace("kHz", "")),
                "resource_blocks": int(match.group(5).replace("RB", "")),
                "resource_block_offset": int(match.group(6).replace("RBO", "")),
                "duplexing": "FDD" if link_direction == "UL" else "TDD"
            }
        except Exception as e:
            logger.error(f"Error parsing waveform parameters from {file_name}: {e}")
            return {}

    @classmethod
    def close_connections(cls):
        """Close VSA and VSG connections."""
        if cls._vsa_instance:
            cls._vsa_instance.sock.close()
            cls._vsa_instance = None
            logger.info("Closed VSA socket")
        if cls._vsg_instance:
            cls._vsg_instance.sock.close()
            cls._vsg_instance = None
            logger.info("Closed VSG socket")

    @method_timer
    def VSG_Config(self):
        """Configure VSG for 5G NR signal generation."""
        try:
            if not self.waveform_file:
                logger.error("No waveform file provided")
                raise ValueError("No waveform file provided")
            scpi_waveform_path = self.waveform_file.replace('\\', '/')
            logger.info(f"Loading waveform file: {scpi_waveform_path}")
            self.VSG.write(':SOUR1:BB:ARB:STAT 0')
            self.VSG.query(f':SOUR1:BB:ARB:WAV:SEL "{scpi_waveform_path}";*OPC?')
            self.VSG.query(':SOUR1:BB:ARB:STAT 1;*OPC?')
            self.VSG.write(f':SOUR1:FREQ:CW {self.freq}')
            self.VSG.write(':OUTP1:STAT 1')
            self.VSG.query(':SOUR1:CORR:OPT:EVM 1;*OPC?')
            self.VSG.write(':SOUR1:BB:ARB:TRIG:OUTP1:MODE REST')
            self.VSG_pwr(self.pwr)
            self.VSG.query('*OPC?')
            logger.info('VSG configuration complete.')
            print('VSG configuration complete.')
        except Exception as e:
            logger.error(f"VSG configuration failed: {e}")
            raise

    def VSG_pwr(self, pwr):
        """Set VSG output power."""
        self.VSG.write(f':SOUR1:POW:POW {float(pwr)}')
        self.pwr = float(pwr)

    @method_timer
    def VSA_Config(self, freq=None, pwr=None):
        """Configure VSA for 5G NR measurement."""
        try:
            logger.info("Configuring VSA for 5G NR")
            if freq is None:
                freq = self.freq
            if not isinstance(freq, (int, float)) or freq <= 0:
                logger.error(f"Invalid frequency: {freq}")
                raise ValueError(f"Invalid frequency: {freq}")
            if not self.setup_file:
                logger.error("No setup file provided")
                raise ValueError("No setup file provided")
            scpi_setup_path = self.setup_file.replace('\\', '/')
            logger.info(f"Recalling setup file: {scpi_setup_path}")
            self.VSA.query('*RST;*OPC?')
            self.VSA.query(f':MMEM:LOAD:STAT 1,"{scpi_setup_path}";*OPC?')
            self.VSA.query(':SENS:ADJ:LEV;*OPC?')
            self.VSA.query(':SENS:ADJ:EVM;*OPC?')
            self.VSA.write('INIT:CONT OFF')
            self.VSA.query(f':SENS:FREQ:CENT {freq};*OPC?')
            self.VSA.write(':SENS:SWE:TIME 0.0008')
            self.VSA.write(':SENS:NR5G:FRAM:SLOT 1')
            self.VSA.query('INIT:IMM;*OPC?')
            self.VSA.query(':SENS:ADJ:EVM;*OPC?')
            logger.info("Performed pre-sweep in VSA_Config")
            print('VSA configuration complete.')
        except Exception as e:
            logger.error(f"VSA configuration failed: {e}")
            raise

    @method_timer
    def VSx_freq(self, freq):
        """Set frequency for both VSA and VSG."""
        logger.info(f"Setting VSA/VSG frequency to {freq / 1e9:.3f}GHz")
        if not isinstance(freq, (int, float)) or freq <= 0:
            logger.error(f"Invalid frequency: {freq}")
            raise ValueError(f"Invalid frequency: {freq}")
        self.VSA.query(f':SENS:FREQ:CENT {freq};*OPC?')
        self.VSG.query(f':SOUR:FREQ:CW {freq};*OPC?')
        self.freq = float(freq)

    @method_timer
    def VSA_sweep(self):
        """Perform VSA sweep for measurement."""
        logger.info("Skipping VSA sweep as it is redundant before EVM measurement")
        # Removed INIT:IMM to reduce test time

    @method_timer
    def VSA_level(self):
        """Adjust VSA input level."""
        logger.info("Adjusting VSA input level")
        self.VSA.query(':SENS:ADJ:LEV;*OPC?')

    @method_timer
    def VSA_get_info(self):
        """Get and return VSA configuration info."""
        if self.waveform_params:
            params = self.waveform_params
            config = (f"{self.freq / 1e9:.3f}GHz_"
                      f"{params['bandwidth_mhz']}MHz_"
                      f"{params['duplexing']}_"
                      f"{params['link_direction']}_"
                      f"{params['subcarrier_spacing_khz']}_"
                      f"{params['resource_blocks']}RB_"
                      f"{params['resource_block_offset']}RBO_"
                      f"{params['modulation']}")
            if self.waveform_file:
                config += f"_waveform_{os.path.basename(self.waveform_file)}"
            if self.setup_file:
                config += f"_setup_{os.path.basename(self.setup_file)}"
        else:
            config = (f"{self.freq / 1e9:.3f}GHz_{self.bw}MHz_{self.dupl}_{self.ldir}_"
                      f"{self.scs}_{self.rb}RB_{self.rbo}RBO_{self.mod}")
            if self.waveform_file:
                config += f"_waveform_{os.path.basename(self.waveform_file)}"
            if self.setup_file:
                config += f"_setup_{os.path.basename(self.setup_file)}"
        logger.info(f"VSA configuration: {config}")
        return config

    @method_timer
    def VSA_get_EVM(self):
        """Measure and return EVM (Error Vector Magnitude).

        Returns:
            float: EVM value in dB.
        """
        logger.info("Measuring EVM")
        try:
            # Ensure VSA is in correct mode
            self.VSA.write(':CONF:NR5G:MEAS EVM;*OPC')
            #  self.VSA.query(':SENS:ADJ:EVM;*OPC?')
            self.VSA.query('INIT:IMM;*OPC?')
            pep_str = self.VSG.query(':SOUR1:POW:PEP?')
            try:
                pep = float(pep_str)
            except ValueError:
                logger.error(f"Failed to parse PEP value: '{pep_str}'")
                raise
            reflev = pep - 2
            self.VSA.write(f':DISP:WIND:TRAC:Y:SCAL:RLEV {reflev}')
            self.VSA.query(':SENS:ADJ:EVM;*OPC?')
            self.VSA.query('INIT:IMM;*OPC?')
            evm_str = self.VSA.query(':FETC:CC1:SUMM:EVM:ALL:AVER?')
            try:
                evm = float(evm_str)
                logger.info(f"EVM measured: {evm:.2f} dB")
                return evm
            except ValueError:
                logger.error(f"Failed to parse EVM value: '{evm_str}'")
                return float('nan')
        except Exception as e:
            logger.error(f"EVM measurement failed: {e}")
            return float('nan')

    @method_timer
    def VSA_get_ACLR(self):
        """Measure and return ACLR (Adjacent Channel Leakage Ratio)."""
        logger.info("Measuring ACLR")
        try:
            self.VSA.write(':CONF:NR5G:MEAS ACLR;*OPC')
            self.VSA.write(f':SENS:FREQ:CENT {self.freq};:SENS:POW:ACH:ACP 2;*OPC')
            self.VSA.write(':SENS:SWE:TYPE SWE')
            self.VSA.write('SENS:SWE:OPT SPE')  # Set sweep optimization to auto
            self.VSA.query('INIT:IMM;*OPC?')
            aclr = self.VSA.query(':CALC:MARK:FUNC:POW:RES? ACP')
            logger.info(f"ACLR measured: {aclr}")
            return str(aclr).strip()
        except Exception as e:
            logger.error(f"ACLR measurement failed: {e}")
            return ''