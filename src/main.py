# File: main.py
# Main script for running RF measurements (NR5G, LTE, SpurSearch, and STN focus)
import logging
import os
import json
import pandas as pd
import statistics
import numpy as np
import re
from src.measurements.nr5g_fr1 import std_insr_driver as NR5GDriver
from src.measurements.lte import std_insr_driver as LTEDriver
from src.measurements.spur_search import SpurSearch
from src.measurements.SubThermalNoise import option_functions as STN
from src.utils.utils import method_timer

# Configure logging
logger = logging.getLogger(__name__)
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'project.log')),
        logging.StreamHandler()
    ]
)

results = []
previous_config = None
previous_freq = None  # Track previous frequency

def format_frequency(fundamental_ghz):
    """Format fundamental frequency for logging/display."""
    if isinstance(fundamental_ghz, (int, float)):
        return f"{fundamental_ghz:.3f} GHz"
    elif isinstance(fundamental_ghz, list):
        return ", ".join(f"{freq:.3f} GHz" for freq in fundamental_ghz)
    elif isinstance(fundamental_ghz, dict) and "range" in fundamental_ghz:
        r = fundamental_ghz["range"]
        return f"range {r['start_ghz']:.3f}–{r['stop_ghz']:.3f} GHz, step {r['step_mhz']} MHz"
    else:
        return str(fundamental_ghz)

def run_nr5g_measurement(test_config, test_set, instr):
    """Run NR5G measurement with specified configuration."""
    global previous_config, previous_freq
    try:
        freq = test_config["center_frequency_ghz"] * 1e9
        pwr = test_config["power_dbm"]
        waveform_file = test_config.get("waveform_file", None)
        setup_file = test_config.get("setup_file", None)
        measure_aclr = test_config.get("measure_aclr", True)

        current_config = {
            "waveform_file": waveform_file,
            "setup_file": setup_file
        }

        logger.info(f"Starting NR5G test set {test_set}: freq={freq / 1e9:.3f}GHz, pwr={pwr}dBm, "
                    f"waveform_file={waveform_file}, setup_file={setup_file}")
        timings = {}

        if previous_config != current_config:
            logger.info("Waveform configuration changed, reconfiguring VSA/VSG")
            _, timings["VSG_Config"] = instr.VSG_Config()
            _, timings["VSA_Config"] = instr.VSA_Config(freq=freq)
            previous_config = current_config
            previous_freq = freq  # Update frequency after VSA/VSG config
        else:
            logger.info("Waveform configuration unchanged, skipping VSA/VSG config")

        # Use tolerance for floating-point comparison
        if previous_freq is None or abs(previous_freq - freq) > 1e-3:
            logger.info(f"Frequency changed, setting VSA/VSG to {freq / 1e9:.3f}GHz")
            _, timings["VSx_freq"] = instr.VSx_freq(freq=freq)
            previous_freq = freq
        else:
            logger.info("Frequency unchanged, skipping VSx_freq")
            timings["VSx_freq"] = 0.0  # Log zero time when skipped

        instr.VSG_pwr(pwr=pwr)
        config_result, timings["VSA_get_info"] = instr.VSA_get_info()
        # Construct config summary to include waveform-specific parameters
        config = (
            f"{freq / 1e9:.3f}GHz_"
            f"{getattr(instr, 'bw', 10)}MHz_"
            f"{getattr(instr, 'dupl', 'FDD')}_"
            f"{getattr(instr, 'ldir', 'UL')}_"
            f"{getattr(instr, 'scs', 30)}_{getattr(instr, 'rb', 24)}RB_"
            f"{getattr(instr, 'rbo', 0)}RBO_"
            f"{getattr(instr, 'mod', '256QAM')}_"
            f"waveform_{os.path.basename(waveform_file) if waveform_file else 'default'}_"
            f"setup_{os.path.basename(setup_file) if setup_file else 'default'}"
        )
        _, timings["VSA_sweep_evm"] = instr.VSA_sweep()
        evm, timings["VSA_get_EVM"] = instr.VSA_get_EVM()
        logger.info(f"NR5G EVM: {evm:.2f} dB")
        ch_pwr = acp_l = acp_u = alt_l = alt_u = None
        timings["VSA_get_ACLR"] = 0.0  # Default in case ACLR is not measured
        if measure_aclr:
            aclr_vals, timings["VSA_get_ACLR"] = instr.VSA_get_ACLR()
            logger.info(f"NR5G ACLR: {aclr_vals}")
            if aclr_vals:
                aclr_parts = aclr_vals.split(',')
                if len(aclr_parts) == 5:
                    ch_pwr, acp_l, acp_u, alt_l, alt_u = map(float, aclr_parts)
        results.append({
            "test_set": test_set,
            "type": "NR5G",
            "center_frequency_hz": float(freq),
            "power_dbm": float(pwr),
            "resource_blocks": getattr(instr, 'rb', None),
            "resource_block_offset": getattr(instr, 'rbo', None),
            "channel_bandwidth_mhz": getattr(instr, 'bw', None),
            "modulation_type": getattr(instr, 'mod', None),
            "subcarrier_spacing_khz": getattr(instr, 'scs', None),
            "duplexing": getattr(instr, 'dupl', None),
            "link_direction": getattr(instr, 'ldir', None),
            "waveform_file": waveform_file,
            "setup_file": setup_file,
            "config": config,
            "evm": float(evm) if evm is not None else None,
            "ch_pwr": float(ch_pwr) if ch_pwr is not None else None,
            "acp_lower": float(acp_l) if acp_l is not None else None,
            "acp_upper": float(acp_u) if acp_u is not None else None,
            "alt_lower": float(alt_l) if alt_l is not None else None,
            "alt_upper": float(alt_u) if alt_u is not None else None,
            "timings": timings
        })
    except Exception as e:
        logger.error(f"NR5G test set {test_set} failed: {e}", exc_info=True)

def run_lte_measurement(test_config, test_set, instr):
    """Run LTE measurement with specified configuration."""
    global previous_config, previous_freq
    try:
        freq = test_config["center_frequency_ghz"] * 1e9
        pwr = test_config["power_dbm"]
        waveform_file = test_config.get("waveform_file", None)
        setup_file = test_config.get("setup_file", None)
        measure_aclr = test_config.get("measure_aclr", True)

        current_config = {
            "waveform_file": waveform_file,
            "setup_file": setup_file
        }

        logger.info(f"Starting LTE test set {test_set}: freq={freq / 1e9:.3f}GHz, pwr={pwr}dBm, "
                    f"waveform_file={waveform_file}, setup_file={setup_file}")
        timings = {}

        if previous_config != current_config:
            logger.info("Waveform configuration changed, reconfiguring VSA/VSG")
            _, timings["VSG_Config"] = instr.VSG_Config()
            _, timings["VSA_Config"] = instr.VSA_Config(freq=freq)
            previous_config = current_config
            previous_freq = freq  # Update frequency after VSA/VSG config
        else:
            logger.info("Waveform configuration unchanged, skipping VSA/VSG config")

        # Use tolerance for floating-point comparison
        if previous_freq is None or abs(previous_freq - freq) > 1e-3:
            logger.info(f"Frequency changed, setting VSA/VSG to {freq / 1e9:.3f}GHz")
            _, timings["VSx_freq"] = instr.VSx_freq(freq=freq)
            previous_freq = freq
        else:
            logger.info("Frequency unchanged, skipping VSx_freq")
            timings["VSx_freq"] = 0.0  # Log zero time when skipped

        instr.VSG_pwr(pwr=pwr)
        config_result, timings["VSA_get_info"] = instr.VSA_get_info()
        # Construct config summary to include waveform-specific parameters
        config = (
            f"{freq / 1e9:.3f}GHz_"
            f"{getattr(instr, 'bw', 20)}MHz_"
            f"{getattr(instr, 'dupl', 'FDD')}_"
            f"{getattr(instr, 'ldir', 'UL')}_15kHz_"
            f"{getattr(instr, 'rb', 100)}RB_"
            f"{getattr(instr, 'rbo', 0)}RBO_"
            f"{getattr(instr, 'mod', 'QAM256')}_"
            f"waveform_{os.path.basename(waveform_file) if waveform_file else 'default'}_"
            f"setup_{os.path.basename(setup_file) if setup_file else 'default'}"
        )
        _, timings["VSA_sweep_evm"] = instr.VSA_sweep()
        evm, timings["VSA_get_EVM"] = instr.VSA_get_EVM()
        logger.info(f"LTE EVM: {evm:.2f} dB")
        ch_pwr = acp_l = acp_u = alt_l = alt_u = None
        timings["VSA_get_ACLR"] = 0.0  # Default in case ACLR is not measured
        if measure_aclr:
            aclr_vals, timings["VSA_get_ACLR"] = instr.VSA_get_ACLR()
            logger.info(f"LTE ACLR: {aclr_vals}")
            if aclr_vals:
                aclr_parts = aclr_vals.split(',')
                if len(aclr_parts) == 5:
                    ch_pwr, acp_l, acp_u, alt_l, alt_u = map(float, aclr_parts)
        results.append({
            "test_set": test_set,
            "type": "LTE",
            "center_frequency_hz": float(freq),
            "power_dbm": float(pwr),
            "resource_blocks": getattr(instr, 'rb', None),
            "resource_block_offset": getattr(instr, 'rbo', None),
            "channel_bandwidth_mhz": getattr(instr, 'bw', None),
            "modulation_type": getattr(instr, 'mod', None),
            "subcarrier_spacing_khz": 15,  # Fixed for LTE
            "duplexing": getattr(instr, 'dupl', None),
            "link_direction": getattr(instr, 'ldir', None),
            "waveform_file": waveform_file,
            "setup_file": setup_file,
            "config": config,
            "evm": float(evm) if evm is not None else None,
            "ch_pwr": float(ch_pwr) if ch_pwr is not None else None,
            "acp_lower": float(acp_l) if acp_l is not None else None,
            "acp_upper": float(acp_u) if acp_u is not None else None,
            "alt_lower": float(alt_l) if alt_l is not None else None,
            "alt_upper": float(alt_u) if alt_u is not None else None,
            "timings": timings
        })
    except Exception as e:
        logger.error(f"LTE test set {test_set} failed: {e}", exc_info=True)

def run_spur_search_measurement(test_config, test_set, instr):
    """Run spur search measurement."""
    try:
        fundamental_ghz = test_config["fundamental_frequency_ghz"]
        rbw_mhz = test_config.get("rbw_mhz", 0.01)
        spur_limit_dbm = test_config.get("spur_limit_dbm", -95)
        pwr = test_config.get("power_dbm", -70)

        if isinstance(fundamental_ghz, list):
            fundamental_ghz = instr.fundamental_ghz
        elif isinstance(fundamental_ghz, dict):
            logger.error(f"Range input not supported in run_spur_search_measurement: {fundamental_ghz}")
            raise ValueError("Range input should be processed in main loop")

        logger.info(f"Starting SpurSearch test set {test_set}: fundamental={format_frequency(fundamental_ghz)}, "
                    f"RBW={rbw_mhz:.3f} MHz, limit={spur_limit_dbm:.2f} dBm, power={pwr:.2f} dBm")
        timings = {}

        _, timings["VSG_config"] = instr.VSG_config(frequency_ghz=fundamental_ghz, pwr=pwr)
        _, timings["VSA_config"] = instr.VSA_config(fundamental_ghz=fundamental_ghz, rbw_mhz=rbw_mhz, spur_limit_dbm=spur_limit_dbm)

        _, timings["measure"] = instr.measure()
        results_data, timings["get_results"] = instr.get_results()
        logger.debug(f"SpurSearch results for {fundamental_ghz:.3f} GHz: {results_data}")

        config = f"{fundamental_ghz:.3f}GHz_Spur_RBW{rbw_mhz:.3f}MHz_Limit{spur_limit_dbm:.2f}dBm"
        result = {
            "test_set": test_set,
            "type": "SpurSearch",
            "fundamental_frequency_hz": float(fundamental_ghz) * 1e9,
            "rbw_hz": rbw_mhz * 1e6,
            "spur_limit_dbm": spur_limit_dbm,
            "power_dbm": pwr,
            "spurs": [{"frequency_hz": freq_hz, "power_dbm": power_dbm} for freq_hz, power_dbm in results_data],
            "config": config,
            "timings": timings.copy()
        }
        if not results_data:
            result["error"] = "No spurs detected"
        results.append(result)
        return test_set + 1
    except Exception as e:
        logger.error(f"SpurSearch test set {test_set} failed: {e}", exc_info=True)
        results.append({
            "test_set": test_set,
            "type": "SpurSearch",
            "fundamental_frequency_hz": None,
            "rbw_hz": rbw_mhz * 1e6,
            "spur_limit_dbm": spur_limit_dbm,
            "power_dbm": pwr,
            "spurs": [],
            "config": f"Spur_RBW{rbw_mhz:.3f}MHz_Limit{spur_limit_dbm:.2f}dBm",
            "timings": timings,
            "error": str(e)
        })
        return test_set + 1

def run_stn_measurement(stn_instr, freq, test_set, swp_time=1.0, iterations=5):
    """Run STN measurement with specified configuration."""
    logger.debug(f"Starting STN test set {test_set}: freq={freq / 1e9:.3f}GHz, iterations={iterations}")
    try:
        timings = {}
        total_test_time = 0.0
        logger.debug("Calling VSA_Config")
        _, timings["VSA_Config"] = stn_instr.VSA_Config()
        total_test_time += timings["VSA_Config"]
        meas = []
        print('Frequency, NoiseMkr, CapTime, MeasTime')
        for i in range(iterations):
            logger.debug(f"Running STN iteration {i + 1}")
            try:
                marker, delta_time = stn_instr.get_VSA_sweep_noise_mkr()
                if delta_time is None:
                    logger.warning(f"STN iteration {i + 1}: No timing returned, using 0.0")
                    delta_time = 0.0
                meas.append({"marker": float(marker), "meas_time": float(delta_time)})
                logger.info(f"STN iteration {i + 1}: marker={marker:.2f}dBm, meas_time={delta_time:.3f}sec")
                print(f'{stn_instr.frequency / 1e9:7.3f}, {marker:.2f}dBm, {delta_time:.3f}sec, {delta_time:.3f}sec')
                timings[f"get_VSA_sweep_noise_mkr_{i + 1}"] = delta_time
                total_test_time += delta_time
            except Exception as e:
                logger.error(f"STN iteration {i + 1} failed: {e}", exc_info=True)
                meas.append({"marker": None, "meas_time": 0.0})
                timings[f"get_VSA_sweep_noise_mkr_{i + 1}"] = 0.0
        stats = None
        valid_markers = [m["marker"] for m in meas if m["marker"] is not None]
        if len(valid_markers) >= 2:
            stats = stn_instr.get_Array_stats(np.array(valid_markers))
            logger.info(f"STN stats: {stats}")
        freq_ghz = freq / 1e9
        config = f"{freq_ghz:.3f}GHz_STN_{swp_time:.1f}sec"
        result = {
            "test_set": test_set,
            "type": "STN",
            "center_frequency_hz": freq,
            "sweep_time": swp_time,
            "iterations": iterations,
            "config": config,
            "markers": meas,
            "stats": stats,
            "timings": timings,
            "total_test_time": total_test_time
        }
        if not valid_markers:
            result["error"] = "No successful measurements"
        results.append(result)
    except Exception as e:
        logger.error(f"STN measurement failed for test set {test_set}: {e}", exc_info=True)
        results.append({
            "test_set": test_set,
            "type": "STN",
            "center_frequency_hz": freq,
            "sweep_time": swp_time,
            "iterations": iterations,
            "config": f"{freq / 1e9:.3f}GHz_STN_{swp_time:.1f}sec",
            "markers": [],
            "stats": None,
            "timings": {},
            "total_test_time": 0.0,
            "error": str(e)
        })

if __name__ == '__main__':
    logger.info("Starting RF measurement script")
    json_path = os.path.join(os.path.dirname(__file__), 'test_inputs.json')
    default_inputs = {
        "nr5g": [{
            "run": False,
            "center_frequency_ghz": [6.123, 6.223, 6.323, 6.423],
            "power_dbm": [-20, -16, -12, -8, -4, 0, 4, 8, 10],
            "measure_aclr": True,
            "waveform_file": "/var/user/5GNR/Qorvo_EVM_opt/5GNR_UL_10MHz_256QAM_30kHz_24RB_0RBO.wv",
            "setup_file": "C:/r_s/instr/user/Qorvo/5GNR_UL_10MHz_256QAM_30kHz_24RB_0RBO.dfl"
        }],
        "lte": [{
            "run": True,
            "center_frequency_ghz": [6.201, 6.501],
            "power_dbm": [-10.0, -9.0],
            "resource_block_offset": 0,
            "channel_bandwidth_mhz": 5,
            "modulation_type": "QPSK",
            "duplexing": "TDD",
            "link_direction": "UL",
            "measure_aclr": True,
            "waveform_file": "/var/user/LTE/Qorvo/LTE_UL_5MHz_QPSK_15kHz_25RB_0RBO.wv",
            "setup_file": "C:/r_s/instr/user/Qorvo/LTE_UL_5MHz_QPSK_15kHz_25RB_0RBO.dfl"
        }],
        "spur_search": [{
            "run": True,
            "fundamental_frequency_ghz": [2.43, 2.44],
            "rbw_mhz": 0.02,
            "spur_limit_dbm": -122,
            "power_dbm": -70
        }, {
            "run": True,
            "fundamental_frequency_ghz": {"range": {"start_ghz": 2.4, "stop_ghz": 2.481, "step_mhz": 20}},
            "rbw_mhz": 0.02,
            "spur_limit_dbm": -122,
            "power_dbm": -70
        }],
        "STN": [{
            "run": True,
            "center_frequency_ghz": {"range": {"start_ghz": 2.4, "stop_ghz": 2.481, "step_mhz": 5}},
            "iterations": 5
        }]
    }
    try:
        with open(json_path, 'r') as f:
            inputs = json.load(f)
        logger.info(f"Loaded test inputs from {json_path}")
    except Exception as e:
        logger.error(f"Error reading JSON file: {e}", exc_info=True)
        print(f"Error reading JSON file: {e}")
        inputs = default_inputs

    logger.debug(f"Test inputs: {json.dumps(inputs, indent=2)}")

    test_set = 1
    instr = None
    # Run NR5G tests
    for test in inputs.get("nr5g", []):
        if test.get("run", False):
            logger.debug(f"Processing NR5G test: {test}")
            frequencies = test["center_frequency_ghz"] if isinstance(test["center_frequency_ghz"], list) else [
                test["center_frequency_ghz"]]
            try:
                instr = NR5GDriver(
                    freq=frequencies[0] * 1e9,
                    pwr=test["power_dbm"][0],
                    waveform_file=test.get("waveform_file", None),
                    setup_file=test.get("setup_file", None)
                )
                for freq in frequencies:
                    for pwr in test["power_dbm"]:
                        test_config = test.copy()
                        test_config["center_frequency_ghz"] = freq
                        test_config["power_dbm"] = pwr
                        print(f"\n=== Test Set {test_set} (NR5G) ===")
                        run_nr5g_measurement(test_config, test_set, instr)
                        test_set += 1
            except Exception as e:
                logger.error(f"NR5G test initialization failed: {e}", exc_info=True)
            finally:
                if instr:
                    try:
                        NR5GDriver.close_connections()
                    except Exception as e:
                        logger.error(f"Error closing NR5G connections: {e}", exc_info=True)
                instr = None

    # Run LTE tests
    for test in inputs.get("lte", []):
        if test.get("run", False):
            logger.debug(f"Processing LTE test: {test}")
            frequencies = test["center_frequency_ghz"] if isinstance(test["center_frequency_ghz"], list) else [
                test["center_frequency_ghz"]]
            try:
                instr = LTEDriver(
                    freq=frequencies[0] * 1e9,
                    pwr=test["power_dbm"][0],
                    waveform_file=test.get("waveform_file", None),
                    setup_file=test.get("setup_file", None)
                )
                for freq in frequencies:
                    for pwr in test["power_dbm"]:
                        test_config = test.copy()
                        test_config["center_frequency_ghz"] = freq
                        test_config["power_dbm"] = pwr
                        print(f"\n=== Test Set {test_set} (LTE) ===")
                        run_lte_measurement(test_config, test_set, instr)
                        test_set += 1
            except Exception as e:
                logger.error(f"LTE test initialization failed: {e}", exc_info=True)
            finally:
                if instr:
                    try:
                        LTEDriver.close_connections()
                    except Exception as e:
                        logger.error(f"Error closing LTE connections: {e}", exc_info=True)
                instr = None

    # Run SpurSearch tests
    spur_instr = None
    for test in inputs.get("spur_search", []):
        if test.get("run", False):
            logger.debug(f"Processing SpurSearch test: {test}")
            fundamental_ghz = test["fundamental_frequency_ghz"]
            if isinstance(fundamental_ghz, dict) and "range" in fundamental_ghz:
                range_config = fundamental_ghz["range"]
                start_ghz = range_config.get("start_ghz")
                stop_ghz = range_config.get("stop_ghz")
                step_mhz = range_config.get("step_mhz")
                if None in [start_ghz, stop_ghz, step_mhz]:
                    logger.error(f"Invalid range parameters: {range_config}")
                    continue
                frequencies = np.linspace(start_ghz, stop_ghz,
                                         int((stop_ghz - start_ghz) / (step_mhz / 1000.0)) + 1).tolist()
            elif isinstance(fundamental_ghz, (list, float, int)):
                frequencies = fundamental_ghz if isinstance(fundamental_ghz, list) else [fundamental_ghz]
            else:
                logger.error(f"Invalid fundamental_frequency_ghz format: {fundamental_ghz}")
                continue

            for freq_ghz in frequencies:
                try:
                    logger.info(f"Initializing SpurSearch for {freq_ghz:.3f} GHz")
                    spur_instr = SpurSearch(
                        fundamental_ghz=freq_ghz,
                        rbw_mhz=test.get("rbw_mhz", 0.01),
                        spur_limit_dbm=test.get("spur_limit_dbm", -95),
                        pwr=test.get("power_dbm", -70)
                    )
                    print(f"\n=== Test Set {test_set} (SpurSearch) ===")
                    print(f"SpurSearch Fundamental: {format_frequency(freq_ghz)}")
                    test_set = run_spur_search_measurement(test, test_set, spur_instr)
                except Exception as e:
                    logger.error(f"SpurSearch test set {test_set} for {freq_ghz:.3f} GHz failed: {e}", exc_info=True)
                    test_set += 1
                finally:
                    if spur_instr:
                        try:
                            spur_instr.close()
                        except Exception as e:
                            logger.error(f"Error closing SpurSearch for {freq_ghz:.3f} GHz: {e}")
                        spur_instr = None

    # Run STN tests
    stn_instr = None
    for test in inputs.get("STN", []):
        if test.get("run", False):
            logger.debug(f"Processing STN test: {test}")
            freq_input = test.get("center_frequency_ghz")
            try:
                if isinstance(freq_input, dict) and "range" in freq_input:
                    range_config = freq_input["range"]
                    start_ghz = range_config.get("start_ghz")
                    stop_ghz = range_config.get("stop_ghz")
                    step_mhz = range_config.get("step_mhz")
                    if None in [start_ghz, stop_ghz, step_mhz]:
                        raise ValueError(f"Missing range parameters: {range_config}")
                    if not all(isinstance(x, (int, float)) for x in [start_ghz, stop_ghz, step_mhz]):
                        raise ValueError(f"Invalid range parameter types: {range_config}")
                    if start_ghz > stop_ghz:
                        raise ValueError(f"Start frequency ({start_ghz} GHz) exceeds stop ({stop_ghz} GHz)")
                    if step_mhz <= 0:
                        raise ValueError(f"Invalid step size: {step_mhz} MHz")
                    num_steps = int((stop_ghz - start_ghz) / (step_mhz / 1000.0)) + 1
                    frequencies = np.linspace(start_ghz, stop_ghz, num_steps).tolist()
                    logger.info(f"Generated {len(frequencies)} frequencies: {frequencies} GHz")
                elif isinstance(freq_input, (list, float, int)):
                    frequencies = freq_input if isinstance(freq_input, list) else [freq_input]
                    logger.info(f"Using discrete frequencies: {frequencies} GHz")
                else:
                    raise ValueError(f"Invalid center_frequency_ghz format: {freq_input}")
            except Exception as e:
                logger.error(f"Failed to process frequency input: {e}", exc_info=True)
                continue

            iterations = test.get("iterations", 5)
            for freq in frequencies:
                logger.info(f"Preparing STN test set {test_set} at {freq:.3f} GHz")
                print(f"\n=== Test Set {test_set} (STN) ===")
                print(f"STN Freq: {freq:.3f} GHz, Iterations: {iterations}")
                try:
                    if stn_instr is None:
                        logger.debug("Initializing new STN instrument")
                        stn_instr = STN(freq=freq * 1e9)
                    else:
                        logger.debug(f"Reusing STN instrument, setting freq to {freq * 1e9:.3f} Hz")
                        stn_instr.STN_set_frequency(freq * 1e9)
                    run_stn_measurement(stn_instr, freq * 1e9, test_set, iterations=iterations)
                    test_set += 1
                except Exception as e:
                    logger.error(f"STN test set {test_set} failed: {e}", exc_info=True)
                    test_set += 1
                finally:
                    if stn_instr:
                        try:
                            stn_instr.close_connections()
                        except Exception as e:
                            logger.error(f"Error closing STN connections: {e}")
                        stn_instr = None

    # Save results to JSON
    results_path = os.path.join(os.path.dirname(__file__), 'results_output.json')
    try:
        with open(results_path, 'w') as outfile:
            json.dump(results, outfile, indent=2)
        logger.info(f"Saved results to: {results_path}")
    except Exception as e:
        logger.error(f"Error saving JSON results: {e}", exc_info=True)

    # Create DataFrame for Test Data
    df_rows = []
    for r in results:
        base_row = {
            "Test Set": r["test_set"],
            "Type": r["type"],
            "Center Frequency (GHz)": r.get("center_frequency_hz", r.get("fundamental_frequency_hz", None)) / 1e9,
            "Power (dBm)": r.get("power_dbm"),
            "Resource Blocks": r.get("resource_blocks"),
            "Resource Block Offset": r.get("resource_block_offset"),
            "Channel Bandwidth (MHz)": r.get("channel_bandwidth_mhz"),
            "Modulation Type": r.get("modulation_type"),
            "Subcarrier Spacing (kHz)": r.get("subcarrier_spacing_khz"),
            "Duplexing": r.get("duplexing"),
            "Link Direction": r.get("link_direction"),
            "Waveform File": r.get("waveform_file"),
            "Setup File": r.get("setup_file"),
            "EVM (dB)": r.get("evm"),
            "VSA_get_EVM Time (s)": r["timings"].get("VSA_get_EVM", 0),
            "Channel Power (dBm)": r.get("ch_pwr"),
            "ACP Lower (dB)": r.get("acp_lower"),
            "ACP Upper (dB)": r.get("acp_upper"),
            "Alternate Lower (dB)": r.get("alt_lower"),
            "Alternate Upper (dB)": r.get("alt_upper"),
            "VSA_get_ACLR Time (s)": r["timings"].get("VSA_get_ACLR", 0),
            "RBW (MHz)": r.get("rbw_hz", None) / 1e6 if r.get("rbw_hz") else None,
            "Spur Limit (dBm)": r.get("spur_limit_dbm"),
            "Spur Frequency (MHz)": None,
            "Spur Power (dBm)": None,
            "Spur Measurement Time (s)": r["timings"].get("measure", 0),
            "Get Results Time (s)": r["timings"].get("get_results", 0),
            "Iteration": None,
            "Marker (dBm)": None,
            "Marker Time (s)": None,
            "Stats Avg (dBm)": None,
            "Total Test Time (s)": None,
            "Config Summary": r.get("config"),
            "VSG_Config Time (s)": r["timings"].get("VSG_Config", r["timings"].get("VSG_config", 0)),
            "VSA_Config Time (s)": r["timings"].get("VSA_Config", r["timings"].get("VSA_config", 0)),
            "VSA_get_info Time (s)": r["timings"].get("VSA_get_info", 0),
            "Error": r.get("error")
        }
        if r["type"] == "SpurSearch" and r.get("spurs"):
            for spur in r["spurs"]:
                spur_row = base_row.copy()
                spur_row["Spur Frequency (MHz)"] = spur["frequency_hz"] / 1e6
                spur_row["Spur Power (dBm)"] = spur["power_dbm"]
                spur_row["Total Test Time (s)"] = sum(
                    t for k, t in r["timings"].items()
                    if k not in ["VSG_Config", "VSA_Config", "VSG_config", "VSA_config"]
                )
                df_rows.append(spur_row)
        elif r["type"] == "STN" and r.get("markers"):
            stats_dict = {}
            if r.get("stats"):
                matches = re.findall(r"(Min|Max|Avg|StdDev|Delta):([-+]?\d+\.\d+)", r["stats"])
                for key, value in matches:
                    stats_dict[key] = float(value)
            total_test_time = r.get("total_test_time", sum(m["meas_time"] for m in r["markers"] if m["meas_time"] is not None))
            total_test_time += r["timings"].get("VSA_Config", 0)
            for i, marker in enumerate(r["markers"], 1):
                stn_row = base_row.copy()
                stn_row["Iteration"] = i
                stn_row["Marker (dBm)"] = marker["marker"]
                stn_row["Marker Time (s)"] = marker["meas_time"]
                stn_row["Stats Avg (dBm)"] = stats_dict.get("Avg")
                stn_row["Total Test Time (s)"] = total_test_time
                df_rows.append(stn_row)
        else:
            base_row["Total Test Time (s)"] = sum(
                t for k, t in r["timings"].items()
                if k not in ["VSG_Config", "VSA_Config", "VSG_config", "VSA_config"]
            )
            df_rows.append(base_row)

    df = pd.DataFrame(df_rows)

    # Ensure numeric columns are floats
    for col in ["Center Frequency (GHz)", "Power (dBm)", "EVM (dB)", "Channel Power (dBm)",
                "ACP Lower (dB)", "ACP Upper (dB)", "Alternate Lower (dB)", "Alternate Upper (dB)",
                "VSA_get_EVM Time (s)", "VSA_get_ACLR Time (s)", "Total Test Time (s)",
                "VSG_Config Time (s)", "VSA_Config Time (s)", "VSA_get_info Time (s)",
                "RBW (MHz)", "Spur Limit (dBm)", "Spur Frequency (MHz)", "Spur Power (dBm)",
                "Spur Measurement Time (s)", "Get Results Time (s)", "Marker (dBm)", "Marker Time (s)",
                "Stats Avg (dBm)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Format numeric columns
    for col in ["Center Frequency (GHz)", "Power (dBm)", "EVM (dB)", "Channel Power (dBm)",
                "ACP Lower (dB)", "ACP Upper (dB)", "Alternate Lower (dB)", "Alternate Upper (dB)",
                "VSA_get_EVM Time (s)", "VSA_get_ACLR Time (s)", "Total Test Time (s)",
                "VSG_Config Time (s)", "VSA_Config Time (s)", "VSA_get_info Time (s)",
                "RBW (MHz)", "Spur Limit (dBm)", "Spur Frequency (MHz)", "Spur Power (dBm)",
                "Spur Measurement Time (s)", "Get Results Time (s)", "Marker (dBm)", "Marker Time (s)",
                "Stats Avg (dBm)"]:
        if col in df.columns:
            df[col] = df[col].map(lambda x: f"{x:.3f}" if pd.notna(x) else "", na_action='ignore')

    # Create Test Statistics DataFrame
    test_times = [r["total_test_time"] for r in results if r["type"] == "STN" and r.get("total_test_time") is not None]
    setup_times = [
        r["timings"].get("VSG_Config", r["timings"].get("VSG_config", 0)) +
        r["timings"].get("VSA_Config", r["timings"].get("VSA_config", 0))
        for r in results
    ]
    evm_times = [r["timings"].get("VSA_get_EVM", 0) for r in results]
    aclr_times = [r["timings"].get("VSA_get_ACLR", 0) for r in results]
    info_times = [r["timings"].get("VSA_get_info", 0) for r in results]
    spur_measure_times = [r["timings"].get("measure", 0) for r in results]
    spur_results_times = [r["timings"].get("get_results", 0) for r in results]
    marker_times = [m["meas_time"] for r in results if r["type"] == "STN" for m in r.get("markers", []) if m["meas_time"] is not None]
    stats_data = {
        "Metric": [
            "Number of Tests",
            "Total Test Time (s)",
            "Average Test Time (s)",
            "Median Test Time (s)",
            "Total Setup Time (s)",
            "Average Setup Time (s)",
            "Median Setup Time (s)",
            "Total VSA_get_EVM Time (s)",
            "Average VSA_get_EVM Time (s)",
            "Median VSA_get_EVM Time (s)",
            "Total VSA_get_ACLR Time (s)",
            "Average VSA_get_ACLR Time (s)",
            "Median VSA_get_ACLR Time (s)",
            "Total VSA_get_info Time (s)",
            "Average VSA_get_info Time (s)",
            "Median VSA_get_info Time (s)",
            "Total Spur Measurement Time (s)",
            "Average Spur Measurement Time (s)",
            "Median Spur Measurement Time (s)",
            "Total Get Results Time (s)",
            "Average Get Results Time (s)",
            "Median Get Results Time (s)",
            "Total Marker Time (s)",
            "Average Marker Time (s)",
            "Median Marker Time (s)"
        ],
        "Value": [
            len(results),
            sum(test_times),
            statistics.mean(test_times) if test_times else 0,
            statistics.median(test_times) if test_times else 0,
            sum(setup_times),
            statistics.mean(setup_times) if setup_times else 0,
            statistics.median(setup_times) if setup_times else 0,
            sum(evm_times),
            statistics.mean(evm_times) if evm_times else 0,
            statistics.median(evm_times) if evm_times else 0,
            sum(aclr_times),
            statistics.mean(aclr_times) if aclr_times else 0,
            statistics.median(aclr_times) if aclr_times else 0,
            sum(info_times),
            statistics.mean(info_times) if info_times else 0,
            statistics.median(info_times) if info_times else 0,
            sum(spur_measure_times),
            statistics.mean(spur_measure_times) if spur_measure_times else 0,
            statistics.median(spur_measure_times) if spur_measure_times else 0,
            sum(spur_results_times),
            statistics.mean(spur_results_times) if spur_results_times else 0,
            statistics.median(spur_results_times) if spur_results_times else 0,
            sum(marker_times),
            statistics.mean(marker_times) if marker_times and any(marker_times) else 0,
            statistics.median(marker_times) if marker_times and any(marker_times) else 0
        ]
    }
    stats_df = pd.DataFrame(stats_data)
    stats_df["Value"] = stats_df["Value"].map(lambda x: f"{x:.3f}" if isinstance(x, float) else x)

    excel_path = os.path.join(os.path.dirname(__file__), 'results_output.xlsx')
    try:
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Test Data', index=False)
            stats_df.to_excel(writer, sheet_name='Test Statistics', index=False)
        logger.info(f"Successfully saved to: {excel_path}")
    except Exception as e:
        logger.error(f"Error saving Excel results: {e}", exc_info=True)