import importlib
import inspect
import pathlib
import re
from datetime import datetime
from typing import Union

import numpy as np
import datajoint as dj
from element_interface.utils import find_root_directory

schema = dj.schema()

_linking_module = None


def activate(
    scan_schema_name: str,
    *,
    create_schema: bool = True,
    create_tables: bool = True,
    linking_module: str = None,
):
    """Activate this schema.

    Args:
        scan_schema_name (str): Schema name on the database server to activate the
            `scan` module
        create_schema (bool): When True (default), create schema in the database if it
            does not yet exist.
        create_tables (bool): When True (default), create tables in the database if they
            do not yet exist.
        linking_module (str): A module name or a module containing the required
            dependencies to activate the `scan` module.

    Dependencies:
    Upstream tables:
        + Session: Parent table to Scan, typically identifying a recording session
    """
        #     + Equipment: Reference table for Scan, specifying the equipment used for the
        #     acquisition of this scan.
        # + Location: Reference table for ScanLocation, specifying the scanned regions's
        #     anatomical location in the brain.

    if isinstance(linking_module, str):
        linking_module = importlib.import_module(linking_module)
    assert inspect.ismodule(
        linking_module
    ), "The argument 'dependency' must be a module's name or a module"

    global _linking_module
    _linking_module = linking_module

    schema.activate(
        scan_schema_name,
        create_schema=create_schema,
        create_tables=create_tables,
        add_objects=_linking_module.__dict__,
    )


# Functions required by element-calcium-imaging  -------------------------------
def get_imaging_root_data_dir() -> list:
    """Return imaging root data director(y/ies)

    Retrieve the root data director(y/ies) containing the imaging data
    for all subjects/sessions (e.g. acquired ScanImage raw files, output files from
    processing routines, etc.). All data paths and directories in DataJoint Elements are
    recommended to be stored as relative paths (posix format), with respect to some
    user-configured "root" directory, which varies from machine to machine
    (e.g. different mounted drive locations).

    Returns:
        dirs (list): A list of string(s) or Path(s) for the absolute paths of the imaging root data
            director(y/ies).
    """

    root_directories = _linking_module.get_imaging_root_data_dir()
    if isinstance(root_directories, (str, pathlib.Path)):
        root_directories = [root_directories]

    if hasattr(_linking_module, "get_processed_root_data_dir"):
        root_directories.append(_linking_module.get_processed_root_data_dir())

    return root_directories


def get_processed_root_data_dir() -> Union[str, pathlib.Path]:
    """Retrieve the root directory for all processed data.

    All data paths and directories in DataJoint Elements are recommended to be stored as
    relative paths (posix format), with respect to some user-configured "root"
    directory, which varies from machine to machine (e.g. different mounted drive
    locations).

    Returns:
        dir (str| pathlib.Path): Absolute path of the processed imaging root data
            directory.
    """

    if hasattr(_linking_module, "get_processed_root_data_dir"):
        return _linking_module.get_processed_root_data_dir()
    else:
        return get_imaging_root_data_dir()[0]


def get_calcium_imaging_files(scan_key: dict, acq_software: str) -> list:
    """Retrieve the list of absolute paths of the calcium imaging files associated with a given Scan and a given acquisition software (e.g. .tif, .sbx, etc.).

    Args:
        scan_key: Primary key of a Scan entry.
        acq_software: name of the acquisition software, matching AcquisitionSoftware entry (i.e. "ScanImage" "Scanbox", "NIS", or "PrairieView")

    Returns:
        A list of full file paths.
    """
    return _linking_module.get_calcium_imaging_files(scan_key, acq_software)


# ----------------------------- Table declarations ----------------------


@schema
class AcquisitionSoftware(dj.Lookup):
    """A list of acquisition softwares supported by the Element.

    Required to define a scan.

    Attributes:
        acq_software (str): Acquisition software
    """

    definition = """  # Acquisition softwares
    acq_software: varchar(24)
    """
    contents = zip(["ScanImage", "Scanbox", "NIS", "PrairieView"])


@schema
class Channel(dj.Lookup):
    """Recording channels for the imaging wavelengths.

    Attributes:
        channel (int): Channel index
    """

    definition = """  # A recording channel
    channel     : tinyint  # 0-based indexing
    """
    contents = zip(range(5))


@schema
class Scan(dj.Manual):
    """Scan defined by a measurement done using a scanner and an acquisition software.

    The details of the scanning data is placed in other tables, including,
    ScanLocation, ScanInfo, and ScanInfo's part tables.

    Attributes:
        Session (foreign key): A primary key from Session.
        rec_idx (int): Unique Scan ID.
        AcquisitionSoftware (foreign key): A primary key from AcquisitionSoftware.
        scan_notes (str, optional): Notes of the experimenter regarding the scan.
    """
    #         Equipment (foreign key, optional): A primary key from Equipment.

    definition = """
    -> Session
    rec_idx: int
    ---
    -> AcquisitionSoftware
    scan_notes='' : varchar(4095)
    """
    #     -> [nullable] Equipment


@schema
class ScanLocation(dj.Manual):
    """Anatomical location of the scanned region in the brain

    Attributes:
        Scan (foreign key): A primary key from Scan.

    """

    definition = """ # Anatomical location
    -> Scan
    """


@schema
class ScanInfo(dj.Imported):
    """
    Information about the scan extracted from the recorded files.

    Attributes:
        Scan (foreign key): A primary key from Scan.
        nfields (int): Number of fields.
        nchannels (int): Number of channels.
        ndepths (int): Number of scanning depths (planes).
        nframes (int): Number of recorded frames (time steps).
        nrois (int): Number of ROIs (see scanimage's multi ROI imaging).
        x (float, optional): ScanImage's 0 point in the motor coordinate system (um).
        y (float, optional): ScanImage's 0 point in the motor coordinate system (um).
        z (float, optional): ScanImage's 0 point in the motor coordinate system (um).
        fps (float) : Frames per second (Hz) - Volumetric Scan Rate.
        bidirectional (bool): True = bidirectional scanning.
        usecs_per_line (float, optional): Microseconds per scan line.
        fill_fraction (float, optional): Raster scan temporal fill fraction (see
            scanimage)
        scan_datetime (datetime, optional): Datetime of the scan.
        scan_duration (float, optional): Duration of the scan (s).
        bidirectional_z (bool, optional): True = bidirectional z-scan.
    """

    definition = """ # General data about the resoscans/mesoscans from header
    -> Scan
    ---
    nfields              : tinyint   # number of fields
    nchannels            : tinyint   # number of channels
    ndepths              : int       # Number of scanning depths (planes)
    nframes              : int       # number of recorded frames (time steps)
    nrois                : tinyint   # number of ROIs (see scanimage's multi ROI imaging)
    x=null               : float     # (um) ScanImage's 0 point in the motor coordinate system
    y=null               : float     # (um) ScanImage's 0 point in the motor coordinate system
    z=null               : float     # (um) ScanImage's 0 point in the motor coordinate system
    fps                  : float     # (Hz) frames per second - Volumetric Scan Rate
    bidirectional        : boolean   # true = bidirectional scanning
    usecs_per_line=null  : float     # microseconds per scan line
    fill_fraction=null   : float     # raster scan temporal fill fraction (see scanimage)
    scan_datetime=null   : datetime  # datetime of the scan
    scan_duration=null   : float     # (seconds) duration of the scan
    bidirectional_z=null : boolean   # true = bidirectional z-scan
    """

    class Field(dj.Part):
        """Stores field information of scan, including its coordinates, size, pixel
        pitch, etc.

        Attributes:
            ScanInfo (foreign key): A primary key from ScanInfo.
            field_idx (int): Unique field index.
            px_height (int): Image height in pixels.
            px_width (int): Image width in pixels.
            um_height (float, optional): Image height in microns.
            um_width (float, optional): Image width in microns.
            field_x (float, optional): X coordinate of the center of field in the motor
                coordinate system (um).
            field_y (float, optional): Y coordinate of the center of field in the motor
                coordinate system (um).
            field_z (float, optional): Relative depth of field (um).
            delay_image (longblob, optional): Delay between the start of the scan and
                pixels in this field (ms).
            roi (int, optional): The scanning roi (as recorded in the acquisition
                software) containing this field - only relevant to mesoscale scans.
        """

        definition = """ # field-specific scan information
        -> master
        field_idx         : int
        ---
        px_height         : smallint  # height in pixels
        px_width          : smallint  # width in pixels
        um_height=null    : float     # height in microns
        um_width=null     : float     # width in microns
        field_x=null      : float     # (um) center of field in the motor coordinate system
        field_y=null      : float     # (um) center of field in the motor coordinate system
        field_z=null      : float     # (um) relative depth of field
        delay_image=null  : longblob  # (ms) delay between the start of the scan and pixels in this field
        roi=null          : int       # the scanning roi (as recorded in the acquisition software) containing this field - only relevant to mesoscale scans
        """

    class ScanFile(dj.Part):
        """Filepath of the scan relative to root data directory.

        Attributes:
            ScanInfo (foreign key): A primary key from ScanInfo.
            file_path (str): Path of the scan file relative to the root data directory.
        """

        definition = """
        -> master
        file_path: varchar(255)  # Filepath relative to root data directory
        """

    def make(self, key):
        """Populate the ScanInfo with the information parsed from image files."""

        acq_software = (Scan & key).fetch1("acq_software")
        scan_filepaths = get_calcium_imaging_files(key, acq_software)

        if acq_software == "ScanImage":
            import scanreader

            # Read the scan
            scan_ = scanreader.read_scan(scan_filepaths)

            # Insert in ScanInfo
            x_zero, y_zero, z_zero = scan_.motor_position_at_zero or (None, None, None)

            self.insert1(
                dict(
                    key,
                    nfields=scan_.num_fields,
                    nchannels=scan_.num_channels,
                    nframes=scan_.num_frames,
                    ndepths=scan_.num_scanning_depths,
                    x=x_zero,
                    y=y_zero,
                    z=z_zero,
                    fps=scan_.fps,
                    bidirectional=scan_.is_bidirectional,
                    usecs_per_line=scan_.seconds_per_line * 1e6,
                    fill_fraction=scan_.temporal_fill_fraction,
                    nrois=scan_.num_rois if scan_.is_multiROI else 0,
                    scan_duration=scan_.num_frames / scan_.fps,
                )
            )
            # Insert Field(s)
            if scan_.is_multiROI:
                self.Field.insert(
                    [
                        dict(
                            key,
                            field_idx=field_id,
                            px_height=scan_.field_heights[field_id],
                            px_width=scan_.field_widths[field_id],
                            um_height=scan_.field_heights_in_microns[field_id],
                            um_width=scan_.field_widths_in_microns[field_id],
                            field_x=(
                                (x_zero or 0)
                                + scan_._degrees_to_microns(scan_.fields[field_id].x)
                            ),
                            field_y=(
                                (y_zero or 0)
                                + scan_._degrees_to_microns(scan_.fields[field_id].y)
                            ),
                            field_z=((z_zero or 0) + scan_.fields[field_id].depth),
                            delay_image=scan_.field_offsets[field_id],
                            roi=scan_.field_rois[field_id][0],
                        )
                        for field_id in range(scan_.num_fields)
                    ]
                )
            else:
                self.Field.insert(
                    [
                        dict(
                            key,
                            field_idx=plane_idx,
                            px_height=scan_.image_height,
                            px_width=scan_.image_width,
                            um_height=getattr(scan_, "image_height_in_microns", None),
                            um_width=getattr(scan_, "image_width_in_microns", None),
                            field_x=x_zero if x_zero else None,
                            field_y=y_zero if y_zero else None,
                            field_z=(
                                z_zero + scan_.scanning_depths[plane_idx]
                                if z_zero
                                else None
                            ),
                            delay_image=scan_.field_offsets[plane_idx],
                        )
                        for plane_idx in range(scan_.num_scanning_depths)
                    ]
                )
        elif acq_software == "Scanbox":
            import sbxreader

            # Read the scan
            sbx_meta = sbxreader.sbx_get_metadata(scan_filepaths[0])
            sbx_matinfo = sbxreader.sbx_get_info(scan_filepaths[0])
            is_multiROI = bool(
                sbx_matinfo.mesoscope.enabled
            )  # currently not handling "multiROI" ingestion

            if is_multiROI:
                raise NotImplementedError(
                    "Loading routine not implemented for Scanbox multiROI scan mode"
                )

            # Insert in ScanInfo
            x_zero, y_zero, z_zero = sbx_meta["stage_pos"]
            self.insert1(
                dict(
                    key,
                    nfields=(
                        sbx_meta["num_fields"]
                        if is_multiROI
                        else sbx_meta["num_planes"]
                    ),
                    nchannels=sbx_meta["num_channels"],
                    nframes=sbx_meta["num_frames"],
                    ndepths=sbx_meta["num_planes"],
                    x=x_zero,
                    y=y_zero,
                    z=z_zero,
                    fps=sbx_meta["frame_rate"],
                    bidirectional=sbx_meta == "bidirectional",
                    nrois=sbx_meta["num_rois"] if is_multiROI else 0,
                    scan_duration=(sbx_meta["num_frames"] / sbx_meta["frame_rate"]),
                )
            )
            # Insert Field(s)
            if not is_multiROI:
                px_width, px_height = sbx_meta["frame_size"]
                self.Field.insert(
                    [
                        dict(
                            key,
                            field_idx=plane_idx,
                            px_height=px_height,
                            px_width=px_width,
                            um_height=(
                                px_height * sbx_meta["um_per_pixel_y"]
                                if sbx_meta["um_per_pixel_y"]
                                else None
                            ),
                            um_width=(
                                px_width * sbx_meta["um_per_pixel_x"]
                                if sbx_meta["um_per_pixel_x"]
                                else None
                            ),
                            field_x=x_zero,
                            field_y=y_zero,
                            field_z=z_zero + sbx_meta["etl_pos"][plane_idx],
                        )
                        for plane_idx in range(sbx_meta["num_planes"])
                    ]
                )
        elif acq_software == "NIS":
            import nd2

            # Read the scan
            nd2_file = nd2.ND2File(scan_filepaths[0])
            is_multiROI = False  # MultiROI to be implemented later

            # Frame per second
            try:
                fps = 1000 / nd2_file.experiment[0].parameters.periods[0].periodDiff.avg
            except:  # noqa: E722
                fps = 1000 / nd2_file.experiment[0].parameters.periodDiff.avg

            # Estimate ND2 file scan duration
            def estimate_nd2_scan_duration(nd2_scan_obj):
                # Calculates scan duration for Nikon images
                ti = (
                    nd2_scan_obj.frame_metadata(0)
                    .channels[0]
                    .time.absoluteJulianDayNumber
                )  # Initial frame's JD.
                tf = (
                    nd2_scan_obj.frame_metadata(nd2_scan_obj.shape[0] - 1)
                    .channels[0]
                    .time.absoluteJulianDayNumber
                )  # Final frame's JD.

                return (tf - ti) * 86400 + 1 / fps

            scan_duration = sum(
                estimate_nd2_scan_duration(nd2.ND2File(f)) for f in scan_filepaths
            )

            try:
                scan_datetime = nd2_file.text_info["date"]
                scan_datetime = datetime.strptime(
                    scan_datetime,
                    (
                        "%m/%d/%Y %H:%M:%S %p"
                        if re.search(("AM|PM"), scan_datetime)
                        else "%m/%d/%Y %H:%M:%S"
                    ),
                )
                scan_datetime = datetime.strftime(scan_datetime, "%Y-%m-%d %H:%M:%S")
            except:  # noqa: E722
                scan_datetime = None

            # Insert in ScanInfo
            self.insert1(
                dict(
                    key,
                    nfields=nd2_file.sizes.get("P", 1),
                    nchannels=nd2_file.attributes.channelCount,
                    nframes=nd2_file.metadata.contents.frameCount,
                    ndepths=nd2_file.sizes.get("Z", 1),
                    x=None,
                    y=None,
                    z=None,
                    fps=fps,
                    bidirectional=bool(
                        nd2_file.custom_data["GrabberCameraSettingsV1_0"][
                            "GrabberCameraSettings"
                        ]["PropertiesQuality"]["ScanDirection"]
                    ),
                    nrois=0,
                    scan_datetime=scan_datetime,
                    scan_duration=scan_duration,
                )
            )

            # MultiROI to be implemented later

            # Insert in Field
            if not is_multiROI:
                self.Field.insert(
                    [
                        dict(
                            key,
                            field_idx=plane_idx,
                            px_height=nd2_file.attributes.heightPx,
                            px_width=nd2_file.attributes.widthPx,
                            um_height=nd2_file.attributes.heightPx
                            * nd2_file.voxel_size().y,
                            um_width=nd2_file.attributes.widthPx
                            * nd2_file.voxel_size().x,
                            field_x=None,
                            field_y=None,
                            field_z=None,
                        )
                        for plane_idx in range(nd2_file.sizes.get("Z", 1))
                    ]
                )
                       
        elif acq_software == "thorimage":
            import utils2p
            
            # Find the xml file of the given folder
            meta = utils2p.find_metadata_file(scan_filepaths)
            # Class for managing ThorImage metadata.
            metadata = utils2p.Metadata(meta)

            self.insert1(
                dict(
                    key,
                    nfields= metadata.get_metadata_value('ZStage','frames') ,
                    nchannels = metadata.get_n_channels(),
                    # Number of scanning depths = (planes)
                    ndepths= metadata.get_metadata_value('ZStage','zStreamFrames'), # PVScan_info["num_planes"],
                    nframes=metadata.get_metadata_value('Streaming','frames'),
                 #   nrois=PVScan_info["num_rois"],
                    x= metadata.get_metadata_value('Sample','initialStageLocationX'), #PVScan_info["x_pos"],
                    y= metadata.get_metadata_value('Sample','initialStageLocationY'), #PVScan_info["y_pos"],
                 #   z=PVScan_info["z_pos"],
                    fps = metadata.get_frame_rate(),
                    bidirectional= metadata.get_metadata_value('LSM','scanMode'),# PVScan_info["bidirectional"],
                    usecs_per_line= metadata.get_dwell_time(), # PVScan_info["usecs_per_line"],
                    scan_datetime = metadata.get_date_time(),
                    scan_duration= metadata.get_dwell_time(), #PVScan_info["scan_duration"],
                )
            )

            self.Field.insert(
                dict(
                    key,
                    field_idx= 1,
                    px_height = metadata.get_num_y_pixels(), 
                    px_width = metadata.get_num_x_pixels(),
                    um_height= metadata.get_metadata_value('LSM','heightUM'), #PVScan_info["height_in_um"]
                    um_width = metadata.get_width(), # PVScan_info["width_in_um"]
                    field_x= metadata.get_metadata_value('LSM','fineOffsetX'), # PVScan_info["fieldX"], 
                    field_y= metadata.get_metadata_value('LSM','fineOffsetY'), # PVScan_info["fieldY"],
                #    field_z=PVScan_info["fieldZ"]
                #    if PVScan_info["num_planes"] == 1
                #    else PVScan_info["fieldZ"][plane_idx],
                    )
                # for plane_idx in range(PVScan_info["num_planes"])
            )

        
        elif acq_software == "PrairieView":
            from element_interface import prairie_view_loader

            PVScan_info = prairie_view_loader.get_prairieview_metadata(
                scan_filepaths[0]
            )
            self.insert1(
                dict(
                    key,
                    nfields=PVScan_info["num_fields"],
                    nchannels=PVScan_info["num_channels"],
                    ndepths=PVScan_info["num_planes"],
                    nframes=PVScan_info["num_frames"],
                    nrois=PVScan_info["num_rois"],
                    x=PVScan_info["x_pos"],
                    y=PVScan_info["y_pos"],
                    z=PVScan_info["z_pos"],
                    fps=PVScan_info["frame_rate"],
                    bidirectional=PVScan_info["bidirectional"],
                    bidirectional_z=PVScan_info["bidirectional_z"],
                    usecs_per_line=PVScan_info["usecs_per_line"],
                    scan_datetime=PVScan_info["scan_datetime"],
                    scan_duration=PVScan_info["scan_duration"],
                )
            )

            self.Field.insert(
                dict(
                    key,
                    field_idx=plane_idx,
                    px_height=PVScan_info["height_in_pixels"],
                    px_width=PVScan_info["width_in_pixels"],
                    um_height=PVScan_info["height_in_um"],
                    um_width=PVScan_info["width_in_um"],
                    field_x=PVScan_info["fieldX"],
                    field_y=PVScan_info["fieldY"],
                    field_z=(
                        PVScan_info["fieldZ"]
                        if PVScan_info["num_planes"] == 1
                        else PVScan_info["fieldZ"][plane_idx]
                    ),
                )
                for plane_idx in range(PVScan_info["num_planes"])
            )
        else:
            raise NotImplementedError(
                f"Loading routine not implemented for {acq_software} "
                "acquisition software"
            )

        # Insert file(s)
        root_dir = find_root_directory(get_imaging_root_data_dir(), scan_filepaths[0])

        scan_files = [
            pathlib.Path(f).relative_to(root_dir).as_posix() for f in scan_filepaths
        ]
        self.ScanFile.insert([{**key, "file_path": f} for f in scan_files])


@schema
class ScanQualityMetrics(dj.Computed):
    """Metrics to assess the quality of the scan.

    Attributes:
        ScanInfo.Field (foreign key): Primary key from ScanInfo.Field.
    """

    definition = """
    -> ScanInfo.Field
    """

    class Frames(dj.Part):
        """Metrics used to evaluate each frame.

        Attributes:
            ScanInfo.Field (foreign key): Primary key from ScanInfo.Field.
            Channel (foreign key): Primary key from Channel.
            min_intensity (longblob): Minimum value of each frame.
            mean_intensity (longblob): Mean value of each frame.
            max_intensity (longblob): Maximum value of each frame.
            contrast (longblob): Contrast of each frame (i.e. difference between the 99 and 1 percentiles)
        """

        definition = """
        -> master
        -> Channel
        ---
        min_intensity: longblob   # Minimum value of each frame.
        mean_intensity: longblob  # Mean value of each frame.
        max_intensity: longblob   # Maximum value of each frame.
        contrast: longblob        # Contrast of each frame (i.e. difference between the 99 and 1 percentiles)
        """

    def make(self, key):
        acq_software, nchannels = (Scan * ScanInfo & key).fetch1(
            "acq_software", "nchannels"
        )
        scan_filepaths = get_calcium_imaging_files(key, acq_software)

        if acq_software == "ScanImage":
            import scanreader

            # Switch from FYXCT to TCYX
            data = scanreader.read_scan(scan_filepaths)[key["field_idx"]].transpose(
                3, 2, 0, 1
            )
        elif acq_software == "Scanbox":
            from sbxreader import sbx_memmap

            # Switch from TFCYX to TCYX
            data = sbx_memmap(scan_filepaths)[:, key["field_idx"]]
        elif acq_software == "NIS":
            import nd2

            nd2_file = nd2.ND2File(scan_filepaths[0])

            nd2_dims = {k: i for i, k in enumerate(nd2_file.sizes)}

            valid_dimensions = "TZCYX"
            assert set(nd2_dims) <= set(
                valid_dimensions
            ), f"Unknown dimensions {set(nd2_dims)-set(valid_dimensions)} in file {scan_filepaths[0]}."

            # Sort the dimensions in the order of TZCYX, skipping the missing ones.
            data = nd2_file.asarray().transpose(
                [nd2_dims[x] for x in valid_dimensions if x in nd2_dims]
            )

            # Expand array to include the missing dimensions.
            for i, dim in enumerate("TZC"):
                if dim not in nd2_dims:
                    data = np.expand_dims(data, i)

            data = data[:, key["field_idx"]]  # Switch from TFCYX to TCYX

        self.insert1(key)

        for channel in range(nchannels):
            movie = data[:, channel, :, :]

            self.Frames.insert1(
                dict(
                    key,
                    channel=channel,
                    min_intensity=movie.min(axis=(1, 2)),
                    mean_intensity=movie.mean(axis=(1, 2)),
                    max_intensity=movie.max(axis=(1, 2)),
                    contrast=np.percentile(movie, 99, axis=(1, 2))
                    - np.percentile(movie, 1, axis=(1, 2)),
                )
            )
