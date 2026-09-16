import logging
import json
import os
from pathlib import Path, PurePath
import typing as ty

from fileformats.core import extra_implementation
from fileformats.generic import UnicodeFile
from fileformats.application import Json, Pdf
from fileformats.medimage.base import MedicalImagingData

from fileformats.vendor.canfield.medimage import (
    TomSeedLog,
    TomTrackLog,
    TrackedDir,
    DexiDataDir,
    WholeBodyCapture,
    VectraExport,
    LesionAnalysisDir,
)

logger = logging.getLogger(__name__)


@extra_implementation(MedicalImagingData.deidentify)
def vectra_deidentify(
    export_dir: VectraExport,
    out_dir: os.PathLike[str],
    spec: ty.Any = None,
    in_place: bool = False,
    **kwargs: ty.Any,
) -> VectraExport:
    """
    Deidentifies the image by stripping any subject-identifying information from the
    image header. The exact implementation of this method will depend on the
    specific image format and the type of identifying information that is present. The
    output files should be named with a new file path(s) that is derived from the metadata,
    such that it doesn't contain any subject-identifying information within it.

    Parameters
    ----------
    export_dir: VectraExport
        The directory containing the Canfield data export directory to be deidentified.
    out_dir: PathLike
        The directory where the deidentified files should be written.
    spec: Any, optional
        A specification for the deidentification process, which may include details on
        which fields to remove or how to handle certain types of data. The exact
        structure of this specification will depend on the specific image format and the
        type of identifying information that is present.

    Returns
    -------
    VectraExport
        The deidentified VectraExport object.
    """
    if not in_place:
        export_dir = export_dir.copy(dest_dir=Path(out_dir))

    for whole_body_capture_dir in export_dir.whole_body_capture_dirs.values():
        whole_body_capture_dir.deidentify(in_place=True, spec=spec, **kwargs)

    for lesion_analysis_dir in export_dir.lesion_analysis_dirs.values():
        lesion_analysis_dir.deidentify(in_place=True, spec=spec, **kwargs)

    for report in export_dir.dermx_reports:
        pdf_report_deidentify(report)

    return export_dir


@extra_implementation(MedicalImagingData.deidentify)
def vectra_3d_capture_deidentify(
    capture_dir: WholeBodyCapture,
    out_dir: os.PathLike[str],
    spec: ty.Any = None,
    in_place: bool = False,
    **kwargs: ty.Any,
) -> WholeBodyCapture:
    if not in_place:
        capture_dir = capture_dir.copy(dest_dir=Path(out_dir))

    if capture_dir.sglue_log_file:
        sglue_log_deidentify(capture_dir.sglue_log_file)

    for tracked_dir in capture_dir.tracked_dirs.values():
        tracked_dir.deidentify(in_place=True, spec=spec, **kwargs)

    return capture_dir


@extra_implementation(MedicalImagingData.deidentify)
def tracked_dir_deidentify(
    tracked_dir: TrackedDir,
    out_dir: os.PathLike[str],
    spec: ty.Any = None,
    in_place: bool = False,
    **kwargs: ty.Any,
) -> TrackedDir:
    if not in_place:
        tracked_dir = tracked_dir.copy(dest_dir=Path(out_dir))

    tracked_dir.seed_log_file.deidentify(in_place=True, spec=spec, **kwargs)
    tracked_dir.track_log_file.deidentify(in_place=True, spec=spec, **kwargs)
    tracking_log_deidentify(tracked_dir.tracking_log_file)

    return tracked_dir


@extra_implementation(MedicalImagingData.deidentify)
def lesion_analysis_deidentify(
    lesion_dir: LesionAnalysisDir,
    out_dir: os.PathLike[str],
    spec: ty.Any = None,
    in_place: bool = False,
    **kwargs: ty.Any,
) -> LesionAnalysisDir:
    if not in_place:
        lesion_dir = lesion_dir.copy(dest_dir=Path(out_dir))

    for dexi_dir in lesion_dir.dexi_dirs.values():
        dexi_dir.deidentify(in_place=True, spec=spec, **kwargs)

    return lesion_dir


@extra_implementation(MedicalImagingData.deidentify)
def dexi_data_dir_deidentify(
    dexi_data_dir: DexiDataDir,
    out_dir: os.PathLike[str],
    spec: ty.Any = None,
    in_place: bool = False,
    **kwargs: ty.Any,
) -> DexiDataDir:
    if not in_place:
        dexi_data_dir = dexi_data_dir.copy(dest_dir=Path(out_dir))

    result_json_deidentify(dexi_data_dir.result_file)

    return dexi_data_dir


def pdf_report_deidentify(pdf_report: Pdf) -> Pdf:
    """
    De-identifies the DermX PDF reports by replacing the contents with "Report redacted"
    Parameters:
    - pdf_report: Path to the PDF report file
    Returns:
    - PDF file contents for writing the de-identified PDF
    """
    if not pdf_report.name.startswith("DermX Report"):
        raise ValueError(f"Expected a DermX Report PDF, but got '{pdf_report.name}'")

    content = "BT /F1 24 Tf 72 700 Td (Report redacted) Tj ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] ",
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = "%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(pdf.encode("latin-1")))
        pdf += f"{i} 0 obj\n{obj}\nendobj\n"

    xref_start = len(pdf.encode("latin-1"))
    pdf += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    pdf += "".join(f"{off:010d} 00000 n \n" for off in offsets)
    pdf += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF"
    pdf_report.save(pdf)

    return pdf_report


def result_json_deidentify(result_json: Json) -> Json:
    """
    De-identify the `result.json` file generated by DEXI version 1
    Replaces the `ImageLocation` field in each `OutputImages` entry with just the filename, removing any directory paths.
    Parameters:
    - result_json: Path to the `result.json` file
    Returns:
    - A JSON string with de-identified data
    """
    if result_json.name != "result.json":
        raise ValueError(f"Expected 'result.json', but got '{result_json.name}'")

    with open(result_json) as resultjson_contents:
        json_data = json.load(resultjson_contents)

        if result_json.parent.name != "DexiData":
            return Json(json.dumps(json_data, indent=2))

        algorithms = json_data.get("Algorithms", [])

        if not isinstance(algorithms, list):
            logger.warning("Algorithms is not a list.")
            return Json(json.dumps(json_data, indent=4))

        for algorithm in algorithms:
            if not isinstance(algorithm, dict):
                continue

            output_images = algorithm.get("OutputImages", [])

            if not isinstance(output_images, list):
                logger.warning("OutputImages is not a list.")
                return Json(json.dumps(json_data, indent=4))

            for image in output_images:
                if not isinstance(image, dict):
                    continue

                location = image.get("ImageLocation")
                if location and isinstance(location, str):
                    location_filename = PurePath(location)
                    image["ImageLocation"] = location_filename.name

    return Json(json.dumps(json_data, indent=4))


def log_file_deidentify(
    log_file: UnicodeFile, sensitive_line_prefixes: str | tuple[str, ...]
) -> UnicodeFile:
    """
    De-identify a log file by removing lines that start with specified sensitive prefixes.
    Parameters:
    - log_file: Path to the log file
    - sensitive_line_prefixes: A string or tuple of strings representing the prefixes of lines to remove
    Returns:
    - A string containing the de-identified log contents
    """
    with open(log_file) as log_contents:
        lines = log_contents.readlines()

    deidentified_lines = []
    for line in lines:
        if not line.startswith(sensitive_line_prefixes):
            deidentified_lines.append(line)

    log_file.save("".join(deidentified_lines))
    return log_file


def sglue_log_deidentify(log_file: UnicodeFile) -> UnicodeFile:
    """
    De-identify the `sglue-log.txt` file by removing lines that start with "cmd line as invoked".
    Parameters:
    - log_file: Path to the `sglue-log.txt` file
    Returns:
    - A string containing the de-identified log contents
    """
    if log_file.name != "sglue-log.txt":
        raise ValueError(f"Expected 'sglue-log.txt', but got '{log_file.name}'")
    file_specific_prefixes = "cmd line as invoked"
    return log_file_deidentify(log_file, file_specific_prefixes)


@extra_implementation(MedicalImagingData.deidentify)
def tom_seed_log_deidentify(
    tom_seed_log: TomSeedLog,
    out_dir: os.PathLike[str],
    spec: ty.Any = None,
    in_place: bool = False,
    **kwargs: ty.Any,
) -> TomSeedLog:
    """
    De-identify the `tom-seed.log` file by removing lines that start with "loading".
    Parameters:
    - tom_seed_log: Path to the `tom-seed.log` file
    Returns:
    - A string containing the de-identified log contents
    """
    if not in_place:
        tom_seed_log = tom_seed_log.copy(Path(out_dir))
    if not tom_seed_log.name.endswith("tom-seed.log"):
        raise ValueError(f"Expected 'tom-seed.log', but got '{tom_seed_log.name}'")

    file_specific_prefixes = ("loading", "loaded")
    return TomSeedLog(log_file_deidentify(tom_seed_log, file_specific_prefixes))


@extra_implementation(MedicalImagingData.deidentify)
def tom_track_log_deidentify(
    tom_track_log: TomTrackLog,
    out_dir: os.PathLike[str],
    spec: ty.Any = None,
    in_place: bool = False,
    **kwargs: ty.Any,
) -> TomTrackLog:
    """
    De-identify the `tom-track-log.txt` file by removing all contents.
    Parameters:
    - tom_track_log: Path to the `tom-track.log` file
    Returns:
    - An empty string, effectively removing all contents of the log
    """
    if not in_place:
        tom_track_log = tom_track_log.copy(Path(out_dir))
    if not tom_track_log.name.endswith("tom-track.log"):
        raise ValueError(f"Expected 'tom-track.log', but got '{tom_track_log.name}'")

    file_specific_prefixes = ("no images", "mesh vertex")
    return TomTrackLog(log_file_deidentify(tom_track_log, file_specific_prefixes))


def tracking_log_deidentify(log_file: UnicodeFile) -> UnicodeFile:
    """
    De-identify the `tracking-log.txt` file by removing all contents.
    Parameters:
    - log_file: Path to the `tracking-log.txt` file
    Returns:
    - An empty string, effectively removing all contents of the log
    """
    if log_file.name != "tracking-log.txt":
        raise ValueError(f"Expected 'tracking-log.txt', but got '{log_file.name}'")
    return log_file_deidentify(log_file, "")
