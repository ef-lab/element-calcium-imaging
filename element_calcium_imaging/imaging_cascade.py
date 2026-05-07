import datajoint as dj
import numpy as np
from cascade2p import cascade  
import ruamel.yaml as yaml

dj.config["enable_python_native_blobs"] = True
dj.config['database.host'] = 'database.eflab.org:3306'

schemata = {'experiment_db'   : 'lab_experiments',
            'stimulus_db'     : 'lab_stimuli',
            'behavior_db'     : 'lab_behavior',
            'recording_db'    : 'lab_recordings',
            'mice_db'         : 'lab_mice', 
            'imaging'         : 'lab_Ca_imaging',
            'imaging_report'  : 'lab_Ca_imaging_report',
            'scan'            : 'lab_Ca_scan',
            'ephys'           : 'lab_npx_ephys' ,
            'ephys_report'    : 'lab_npx_ephys_report' ,
            'probe'           : 'lab_npx_probe' ,
            'analysis_test '  : 'lab_npx_analysis_test',
            'lab_anatomy'     : 'lab_anatomy',
            'reso'            : 'pipeline_reso',
            'meso'            : 'pipeline_meso',
            'old_fuse'        : 'pipeline_fuse',
            'simulations'     : 'maria_simulations',
            'stimulus'        : 'pipeline_stimulus',
            'old_anatomy'     : 'pipeline_anatomy',
            'fuse'            : 'lab_fuse',
            'experiment'      : 'pipeline_experiment'
           }

# create a virtual module for every database schema that you are going to use
for schemas, value in schemata.items():
    globals()[schemas] = dj.create_virtual_module(schemas, value, create_tables=True, create_schema=True)


schema = dj.schema('lab_Ca_imaging')  # or reuse existing `schema` object


@schema
class ActivityCascadeMethod(dj.Lookup):
    definition = """
    # Cascade spike inference configuration
    cascade_method: varchar(64)
    ---
    model_name: varchar(128)
    model_folder='Pretrained_models': varchar(255)
    threshold=1: tinyint
    """

    contents = zip(
        # cascade_method label
        ["GC8_5Hz_400ms_default"],
        # model_name (exact string from your YAML)
        ["GC8_EXC_5Hz_smoothing400ms_high_noise"],
        # model_folder (absolute path so it works regardless of cwd)
        ["/home/efadmin/Public/Cascade/Pretrained_models"],
        # threshold (1 = AP-size thresholding, good default)
        [1],
    )

# GCaMP8 pre-trained model
# https://gcamp6f.com/2024/08/22/spike-inference-with-gcamp8-new-pretrained-models-available/

@schema
class ActivityCascade(dj.Computed):
    """Neural activity inferred with Cascade from ΔF/F traces.

    Depends only on Fluorescence + a chosen Cascade model.
    """

    definition = """
    # Neural activity inferred with Cascade
    -> imaging.Fluorescence
    -> ActivityCascadeMethod
    """

    class Trace(dj.Part):
        """Cascade activity trace for each ROI (mask, channel)."""

        definition = """
        -> master
        -> imaging.Fluorescence.Trace
        ---
        activity_trace: longblob  # spike rate / probability from Cascade (same shape as fluorescence)
        """

    def make(self, key):
        """
        For one (Fluorescence, CascadeMethod) pair:
        1) Collect all ΔF/F traces (neurons x time)
        2) Run Cascade
        3) Store resulting activity traces per ROI
        """

        # --- Fetch Cascade config for this job ---
        cfg = (ActivityCascadeMethod & key).fetch1()
        model_name = cfg["model_name"]
        model_folder = cfg["model_folder"]
        thr = cfg["threshold"]
        if thr == -1:
            threshold = False
        else:
            threshold = int(thr)

        # --- Fetch ΔF/F traces for this Fluorescence key ---
        # We fetch keys so we can map each row back to a Fluorescence.Trace
        trace_keys, fluo_traces = (Fluorescence.Trace & key).fetch(
            "KEY", "fluorescence", order_by="mask"
        )

        # Convert to 2D array: neurons x time (float32 is enough)
        dff = np.vstack([np.asarray(f, dtype=np.float32) for f in fluo_traces])

        # IMPORTANT: Cascade expects ΔF/F *fractions*, not percent.
        # If your traces are in percent, convert: dff /= 100.0

        # --- Run Cascade ---
        # This uses cascade2p.cascade.predict(model_name, traces, ...)
        spike_rate = cascade.predict(
            model_name=model_name,
            traces=dff,
            model_folder=model_folder,
            threshold=threshold,
            verbosity=0,
        )
        # spike_rate has shape (neurons x time), same order as dff

        # --- Insert into DataJoint ---
        self.insert1(key)

        tuples = []
        for k, spks in zip(trace_keys, spike_rate):
            tuples.append({
                **key,
                **k,  # contains mask, fluo_channel, etc. from Fluorescence.Trace
                "activity_trace": spks.astype(np.float32),
            })

        # Insert in chunks to avoid connection / packet size issues
        try:
            self.Trace.insert(tuples, chunk_size=1000)
        except Exception as e:
            print(
                "ActivityCascade.Trace bulk insert failed, falling back to insert1(). "
                f"Error was: {e}"
            )
            for t in tuples:
                self.Trace.insert1(t)
