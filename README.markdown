RF Measurement Project
Overview
This project provides Python scripts to control a Vector Signal Analyzer (VSA) and Vector Signal Generator (VSG) for RF measurements, supporting LTE, 5G NR (FR1), Sub-Thermal Noise (STN), and Spur Search tests. Test parameters and execution flags are defined in a JSON configuration file (config/test_inputs.json). Results are saved to an Excel file (results_output.xlsx) for analysis.
Project Structure
Qorvo_STNoise_LTE_5GNR_meas_with_timing/
├── src/                     # Source code
│   ├── instruments/         # Instrument control and communication
│   │   ├── iSocket.py      # Custom socket communication library
│   │   ├── bench.py        # Instrument connection logic
│   │   ├── bench_config.ini # Instrument IP configuration
│   ├── measurements/        # Measurement driver scripts
│   │   ├── nr5g_fr1.py     # 5G NR measurement driver
│   │   ├── lte.py          # LTE measurement driver
│   │   ├── spur_search.py   # Spur Search measurement driver
│   │   ├── SubThermalNoise.py # STN measurement driver
│   ├── utils/               # Utility functions (e.g., timing decorators)
│   ├── main.py              # Main script to run measurements
├── config/                  # Configuration files
│   ├── test_inputs.json     # User-defined test parameters and flags
│   ├── bench_config.ini     # Instrument IP settings
├── tests/                   # Unit tests for validation
├── scripts/                 # Automation scripts (planned, currently empty)
├── logs/                    # Log files generated during execution
├── docs/                    # Project documentation
├── requirements.txt         # Python dependencies
├── setup.bat                # Windows setup script
├── .gitignore               # Git ignore rules
├── .gitattributes           # Git attributes
└── pyproject.toml           # Project metadata and build configuration

Setup
Prerequisites

Python: 3.8 or higher
Operating Systems: Windows, Linux, or macOS
Hardware: Network-accessible VSA (e.g., Rohde & Schwarz FSW) and VSG (e.g., Rohde & Schwarz SMW) with SCPI command support
Network: Stable LAN connection to instruments

Install Dependencies
pip install -r requirements.txt

The iSocket library is included in src/instruments/iSocket.py. Alternatively, you can use pyvisa by installing pyvisa>=1.12.0 and updating src/instruments/bench.py.
Configure Instruments

Update config/bench_config.ini with the IP addresses of your VSA and VSG:[Settings]
VSA_IP = 192.168.200.20
VSG_IP = 192.168.200.10



Configure Test Parameters

Edit config/test_inputs.json to define test parameters for LTE, 5G NR, STN, and Spur Search. The file contains four sections:
lte: LTE signal measurements
nr5g: 5G NR (FR1) measurements
STN: Sub-Thermal Noise measurements
spur_search: Spur detection


Example configuration:{
  "lte": [
    {
      "run": true,
      "center_frequency_ghz": 6.201,
      "power_dbm": -10.0,
      "waveform_file": "C:/Waveforms/LTE_UL_20MHz_QPSK_100RB_0RBO.wv",
      "setup_file": "C:/Setups/LTE_UL_20MHz_QPSK_100RB_0RBO.dfl",
      "measure_aclr": true
    }
  ],
  "nr5g": [
    {
      "run": true,
      "center_frequency_ghz": 6.123,
      "power_dbm": -5.0,
      "waveform_file": "C:/Waveforms/5GNR_UL_20MHz_QAM256_30kHz_51RB_0RBO.wv",
      "setup_file": "C:/Setups/5GNR_UL_20MHz_QAM256_30kHz_51RB_0RBO.dfl",
      "measure_aclr": true
    }
  ],
  "STN": [
    {
      "run": true,
      "center_frequency_ghz": 0.617,
      "iterations": 10
    }
  ],
  "spur_search": [
    {
      "run": true,
      "fundamental_frequency_ghz": 6.000,
      "rbw_mhz": 0.01,
      "spur_limit_dbm": -95,
      "power_dbm": -10.0
    }
  ]
}


Notes on test_inputs.json:
Frequencies: Specify in GHz as single values, lists, or ranges (e.g., {"range": {"start_ghz": 0.617, "stop_ghz": 0.961, "step_mhz": 10}}).
Power Inputs: Use single values or arrays for power sweeps (e.g., [-10.0, -9.0]).
Run Flags: Set "run": true to enable a test; false to skip.
Waveform/Setup Files: For LTE and NR5G, use specific naming conventions:
LTE: LTE_[UL|DL]_[bandwidth]MHz_[modulation]_[RB]RB_[RBO]RBO.wv (waveform) or .dfl (setup)
NR5G: 5GNR_[UL|DL]_[bandwidth]MHz_[modulation]_[scs]kHz_[RB]RB_[RBO]RBO.wv (waveform) or .dfl (setup)


Ensure numeric values for frequencies/powers and boolean flags.
Save with UTF-8 encoding.



Usage
Run the measurements using:
python src/main.py

Supported Measurements

LTE Measurement: Measures EVM and ACLR for LTE signals.
5G NR Measurement: Measures EVM and ACLR for 5G NR (FR1) signals.
Sub-Thermal Noise (STN) Measurement: Measures noise power with statistical analysis.
Spur Search Measurement: Detects spurs excluding the fundamental frequency.

Parameter Sweeps

Frequency Sweeps: Use lists or ranges in center_frequency_ghz or fundamental_frequency_ghz.
Power Sweeps: Use arrays in power_dbm.

Output
Results are saved to:

results_output.xlsx: Excel file with "Test Data" (detailed results) and "Test Statistics" (summary metrics) sheets.

Requirements

Python: 3.8+
Libraries:
numpy>=1.24.0
pandas>=2.0.0
openpyxl>=3.1.0
iSocket (custom, included in src/instruments/iSocket.py)
Optional: pyvisa>=1.12.0 (alternative to iSocket)



Notes

Ensure VSA and VSG are network-accessible and support SCPI commands.
Customize SCPI commands in src/measurements/ (e.g., nr5g_fr1.py, lte.py) for different instrument models.
Add unit tests in tests/ to validate functionality.
Generated files (results_output.xlsx, logs/) are excluded from version control via .gitignore.
The scripts/ directory is reserved for future automation scripts.
The pyproject.toml file defines project metadata and dependencies for build tools like poetry or flit.

Contributing
Contributions are welcome! Please:

Fork the repository.
Create a feature branch (git checkout -b feature/your-feature).
Follow PEP 8 for Python code style.
Add unit tests in tests/ for new functionality.
Commit changes (git commit -m 'Add your feature').
Push to the branch (git push origin feature/your-feature).
Open a pull request with a clear description of changes.

License
This project is licensed under the MIT License. See the LICENSE file for details.