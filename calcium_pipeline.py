import os
import datajoint as dj
from element_calcium_imaging import (
    imaging, 
    scan,
    imaging_report,
    plotting,
)
import element_interface
import pathlib
import sys

dj.config["enable_python_native_blobs"] = True
dj.config['database.host'] = 'database.eflab.org:3306'
dj.conn()

schemata = {'experiment_db'   : 'lab_experiments',
            'stimulus_db'     : 'lab_stimuli',
            'behavior_db'     : 'lab_behavior',
            'recording_db'    : 'lab_recordings',
            'mice_db'         : 'lab_mice', 
            'decoder'         : 'lab_decoder'}

# create a virtual module for every database schema that you are going to use
for schema, value in schemata.items():
    globals()[schema] = dj.create_virtual_module(schema, value) #, create_tables=True, create_schema=True)

# Set Your prefix and Set "imaging_root_data_dir"
experiment_dir=  '/mnt/lab/data01/ScanImage_Imager/'
output_dir_base = '/mnt/local_storage/s2p_output'
prefix = 'lab_Ca_' 

dj.config['custom']={'database.prefix':prefix, 'imaging_root_data_dir':experiment_dir, 'output_dir':output_dir_base} #, 'imaging_root_data_dir':experiment_dir}#, 'output_dir':output_dir_base}

if "custom" not in dj.config:
    dj.config["custom"] = {}

# overwrite dj.config['custom'] values with environment variables if available

dj.config["custom"]["database.prefix"] = os.getenv(
    "DATABASE_PREFIX", dj.config["custom"].get("database.prefix", "")
)

dj.config["custom"]["imaging_root_data_dir"] = os.getenv(
    "IMAGING_ROOT_DATA_DIR", dj.config["custom"].get("imaging_root_data_dir", "")
)

db_prefix = dj.config["custom"].get("database.prefix", "")

# REPLAXED by getLocal
sys.path.append('/home/efadmin/Public/Christos/lab/python/')
import common
# def replace_directory(a_directory):
#     """
#     Replace Windows path prefix with Linux path prefix.
#     """
#     # Define the mapping
#     old_prefix = 'W:/ScanImage\\'
#     old_prefix2 = 'W:\ScanImage\\'
#     new_prefix = '/mnt/lab/data01/ScanImage/'
#     # Replace the prefix
#     if a_directory.startswith(old_prefix):
#         return a_directory.replace(old_prefix, new_prefix)
#     elif a_directory.startswith(old_prefix2):
#         return a_directory.replace(old_prefix2, new_prefix)        
#     return a_directory
# directory = common.Paths.getLocal(a_directory)

# Declare functions for retrieving data
def get_imaging_root_data_dir():
    """Retrieve imaging root data directory."""
    imaging_root_dirs = dj.config.get("custom", {}).get("imaging_root_data_dir", None)
    if not imaging_root_dirs:
        return None
    elif isinstance(imaging_root_dirs, (str, pathlib.Path)):
        return [imaging_root_dirs]
    elif isinstance(imaging_root_dirs, list):
        return imaging_root_dirs
    else:
        raise TypeError("`imaging_root_data_dir` must be a string, pathlib, or list")


def get_calcium_imaging_files(scan_key, acq_software: str):
    """Retrieve the list of absolute paths of the calcium imaging files associated with a given Scan and a given acquisition software (e.g. "ScanImage", "PrairieView", etc.)."""
    # Folder structure: root / subject / session / .tif or .sbx or .nd2
    rep_dir = common.Paths.getLocal((recording_db.Recording & scan_key).fetch1("target_path"))
    print(rep_dir)
    session_dir = element_interface.utils.find_full_path(
        get_imaging_root_data_dir(),
        # (session.SessionDirectory & scan_key).fetch1("session_dir"),
        # common.Paths.getLocal((recording_db.Recording & scan_key).fetch1("target_path"))
        # replace_directory((recording_db.Recording & scan_key).fetch1("target_path"))
        rep_dir
    )

    if acq_software == "ScanImage":
        filepaths = [fp.as_posix() for fp in session_dir.glob("*.tif")]
    elif acq_software == "Scanbox":
        filepaths = [fp.as_posix() for fp in session_dir.glob("*.sbx")]
    elif acq_software == "NIS":
        filepaths = [fp.as_posix() for fp in session_dir.glob("*.nd2")]
    elif acq_software == "PrairieView":
        filepaths = [fp.as_posix() for fp in session_dir.glob("*.tif")]
    elif acq_software == "ThorImage":
        filepaths = [fp.as_posix() for fp in session_dir.glob("*0.tif")]
    else:
        raise NotImplementedError(f"{acq_software} is not implemented")

    if not filepaths:
        raise FileNotFoundError(f"No {acq_software} file found in {session_dir}")
    return filepaths

Experimenter = experiment_db.Session
Session      = experiment_db.Session
Subject      = experiment_db.Session
Recording    = recording_db.Recording
# Equipment    = recording_db.Recording
# Location     = common.Paths

# Activate schemas
imaging.activate(db_prefix + "imaging", db_prefix + "scan", linking_module=__name__)