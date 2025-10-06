# File: src/measurements/spur_search.py
# Author: [Your Name or Company]
# Date: October 06, 2025
# Description: This module handles spur search measurements using FSW-K50. It configures instruments,
#              performs measurements, and retrieves results while filtering out the fundamental frequency.

import logging
from src.utils.utils import method_timer
from src.instruments.bench import bench

logger = logging.getLogger(__name__)


class SpurSearch:
    """Class for FSW-K50 spur measurements.

    This class manages the setup, execution, and retrieval of spur search measurements.
    """

    def __init__(self, fundamental_ghz, rbw_mhz=0.01, spur_limit_dbm=-95, pwr=0):
        """Initialize the SpurSearch class for FSW-K50 spur measurements.

        Args:
            fundamental_ghz (float): Fundamental frequency in GHz.
            rbw_mhz (float, optional): Resolution bandwidth in MHz, default 0.01.
            spur_limit_dbm (float, optional): Spur limit in dBm, default -95.
            pwr (float, optional): VSG power in dBm, default 0.
        """
        self.fundamental_ghz = fundamental_ghz
        self.rbw_mhz = rbw_mhz
        self.spur_limit_dbm = spur_limit_dbm
        self.pwr = pwr
        self.frequency = fundamental_ghz * 1e9
        self.VSA = bench().VSA_start()  # Start VSA connection
        self.VSA.sock.settimeout(30)  # Set timeout
        self.VSG = bench().VSG_start()  # Start VSG connection
        self.VSG.sock.settimeout(30)  # Set timeout
        logger.info(f"SpurSearch initialized: fundamental={fundamental_ghz} GHz, "
                    f"RBW={rbw_mhz} MHz, spur_limit={spur_limit_dbm} dBm, VSG_power={pwr} dBm")

    @method_timer
    def VSA_config(self, fundamental_ghz=None, rbw_mhz=None, spur_limit_dbm=None):
        """Configure the FSW for spur search measurement.

        Args:
            fundamental_ghz (float, optional): Override fundamental frequency in GHz.
            rbw_mhz (float, optional): Override resolution bandwidth in MHz.
            spur_limit_dbm (float, optional): Override spur limit in dBm.
        """
        try:
            # Use provided parameters or instance defaults
            fundamental_ghz = fundamental_ghz if fundamental_ghz is not None else self.fundamental_ghz
            rbw_mhz = rbw_mhz if rbw_mhz is not None else self.rbw_mhz
            spur_limit_dbm = spur_limit_dbm if spur_limit_dbm is not None else self.spur_limit_dbm

            self.VSA.query('*RST;*OPC?')  # Reset VSA
            logger.info("FSW reset for spur search")

            # Define frequency ranges for spur search
            start_freq1 = (fundamental_ghz / 2) * 1e9
            stop_freq1 = fundamental_ghz * 1e9 - 1e6
            start_freq2 = fundamental_ghz * 1e9 + 1e6
            stop_freq2 = (2 * fundamental_ghz) * 1e9  #

            self.VSA.write('INIT:CONT OFF')  # Disable continuous sweep
            #  self.VSA.query('INIT:IMM;*OPC?')  # Initiate sweep and wait for completion

            # Configure Range 1 Fo/2 --> Fo-1MHz
            self.VSA.write(f"SENS:FREQ:STAR {start_freq1:.0f}")
            self.VSA.write(f"SENS:FREQ:STOP {stop_freq1:.0f}")
            self.VSA.write(':DISP:WIND1:SUBW:TRAC1:MODE AVER')  # Set trace mode to average
            self.VSA.write(':SENS:AVER:COUN 5')
            self.VSA.write(':SENS:WIND1:DET1:FUNC RMS')  # Set RMS detector
            self.VSA.write(':SENS:LIST:RANG1:FILT:TYPE NORM')  # Normal filter 3dB
            self.VSA.write(f':SENS:BAND:RES {rbw_mhz * 1e6}')
            self.VSA.write(':SENS:SWE:TIME:AUTO ON')  # Sweep Time Auto
            self.VSA.write('SENS:SWE:TYPE FFT')  # Set sweep type to auto
            self.VSA.write('SENS:SWE:OPT SPE')  # Set sweep optimization to auto
            self.VSA.write(f'SENS:SWE:WIND1:POIN {100001}')  # Set sweep points to 2001
            self.VSA.write(f'DISP:WIND1:TRAC:Y:SCAL:RLEV {-30}')  # Set reference level to -40 dBm
            self.VSA.write('SENS:INP:ATT:AUTO OFF')  # Auto attenuation OFF
            self.VSA.write(f':INP:ATT {0}   ')  # Set attenuation to 0 dB
            self.VSA.write('INP:GAIN:STAT ON')  # Sweep Time Auto
            self.VSA.write('INP:GAIN:VAL 30')  # Set gain to 30 dB
            self.VSA.write('SENS:POW:NCOR ON')  # Enable power noise correction
            #  self.VSA.write(f'CALC1:DLIN1 {spur_limit_dbm}')
            self.VSA.write('CALC1:MARK1:FUNC:FPE:STAT ON')
            self.VSA.write(f'CALC1:MARK1:X:SLIM:LEFT {start_freq1}')  # Set left limit for spur detection
            self.VSA.write(f'CALC1:MARK1:X:SLIM:RIGH {stop_freq2}')  # Set right limit for spur detection
            self.VSA.write(f'CALC1:THR {spur_limit_dbm}')  # Set threshold for spur detection
            self.VSA.write('CALC1:MARK1:X:SLIM:STAT ON')
            self.VSA.write('CALC1:THR:STAT ON')
            #  self.VSA.query('INIT:IMM;*OPC?')  # Initiate sweep and wait for completion
            #  self.VSA.write('DISP:WIND1:SUBW:TRAC1:Y:SCAL:AUTO ONCE')  # Auto scale Y-axis
            logger.info("Spur detection table configured")
            logger.info(f"Range 1: {start_freq1 / 1e9:.3f}–{stop_freq1 / 1e9:.3f} GHz")

        except Exception as e:
            logger.error(f"Failed to configure FSW: {e}")
            raise

    @method_timer
    def VSG_config(self, frequency_ghz=None, pwr=None):
        """Configure the VSG for spur search.

        Args:
            frequency_ghz (float, optional): Frequency in GHz.
            pwr (float, optional): Power in dBm.
        """
        try:
            frequency = (frequency_ghz * 1e9) if frequency_ghz is not None else self.frequency
            pwr = pwr if pwr is not None else self.pwr

            self.VSG.query('*RST;*OPC?')  # Reset VSG
            self.VSG.write(f"SOUR:FREQ:CW {frequency:.0f}")  # Set frequency
            self.VSG.write(f"SOUR:POW:LEV:IMM:AMPL {pwr:.2f}")  # Set power

            # Configure multi-carrier arbitrary waveform for testing
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier1:MODE ARB')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier1:COUNt 4')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier1:FREQuency -1000000000')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier2:FREQuency -500000000')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier3:FREQuency 600000000')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier4:FREQuency 1000000000')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier1:POWer -45')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier2:POWer -20')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier3:POWer -25')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier4:POWer -50')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier1:STATe 1')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier2:STATe 1')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier3:STATe 1')
            self.VSG.write('SOURce1:BB:ARBitrary:MCARrier:CARRier4:STATe 1')
            self.VSG.query('SOURce1:BB:ARBitrary:MCARrier:CLOad;*OPC?')
            self.VSG.write('SOURce1:BB:ARBitrary:TRIGger:OUTPut1:MODE REST')
            self.VSG.write('SOURce1:BB:ARBitrary:STATe 1')
            self.VSG.write('OUTPut1:STATe 1')

            logger.info(f"VSG set: frequency={frequency / 1e9:.3f} GHz, power={pwr:.2f} dBm")
        except Exception as e:
            logger.error(f"Failed to configure VSG: {e}")
            raise

    @method_timer
    def VSx_freq(self, freq):
        """Set frequency for both VSA and VSG.

        Args:
            freq (float): Frequency in Hz.
        """
        logger.info(f"Setting VSA/VSG frequency to {freq / 1e9:.3f} GHz")
        self.VSA.write(f"SENS:FREQ:CENT {freq:.0f}")
        self.VSG.write(f"SOUR:FREQ:CW {freq:.0f}")
        self.frequency = freq

    @method_timer
    def measure(self):
        """Perform the spur search measurement."""
        try:
            self.VSA.write(':INIT:CONT OFF')  # Disable continuous sweep
            self.VSA.query("INIT:IMM;*OPC?")  # Initiate sweep and wait
            logger.info("Spur search measurement completed")
        except Exception as e:
            logger.error(f"Spur search measurement failed: {e}")
            raise

    @method_timer
    def get_results(self):
        """Retrieve spur search results.

        Returns:
            list: List of tuples (frequency_hz, power_dbm) for detected spurs, excluding fundamental.
        """
        try:
            # Query the number of spurs detected
            spur_count = int(self.VSA.query(":CALC:MARK:FUNC:FPE:COUN?").strip())
            spurs = []

            if spur_count > 0:
                self.VSA.write('DISP:WIND1:SUBW:TRAC1:Y:SCAL:AUTO ONCE')  # Auto scale Y-axis
                # Query all spur frequencies and amplitudes at once
                freq_response = self.VSA.query(":CALC:MARK:FUNC:FPE:X?").strip()
                power_response = self.VSA.query(":CALC:MARK:FUNC:FPE:Y?").strip()

                # Split the comma-separated responses into lists
                freqs = [float(f) for f in freq_response.split(",") if f.strip()]
                powers = [float(p) for p in power_response.split(",") if p.strip()]

                # Ensure the number of frequencies and powers match
                if len(freqs) != spur_count or len(powers) != spur_count:
                    logger.warning(
                        f"Mismatch in spur data: expected {spur_count} spurs, got {len(freqs)} frequencies and {len(powers)} powers")
                    return spurs

                # Filter spurs to exclude fundamental frequency (±10 MHz)
                fundamental_hz = self.fundamental_ghz * 1e9
                exclusion_window_hz = 10e6  # ±10 MHz around fundamental
                for i, (freq_hz, power_dbm) in enumerate(zip(freqs, powers), 1):
                    if abs(freq_hz - fundamental_hz) > exclusion_window_hz:
                        spurs.append((freq_hz, power_dbm))
                        logger.info(f"Spur {i}: {freq_hz / 1e9:.6f} GHz, {power_dbm:.2f} dBm")
                    else:
                        logger.debug(
                            f"Excluding spur at {freq_hz / 1e9:.6f} GHz (near fundamental {fundamental_hz / 1e9:.3f} GHz)")

            if not spurs:
                logger.info("No spurs detected after filtering")
            return spurs
        except Exception as e:
            logger.error(f"Failed to retrieve spur results: {e}")
            return []

    def close(self):
        """Close VSA and VSG connections."""
        try:
            if self.VSA:
                self.VSA.close()
                logger.info("FSW connection closed")
            if self.VSG:
                self.VSG.write("OUTP:STAT OFF")  # Turn off VSG output
                self.VSG.close()
                logger.info("VSG connection closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")