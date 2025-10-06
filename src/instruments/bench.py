"""Instrument control for VSA and VSG.

Manages connections and configurations for Vector Signal Analyzer (VSA) and
Vector Signal Generator (VSG) instruments.
"""

from src.instruments.iSocket import iSocket
import configparser
import os


class bench:
    """Class to manage VSA and VSG instrument connections and settings."""

    def __init__(self):
        config = configparser.ConfigParser()
        # Construct the path to bench_config.ini relative to this script's location
        config_file = os.path.join(os.path.dirname(__file__), 'bench_config.ini')
        if not config.read(config_file):
            raise FileNotFoundError(f"Configuration file '{config_file}' not found.")
        if 'Settings' not in config:
            raise ValueError(f"Configuration file '{config_file}' is missing the 'Settings' section.")
        self.VSA_IP = config['Settings']['VSA_IP']  # Load VSA IP
        self.VSG_IP = config['Settings']['VSG_IP']  # Load VSG IP
        self.VSA = None
        self.VSG = None

    def bench_verify(self):
        """Verify connectivity to VSA and VSG by querying their IDs."""
        try:
            self.VSA = iSocket().open(self.VSA_IP, 5025)
            self.VSG = iSocket().open(self.VSG_IP, 5025)
            print(f"\nVSA ID: {self.VSA.idn}")
            print(f"VSG ID: {self.VSG.idn}")
        except Exception as e:
            print(f"Error connecting to instruments: {e}")
            raise

    def VSA_start(self):
        """Establish connection to VSA and return the socket object."""
        try:
            self.VSA = iSocket().open(self.VSA_IP, 5025)
            return self.VSA
        except Exception as e:
            print(f"Error starting VSA: {e}")
            raise

    def VSG_network_reset(self):
        """Reset VSG network settings and wait for completion."""
        self.VSG_start()
        self.VSG.query('SYST:COMM:NETW:REST;*OPC?')

    def VSG_start(self):
        """Establish connection to VSG and return the socket object."""
        try:
            self.VSG = iSocket().open(self.VSG_IP, 5025)
            return self.VSG
        except Exception as e:
            print(f"Error starting VSG: {e}")
            raise

    def set_VSx_freq(self, freq):
        """Set center frequency for both VSA and VSG.

        Args:
            freq (float): Frequency in Hz.
        """
        self.VSA.write(f':SENS:FREQ:CENT {freq}')
        self.VSG.write(f':SOUR1:FREQ:CW {freq}')

    def set_inst_off(self):
        self.VSA.write(':SYST:SHUT')
        self.VSG.write(':SYST:SHUT')
        if hasattr(self.VSA, 'sock') and self.VSA.sock:
            self.VSA.sock.close()
        if hasattr(self.VSG, 'sock') and self.VSG.sock:
            self.VSG.sock.close()
